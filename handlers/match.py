from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from pymongo.asynchronous.database import AsyncDatabase
import html
import logging

from database.models import User, Gender
from database import repo
from utils.texts import Texts
from utils.helpers import get_admin_status
from keyboards.inline import gender_pref_kb
from keyboards.reply import main_menu_kb, gender_kb, chat_kb, searching_kb
from handlers.start import Registration

# `router`      -> menu buttons / callbacks (must be included BEFORE relay.router)
# `chat_router` -> catch-all that forwards chat messages (must be included LAST)
router = Router()
chat_router = Router()

MAX_MATCH_ATTEMPTS = 5


async def _clear_state_of(bot: Bot, storage, tg_id: int) -> None:
    """Reset the FSM state of ANOTHER user (private chat: chat_id == user_id)."""
    try:
        key = StorageKey(bot_id=bot.id, chat_id=tg_id, user_id=tg_id)
        await storage.set_state(key, None)
        await storage.set_data(key, {})
    except Exception as e:
        logging.warning(f"[MATCH] could not clear state of {tg_id}: {e}")


async def _ask_gender(message: types.Message, state: FSMContext) -> None:
    await message.answer(Texts.CHOOSE_GENDER, reply_markup=gender_kb(), parse_mode="HTML")
    await state.set_state(Registration.choosing_gender)


async def _search(bot: Bot, storage, db: AsyncDatabase, db_user: User, pref_gender: Gender, target: types.Message) -> None:
    """Find a partner right now, otherwise put the user in the waiting queue."""
    await repo.update_user(db, db_user, match_pref=pref_gender.value)

    # Drop an old/stale queue entry so the (new) preference is used
    await repo.leave_queue(db, db_user.id)

    partner = None
    for _ in range(MAX_MATCH_ATTEMPTS):
        candidate_id = await repo.pop_match(db, db_user, pref_gender)
        if not candidate_id:
            break

        candidate = await repo.get_user(db, candidate_id)
        if not candidate:
            continue
        # skip ghosts: queue entry of someone who is already chatting
        if await repo.get_active_session(db, candidate.id):
            continue

        session = await repo.create_session(db, db_user.id, candidate.id)

        partner_name = html.escape(candidate.nickname or candidate.full_name or "Anonymous")
        my_name = html.escape(db_user.nickname or db_user.full_name or "Anonymous")
        msg = "<b>🎉 You're connected!</b>\nYou can now chat with each other."

        try:
            await bot.send_message(
                candidate.tg_id,
                f"{msg}\n👤 Chat partner: <b>{my_name}</b>",
                parse_mode="HTML",
                reply_markup=chat_kb(),
            )
        except Exception as e:
            # Partner blocked the bot / deleted the chat -> drop them and keep searching
            logging.warning(f"[MATCH] cannot reach {candidate.tg_id}: {e}")
            await repo.end_session(db, session)
            continue

        await _clear_state_of(bot, storage, candidate.tg_id)
        await target.answer(
            f"{msg}\n👤 Chat partner: <b>{partner_name}</b>",
            parse_mode="HTML",
            reply_markup=chat_kb(),
        )
        partner = candidate
        logging.info(f"[MATCH] {db_user.tg_id} <-> {candidate.tg_id}")
        break

    if not partner:
        if await repo.enqueue(db, db_user, pref_gender):
            await target.answer(
                "🔎 <b>Searching for a suitable person...</b>\nPlease be patient.",
                parse_mode="HTML",
                reply_markup=searching_kb(),
            )
            logging.info(f"[MATCH] {db_user.tg_id} queued (gender={db_user.gender.value}, wants={pref_gender.value})")


@router.message(F.text == Texts.RANDOM_CHAT)
async def start_matchmaking(message: types.Message, db: AsyncDatabase, db_user: User, state: FSMContext):
    # Pressing a menu button always leaves any old flow (link-message, profile edit, ...)
    await state.clear()

    if await repo.get_active_session(db, db_user.id):
        await message.answer("You are already in a chat!", parse_mode="HTML")
        return

    # Matching is impossible without a gender
    if db_user.gender == Gender.UNKNOWN:
        await _ask_gender(message, state)
        return

    await message.answer("Who would you like to chat with?", reply_markup=gender_pref_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("match_pref_"))
async def start_matching(
    callback: types.CallbackQuery, db: AsyncDatabase, state: FSMContext, db_user: User, bot: Bot
):
    # callback_data: match_pref_male / match_pref_female / match_pref_any
    pref = callback.data.split("_")[-1]
    pref_gender = Gender.MALE if pref == "male" else Gender.FEMALE if pref == "female" else Gender.UNKNOWN

    await state.clear()

    if db_user.gender == Gender.UNKNOWN:
        await callback.answer()
        await _ask_gender(callback.message, state)
        return

    if await repo.get_active_session(db, db_user.id):
        await callback.message.answer("You are already in a chat!", parse_mode="HTML")
        await callback.answer()
        return

    await _search(bot, state.storage, db, db_user, pref_gender, callback.message)

    await callback.answer()


@router.message(F.text == Texts.SEND_PROFILE)
async def send_profile_in_chat(message: types.Message, db: AsyncDatabase, db_user: User, bot: Bot):
    session = await repo.get_active_session(db, db_user.id)

    if not session:
        await message.answer("⚠️ You are not in an active chat.", parse_mode="HTML")
        return

    partner = await repo.get_user(db, session.partner_of(db_user.id))

    gender_text = (
        Texts.GENDER_MALE if db_user.gender == Gender.MALE
        else Texts.GENDER_FEMALE if db_user.gender == Gender.FEMALE
        else "Unknown"
    )
    bio = db_user.bio or "None"
    age = db_user.age or "Unknown"
    name = html.escape(db_user.nickname or db_user.full_name or "Anonymous")

    profile_text = (
        f"<b>👤 Your Chat Partner's Profile:</b>\n\n"
        f"🏷 <b>Name:</b> {name}\n"
        f"🎂 <b>Age:</b> {age}\n"
        f"🚻 <b>Gender:</b> {gender_text}\n"
        f"📝 <b>Bio:</b> {html.escape(bio)}"
    )

    await bot.send_message(partner.tg_id, profile_text, parse_mode="HTML")
    await message.answer("✅ Your profile has been sent to your chat partner.", parse_mode="HTML")


@router.message(F.text == Texts.BLOCK_USER)
async def block_user_btn(message: types.Message, db: AsyncDatabase, db_user: User, bot: Bot):
    session = await repo.get_active_session(db, db_user.id)

    if not session:
        await message.answer("⚠️ You are not in an active chat.", parse_mode="HTML")
        return

    partner = await repo.get_user(db, session.partner_of(db_user.id))

    await repo.add_block(db, db_user.id, partner.id)
    await repo.end_session(db, session)

    my_admin = await get_admin_status(db_user.tg_id, db)
    partner_admin = await get_admin_status(partner.tg_id, db)
    await message.answer(Texts.USER_BLOCKED, reply_markup=main_menu_kb(is_admin=my_admin), parse_mode="HTML")
    try:
        await bot.send_message(partner.tg_id, Texts.YOU_ARE_BLOCKED, reply_markup=main_menu_kb(is_admin=partner_admin), parse_mode="HTML")
    except Exception:
        pass


@router.message(F.text == Texts.NEXT_CHAT)
async def next_chat(message: types.Message, db: AsyncDatabase, db_user: User, bot: Bot, state: FSMContext):
    """End the current chat (if any) and immediately look for someone new."""
    await state.clear()

    if db_user.gender == Gender.UNKNOWN:
        await _ask_gender(message, state)
        return

    session = await repo.get_active_session(db, db_user.id)
    if session:
        await repo.end_session(db, session)
        partner = await repo.get_user(db, session.partner_of(db_user.id))
        partner_is_admin = await get_admin_status(partner.tg_id, db)
        try:
            await bot.send_message(partner.tg_id, "🏁 Your chat partner has left the chat.", reply_markup=main_menu_kb(is_admin=partner_is_admin), parse_mode="HTML")
        except Exception:
            pass

    if not db_user.match_pref:
        await message.answer("Who would you like to chat with?", reply_markup=gender_pref_kb(), parse_mode="HTML")
        return

    await message.answer("⏭ Looking for the next person...", parse_mode="HTML")
    await _search(bot, state.storage, db, db_user, Gender(db_user.match_pref), message)


@router.message(Command("stop"))
@router.message(F.text.in_({Texts.STOP_CHAT, Texts.CANCEL_SEARCH, Texts.STOP_SEARCH}))
async def stop_chat(message: types.Message, db: AsyncDatabase, db_user: User, bot: Bot, state: FSMContext):
    await state.clear()
    session = await repo.get_active_session(db, db_user.id)
    is_admin = await get_admin_status(db_user.tg_id, db)

    if session:
        await repo.end_session(db, session)
        partner = await repo.get_user(db, session.partner_of(db_user.id))

        await message.answer("🏁 The chat has been ended at your request.", reply_markup=main_menu_kb(is_admin=is_admin), parse_mode="HTML")

        partner_is_admin = await get_admin_status(partner.tg_id, db)
        try:
            await bot.send_message(partner.tg_id, "🏁 Your chat partner has left the chat.", reply_markup=main_menu_kb(is_admin=partner_is_admin), parse_mode="HTML")
        except Exception:
            pass
    elif await repo.leave_queue(db, db_user.id):
        await message.answer("❌ You have left the waiting queue.", reply_markup=main_menu_kb(is_admin=is_admin), parse_mode="HTML")
    else:
        await message.answer("⚠️ You are not in an active chat.", reply_markup=main_menu_kb(is_admin=is_admin), parse_mode="HTML")


@chat_router.message()
async def process_chat_message(message: types.Message, db: AsyncDatabase, db_user: User, bot: Bot):
    # Catch-all: relays messages between matched users.
    session = await repo.get_active_session(db, db_user.id)
    if not session:
        return

    partner = await repo.get_user(db, session.partner_of(db_user.id))
    try:
        await bot.copy_message(
            chat_id=partner.tg_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
    except Exception:
        # Maybe the partner blocked the bot
        pass
