from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from pymongo.asynchronous.database import AsyncDatabase
from database.models import User, Gender
from database import repo
from utils.texts import Texts
from keyboards.inline import gender_pref_kb
from keyboards.reply import main_menu_kb
from aiogram.fsm.context import FSMContext
import html
from utils.helpers import get_admin_status

router = Router()


def _chat_kb() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=Texts.STOP_CHAT), types.KeyboardButton(text=Texts.BLOCK_USER)],
            [types.KeyboardButton(text=Texts.SEND_PROFILE)]
        ],
        resize_keyboard=True
    )


@router.message(F.text == Texts.RANDOM_CHAT)
async def start_matchmaking(message: types.Message, db: AsyncDatabase, db_user: User):
    # Check if already in session
    if await repo.get_active_session(db, db_user.id):
        await message.answer("You are already in a chat!", parse_mode="HTML")
        return

    await message.answer("Who would you like to chat with?", reply_markup=gender_pref_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("match_pref_"))
async def start_matching(callback: types.CallbackQuery, db: AsyncDatabase, state: FSMContext, db_user: User):
    # callback_data: match_pref_male / match_pref_female / match_pref_any
    pref = callback.data.split("_")[-1]
    pref_gender = Gender.MALE if pref == "male" else Gender.FEMALE if pref == "female" else Gender.UNKNOWN

    # Already chatting?
    if await repo.get_active_session(db, db_user.id):
        await callback.message.answer("You are already in a chat!", parse_mode="HTML")
        await callback.answer()
        return

    # Check if already in queue
    if await repo.is_in_queue(db, db_user.id):
        await callback.message.answer("⚠️ You are already in the waiting queue.", parse_mode="HTML")
        await callback.answer()
        return

    # Atomically claim the oldest compatible person in the queue
    match_user_id = await repo.pop_match(db, db_user, pref_gender)
    partner = await repo.get_user(db, match_user_id) if match_user_id else None

    if partner:
        await repo.create_session(db, db_user.id, partner.id)

        partner_name = html.escape(partner.nickname or partner.full_name or "Anonymous")
        my_name = html.escape(db_user.nickname or db_user.full_name or "Anonymous")

        chat_kb = _chat_kb()
        msg = "<b>🎉 You're connected!</b>\nYou can now chat with each other."
        await callback.message.answer(f"{msg}\n👤 Chat partner: <b>{partner_name}</b>", parse_mode="HTML", reply_markup=chat_kb)
        await callback.bot.send_message(partner.tg_id, f"{msg}\n👤 Chat partner: <b>{my_name}</b>", parse_mode="HTML", reply_markup=chat_kb)
    else:
        # Add to queue
        if await repo.enqueue(db, db_user, pref_gender):
            await callback.message.answer("🔎 <b>Searching for a suitable person...</b>\nPlease be patient.", parse_mode="HTML")
        else:
            await callback.message.answer("⚠️ You are already in the waiting queue.", parse_mode="HTML")

    await callback.answer()


@router.message(F.text == Texts.SEND_PROFILE)
async def send_profile_in_chat(message: types.Message, db: AsyncDatabase, db_user: User, bot: Bot):
    session = await repo.get_active_session(db, db_user.id)

    if not session:
        await message.answer("⚠️ You are not in an active chat.", parse_mode="HTML")
        return

    partner = await repo.get_user(db, session.partner_of(db_user.id))

    # Format Profile
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

    # Create Block + end session
    await repo.add_block(db, db_user.id, partner.id)
    await repo.end_session(db, session)

    my_admin = await get_admin_status(db_user.tg_id, db)
    partner_admin = await get_admin_status(partner.tg_id, db)
    await message.answer(Texts.USER_BLOCKED, reply_markup=main_menu_kb(is_admin=my_admin), parse_mode="HTML")
    await bot.send_message(partner.tg_id, Texts.YOU_ARE_BLOCKED, reply_markup=main_menu_kb(is_admin=partner_admin), parse_mode="HTML")


@router.message(Command("stop"))
@router.message(F.text == Texts.STOP_CHAT)
async def stop_chat(message: types.Message, db: AsyncDatabase, db_user: User, bot: Bot):
    session = await repo.get_active_session(db, db_user.id)
    is_admin = await get_admin_status(db_user.tg_id, db)

    if session:
        await repo.end_session(db, session)

        partner = await repo.get_user(db, session.partner_of(db_user.id))

        await message.answer("🏁 The chat has been ended at your request.", reply_markup=main_menu_kb(is_admin=is_admin), parse_mode="HTML")

        partner_is_admin = await get_admin_status(partner.tg_id, db)
        await bot.send_message(partner.tg_id, "🏁 Your chat partner has left the chat.", reply_markup=main_menu_kb(is_admin=partner_is_admin), parse_mode="HTML")
    else:
        # Also check if in queue
        if await repo.leave_queue(db, db_user.id):
            await message.answer("❌ You have left the waiting queue.", reply_markup=main_menu_kb(is_admin=is_admin), parse_mode="HTML")
        else:
            # Force remove keyboard if user thinks they are in chat but aren't
            await message.answer("⚠️ You are not in an active chat.", reply_markup=main_menu_kb(is_admin=is_admin), parse_mode="HTML")


@router.message()
async def process_chat_message(message: types.Message, db: AsyncDatabase, db_user: User, bot: Bot):
    # This handler captures ALL text/media not handled above.
    # It serves as the relay for active matches.
    session = await repo.get_active_session(db, db_user.id)

    if session:
        partner = await repo.get_user(db, session.partner_of(db_user.id))
        try:
            await bot.copy_message(
                chat_id=partner.tg_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
        except Exception:
            # Maybe the partner blocked the bot
            pass
    else:
        # Not in a chat and not a known command: ignore
        pass
