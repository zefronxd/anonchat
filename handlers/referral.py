from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo.asynchronous.database import AsyncDatabase
from database.models import User
from database import repo
from utils.texts import Texts
from urllib.parse import quote

router = Router()


@router.message(F.text == Texts.REFERRAL_MENU)
async def view_referrals(
    message: types.Message, db: AsyncDatabase, db_user: User, bot: Bot, state: FSMContext
):
    # Clear any previous state
    await state.clear()

    # Count referrals (Strict: only confirmed)
    referral_count = await repo.count_confirmed_referrals(db, db_user.id)

    # Calculate rewards: 30 referrals = 1 hour bonus
    # Determine if eligible for reward
    has_reward = referral_count >= 30

    bot_info = await bot.get_me()

    if not db_user.link_token:
        await repo.update_user(db, db_user, link_token=repo.new_link_token())

    referral_link = f"https://t.me/{bot_info.username}?start={db_user.link_token}"

    # Format text
    text = Texts.REFERRAL_INFO.format(link=referral_link, count=referral_count)

    # Build keyboard
    buttons = []
    # Share button with proper URL encoding
    share_text = quote("Send me an anonymous message! 👇")
    share_url = f"https://t.me/share/url?url={quote(referral_link)}&text={share_text}"
    buttons.append([InlineKeyboardButton(text="Share 📤", url=share_url)])

    if has_reward:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=Texts.CLAIM_REWARD, callback_data="claim_reward"
                )
            ]
        )

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data == "claim_reward")
async def process_claim_reward(
    callback: types.CallbackQuery, db: AsyncDatabase, db_user: User
):
    """
    Handle claim reward button click.
    Checks strict referral count.
    """
    # Double check eligibility
    referral_count = await repo.count_confirmed_referrals(db, db_user.id)

    if referral_count >= 30:
        await callback.message.answer(Texts.CLAIM_REWARD_MSG, parse_mode="HTML")
        await callback.answer()
    else:
        await callback.answer(
            "❌ You haven't reached the required number yet.", show_alert=True
        )
