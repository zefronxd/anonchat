from aiogram import Router, types, F, Bot
from aiogram.filters import CommandStart, Command
from pymongo.asynchronous.database import AsyncDatabase
from database.models import User, Gender
from database import repo
from utils.texts import Texts
from utils.helpers import get_admin_status
from keyboards.reply import main_menu_kb, gender_kb, chat_kb, link_chat_kb
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from handlers.relay import RelayStates
import html
import logging

router = Router()


class Registration(StatesGroup):
    choosing_gender = State()


@router.message(CommandStart())
async def cmd_start(
    message: types.Message, db: AsyncDatabase, state: FSMContext, db_user: User
):
    args = message.text.split()
    if len(args) > 1:
        token = args[1]

        # ───────── REFERRAL link: t.me/bot?start=ref_<token> ─────────
        if token.startswith("ref_"):
            referrer = await repo.get_user_by_ref_token(db, token[4:])
            # Only count brand-new users (those who haven't finished registration yet)
            if (
                referrer
                and referrer.id != db_user.id
                and not db_user.referred_by_id
                and db_user.gender == Gender.UNKNOWN
            ):
                await repo.update_user(
                    db, db_user, referred_by_id=referrer.id, referral_confirmed=False
                )
                logging.info(
                    f"Referral tracked: {db_user.tg_id} referred by {referrer.tg_id}"
                )
            # ...then continue with the normal welcome / gender flow below

        # ───────── ANONYMOUS MESSAGE link: t.me/bot?start=<token> ─────────
        else:
            target = await repo.get_user_by_link_token(db, token)

            if target:
                if target.tg_id == message.from_user.id:
                    await message.answer(
                        "⚠️ You can't send an anonymous message to yourself! 😅",
                        parse_mode="HTML",
                    )
                else:
                    target_name = html.escape(
                        target.nickname or target.full_name or "Someone"
                    )
                    # ObjectId is stored as a string in FSM (memory storage / JSON-safe)
                    await state.update_data(target_id=str(target.id))

                    await message.answer(
                        f"✍️ Sending an anonymous message to <b>{target_name}</b>...\n"
                        f"Write whatever you want (text, photo, voice, etc.).\n"
                        f"Replies will arrive here as normal messages.",
                        parse_mode="HTML",
                        reply_markup=link_chat_kb(),
                    )
                    await state.set_state(RelayStates.relay_flow)
                    return

    # If they are returning without a link
    if db_user.gender == Gender.UNKNOWN:
        await message.answer(f"👋 {Texts.START_WELCOME}", parse_mode="HTML")
        await message.answer(
            Texts.CHOOSE_GENDER, reply_markup=gender_kb(), parse_mode="HTML"
        )
        await state.set_state(Registration.choosing_gender)
    else:
        # IMPORTANT: Check if user is in active chat session
        active_session = await repo.get_active_session(db, db_user.id)

        if active_session:
            # User is in active chat - preserve chat keyboard
            await message.answer(
                "💬 You are currently in a chat. Use the buttons below.",
                reply_markup=chat_kb(),
                parse_mode="HTML",
            )
        else:
            # Normal flow - show main menu
            is_admin = await get_admin_status(message.from_user.id, db)
            await message.answer(
                f"🏠 {Texts.MAIN_MENU}",
                reply_markup=main_menu_kb(is_admin=is_admin),
                parse_mode="HTML",
            )


@router.message(Registration.choosing_gender)
async def process_gender(
    message: types.Message,
    db: AsyncDatabase,
    state: FSMContext,
    db_user: User,
    bot: Bot,
):
    if message.text == Texts.GENDER_MALE:
        gender = Gender.MALE
    elif message.text == Texts.GENDER_FEMALE:
        gender = Gender.FEMALE
    else:
        await message.answer(
            "❌ Please choose one of the options from the keyboard.", parse_mode="HTML"
        )
        return

    await repo.update_user(db, db_user, gender=gender)

    # Registration finished -> confirm the referral (counts for the referrer now)
    if db_user.referred_by_id and not db_user.referral_confirmed:
        await repo.update_user(db, db_user, referral_confirmed=True)
        try:
            referrer = await repo.get_user(db, db_user.referred_by_id)
            if referrer:
                total = await repo.count_confirmed_referrals(db, referrer.id)
                await bot.send_message(
                    referrer.tg_id,
                    f"🎉 Someone joined using your referral link!\n👤 Total referrals: <b>{total}</b>",
                    parse_mode="HTML",
                )
        except Exception as e:
            logging.warning(f"Could not notify referrer: {e}")

    await state.clear()
    is_admin = await get_admin_status(message.from_user.id, db)
    await message.answer(
        "✅ Your gender has been saved!",
        reply_markup=main_menu_kb(is_admin=is_admin),
        parse_mode="HTML",
    )
