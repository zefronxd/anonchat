from aiogram import Router, types, F, Bot
from pymongo.asynchronous.database import AsyncDatabase
from database.models import User
from database import repo
from utils.texts import Texts
from utils.helpers import get_admin_status
from keyboards.reply import main_menu_kb, link_chat_kb, EXIT_LINK_CHAT
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from urllib.parse import quote
import hashlib
import time


class RelayStates(StatesGroup):
    relay_flow = State()   # visitor who opened someone's anonymous link
    reply_flow = State()   # link owner who pressed "Reply"


router = Router()

INTRO_TEXT = (
    "✅ Sent anonymously!\n"
    "You can keep chatting here — just send messages, replies will arrive as normal messages.\n"
    "Press <b>Exit Chat 🚪</b> when you want to leave."
)


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


async def _in_mutual_chat(bot: Bot, storage, target_tg_id: int, my_id) -> bool:
    """True if the other person is *currently* chatting with me in link-chat mode.
    In that case messages are delivered as plain, normal messages (no header, no buttons)."""
    try:
        key = StorageKey(bot_id=bot.id, chat_id=target_tg_id, user_id=target_tg_id)
        st = await storage.get_state(key)
        if st not in (RelayStates.relay_flow.state, RelayStates.reply_flow.state):
            return False
        data = await storage.get_data(key)
        return data.get("target_id") == str(my_id)
    except Exception:
        return False


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


# NOTE: the exit handler must be registered BEFORE the state handler below,
# otherwise the "Exit Chat" button text would be relayed as a message.
@router.message(F.text.in_({"Cancel ❌", EXIT_LINK_CHAT}))
async def exit_link_chat(message: types.Message, state: FSMContext, db: AsyncDatabase):
    current_state = await state.get_state()
    if current_state not in (RelayStates.relay_flow.state, RelayStates.reply_flow.state):
        return

    await state.clear()
    is_admin = await get_admin_status(message.from_user.id, db)
    await message.answer(
        "✅ You left the chat.",
        reply_markup=main_menu_kb(is_admin=is_admin),
        parse_mode="HTML",
    )


@router.message(RelayStates.relay_flow)
@router.message(RelayStates.reply_flow)
async def process_link_message(
    message: types.Message, db: AsyncDatabase, state: FSMContext, bot: Bot, db_user: User
):
    data = await state.get_data()
    current_state = await state.get_state()
    target_oid = repo.parse_oid(data.get("target_id"))
    target = await repo.get_user(db, target_oid) if target_oid else None

    if not target:
        await state.clear()
        is_admin = await get_admin_status(message.from_user.id, db)
        await message.answer(
            "❌ Recipient not found.", reply_markup=main_menu_kb(is_admin=is_admin)
        )
        return

    is_visitor = current_state == RelayStates.relay_flow.state
    mutual = await _in_mutual_chat(bot, state.storage, target.tg_id, db_user.id)

    delivered = True
    try:
        if mutual:
            # Both sides are in the chat -> deliver as a normal message
            await bot.copy_message(
                chat_id=target.tg_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
        else:
            if is_visitor:
                # Anonymous ID (changes every 3 days)
                period_salt = int(time.time() / (86400 * 3))
                raw_id = f"{db_user.id}:{target.id}:{period_salt}"
                anon_id = int(hashlib.md5(raw_id.encode()).hexdigest(), 16) % 1000000
                header = f"🔔 <b>New anonymous message!</b>\n👤 Sender: <code>#{anon_id}</code>"
            else:
                header = "💬 <b>New reply from the anonymous user:</b>"

            await bot.send_message(target.tg_id, header, parse_mode="HTML")
            await bot.copy_message(
                chat_id=target.tg_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                reply_markup=get_relay_kb(db_user.id),
            )
    except Exception:
        delivered = False
        await message.answer(
            "⚠️ Message could not be sent. The recipient may have blocked the bot."
        )

    if delivered:
        await repo.log_message(
            db,
            sender_id=db_user.id,
            receiver_id=target.id,
            content_type=message.content_type,
            content=message.text or message.caption or f"[{message.content_type}]",
            context="link" if is_visitor else "reply",
        )
        # Show the short intro only once; after that it behaves like a normal chat
        if not data.get("intro_shown"):
            await state.update_data(intro_shown=True)
            await message.answer(INTRO_TEXT, reply_markup=link_chat_kb(), parse_mode="HTML")


@router.callback_query(F.data.startswith("reply_"))
async def start_reply(
    callback: types.CallbackQuery, state: FSMContext, db: AsyncDatabase, db_user: User
):
    target_id = callback.data.split("_", 1)[1]
    if not repo.parse_oid(target_id):
        await callback.answer("❌ Invalid recipient.", show_alert=True)
        return

    if await repo.get_active_session(db, db_user.id):
        await callback.answer(
            "⚠️ Finish your random chat first (End Chat 🏁).", show_alert=True
        )
        return

    await state.set_state(RelayStates.reply_flow)
    await state.set_data({"target_id": target_id, "intro_shown": True})
    await callback.message.answer(
        "✍️ You are now chatting anonymously.\n"
        "Just send your messages here. Press <b>Exit Chat 🚪</b> to leave.",
        reply_markup=link_chat_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "close_relay")
async def close_relay_msg(
    callback: types.CallbackQuery, state: FSMContext, db: AsyncDatabase
):
    await state.clear()
    await callback.message.edit_reply_markup(reply_markup=None)
    is_admin = await get_admin_status(callback.from_user.id, db)
    await callback.message.answer(
        "❌ Chat closed.", reply_markup=main_menu_kb(is_admin=is_admin)
    )
    await callback.answer()
