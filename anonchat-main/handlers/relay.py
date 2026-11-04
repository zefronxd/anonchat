from aiogram import Router, types, F, Bot
from pymongo.asynchronous.database import AsyncDatabase
from database.models import User
from database import repo
from utils.texts import Texts
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from urllib.parse import quote
import hashlib
import time


class RelayStates(StatesGroup):
    relay_flow = State()
    reply_flow = State()


router = Router()


def get_relay_kb(sender_internal_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=Texts.REPLY, callback_data=f"reply_{sender_internal_id}"
                ),
                InlineKeyboardButton(
                    text=Texts.CLOSE_RELAY, callback_data="close_relay"
                ),
            ]
        ]
    )


@router.message(F.text == Texts.MY_LINK)
async def get_my_link(
    message: types.Message, db_user: User, db: AsyncDatabase, bot: Bot
):
    if not db_user.link_token:
        await repo.update_user(db, db_user, link_token=repo.new_link_token())

    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={db_user.link_token}"

    # Proper URL encoding for share text
    share_text = quote("Got something on your mind? Tell me anonymously! 👇")
    share_url = f"https://t.me/share/url?url={quote(link)}&text={share_text}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Share 📤", url=share_url)]]
    )

    await message.answer(f"🔗 {Texts.YOUR_LINK.format(link=link)}", reply_markup=kb)


@router.message(RelayStates.relay_flow)
async def process_relay(
    message: types.Message, db: AsyncDatabase, state: FSMContext, bot: Bot, db_user: User
):
    data = await state.get_data()
    target_oid = repo.parse_oid(data.get("target_id"))
    target = await repo.get_user(db, target_oid) if target_oid else None

    if not target:
        await message.answer("❌ An error occurred. Recipient not found.")
        await state.clear()
        return

    # Generate Anonymous ID (changes every 3 days)
    period_salt = int(time.time() / (86400 * 3))  # 3 days window
    # Simple consistent hash
    raw_id = f"{db_user.id}:{target.id}:{period_salt}"
    hash_obj = hashlib.md5(raw_id.encode())
    # Take last 6 digits of the int value
    anon_id = int(hash_obj.hexdigest(), 16) % 1000000

    # Relay message
    try:
        await bot.send_message(
            target.tg_id,
            f"🔔 <b>New anonymous message!</b>\n👤 Sender: <code>#{anon_id}</code>",
            parse_mode="HTML",
        )
        await bot.copy_message(
            chat_id=target.tg_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=get_relay_kb(db_user.id),
        )
        await message.answer("✅ Your message was sent anonymously!")
    except Exception:
        await message.answer(
            "⚠️ Message could not be sent. The recipient may have blocked the bot."
        )

    # Log message
    await repo.log_message(
        db,
        sender_id=db_user.id,
        receiver_id=target.id,
        content_type=message.content_type,
        content=message.text or message.caption or f"[{message.content_type}]",
        context="link",
    )

    await state.clear()


@router.callback_query(F.data.startswith("reply_"))
async def start_reply(callback: types.CallbackQuery, state: FSMContext):
    target_id = callback.data.split("_", 1)[1]
    if not repo.parse_oid(target_id):
        await callback.answer("❌ Invalid recipient.", show_alert=True)
        return
    await state.update_data(target_id=target_id)
    await state.set_state(RelayStates.reply_flow)
    await callback.message.answer(f"✍️ {Texts.REPLY_PROMPT}")
    await callback.answer()


@router.callback_query(F.data == "close_relay")
async def close_relay_msg(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("❌ Chat closed.")
    await callback.answer()


@router.message(RelayStates.reply_flow)
async def process_reply(
    message: types.Message, db: AsyncDatabase, state: FSMContext, bot: Bot, db_user: User
):
    data = await state.get_data()
    target_oid = repo.parse_oid(data.get("target_id"))
    target = await repo.get_user(db, target_oid) if target_oid else None

    if not target:
        await message.answer("❌ Sorry, the recipient is no longer available.")
        await state.clear()
        return

    try:
        await bot.send_message(
            target.tg_id,
            "💬 <b>New reply from the anonymous user:</b>",
            parse_mode="HTML",
        )
        await bot.copy_message(
            chat_id=target.tg_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
            reply_markup=get_relay_kb(db_user.id),  # Link owners can keep replying
        )
        await message.answer("✅ Your reply was sent successfully.")
    except Exception:
        await message.answer("⚠️ Reply could not be sent.")

    await repo.log_message(
        db,
        sender_id=db_user.id,
        receiver_id=target.id,
        content_type=message.content_type,
        content=message.text or message.caption or f"[{message.content_type}]",
        context="reply",
    )
    await state.clear()


@router.message(F.text == "Cancel ❌")
async def cancel_relay(message: types.Message, state: FSMContext, db: AsyncDatabase):
    """Handle cancel button during relay flow"""
    current_state = await state.get_state()

    # Only handle if in relay or reply flow
    if current_state in [RelayStates.relay_flow, RelayStates.reply_flow]:
        await state.clear()

        from keyboards.reply import main_menu_kb
        from utils.helpers import get_admin_status

        is_admin = await get_admin_status(message.from_user.id, db)
        await message.answer(
            "❌ Message sending cancelled.",
            reply_markup=main_menu_kb(is_admin=is_admin),
            parse_mode="HTML",
        )
