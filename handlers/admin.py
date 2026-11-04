from aiogram import Router, types, F, Bot
import asyncio
import html
import io
from aiogram.filters import Command
from pymongo.asynchronous.database import AsyncDatabase
from database import repo
from config import config
from utils.texts import Texts
from utils.helpers import get_admin_status
from keyboards.reply import main_menu_kb
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile

router = Router()


class AdminStates(StatesGroup):
    broadcasting = State()
    adding_admin = State()
    setting_channel = State()
    searching_logs = State()


@router.message(F.text == Texts.ADMIN_PANEL)
@router.message(Command("admin"))
async def admin_panel(message: types.Message, db: AsyncDatabase):
    if not await get_admin_status(message.from_user.id, db):
        return

    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=Texts.STATS), types.KeyboardButton(text=Texts.BROADCAST)],
            [types.KeyboardButton(text=Texts.ADD_ADMIN), types.KeyboardButton(text=Texts.SET_CHANNEL)],
            [types.KeyboardButton(text=Texts.SEARCH_LOGS), types.KeyboardButton(text=Texts.EXPORT_USERS)],
            [types.KeyboardButton(text=Texts.REFERRAL_MENU), types.KeyboardButton(text="Back 🔙")]
        ],
        resize_keyboard=True
    )
    await message.answer("Welcome, sir. Admin panel activated.", reply_markup=kb)


@router.message(F.text == Texts.SET_CHANNEL)
async def start_set_channel(message: types.Message, db: AsyncDatabase, state: FSMContext):
    if not await get_admin_status(message.from_user.id, db):
        return
    await message.answer(Texts.ENTER_CHANNEL_ID)
    await state.set_state(AdminStates.setting_channel)


@router.message(AdminStates.setting_channel)
async def process_set_channel(message: types.Message, db: AsyncDatabase, state: FSMContext):
    if not await get_admin_status(message.from_user.id, db):
        return

    channel_id = message.text.strip()
    await repo.set_setting(db, "required_channel_id", channel_id)
    await message.answer(Texts.CHANNEL_UPDATED)
    await state.clear()
    await admin_panel(message, db)


@router.message(F.text == Texts.SEARCH_LOGS)
async def start_search_logs(message: types.Message, db: AsyncDatabase, state: FSMContext):
    if not await get_admin_status(message.from_user.id, db):
        return
    await message.answer(Texts.ENTER_USER_ID)
    await state.set_state(AdminStates.searching_logs)


@router.message(AdminStates.searching_logs)
async def process_search_logs(message: types.Message, db: AsyncDatabase, state: FSMContext):
    if not await get_admin_status(message.from_user.id, db):
        return

    input_data = message.text.strip()
    target_user = None

    try:
        if input_data.isdigit():
            target_user = await repo.get_user_by_tg_id(db, int(input_data))
        else:
            username = input_data.replace("@", "").strip()
            target_user = await repo.get_user_by_username(db, username)

        if not target_user:
            await message.answer(f"❌ {Texts.USER_NOT_FOUND}", parse_mode="HTML")
            await state.clear()
            await admin_panel(message, db)
            return

        # Find logs as sender or receiver
        logs = await repo.recent_logs_for(db, target_user.id, limit=50)

        if not logs:
            await message.answer("⚠️ No messages found.", parse_mode="HTML")
        else:
            log_header = Texts.USER_LOGS_HEADER.format(user_id=target_user.tg_id)
            log_text = f"<b>🔍 {html.escape(log_header)}</b>\n\n"
            for log in logs:
                direction = "📤 Sent" if log.sender_id == target_user.id else "📥 Received"
                content = html.escape(str(log.content)[:50]) if log.content else "---"
                log_text += f"{direction} (<code>{log.created_at.strftime('%H:%M')}</code>): {content}...\n"

            await message.answer(log_text, parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ Unexpected error: {html.escape(str(e))}", parse_mode="HTML")
    finally:
        await state.clear()
        await admin_panel(message, db)


@router.message(F.text == Texts.EXPORT_USERS)
async def export_users_list(message: types.Message, db: AsyncDatabase):
    if not await get_admin_status(message.from_user.id, db):
        return

    users = await repo.list_users(db)

    output = io.StringIO()
    output.write("ID | Username | Full Name | Nickname | Gender\n")
    output.write("-" * 60 + "\n")

    for u in users:
        username = f"@{u.username}" if u.username else "N/A"
        nickname = u.nickname or "N/A"
        output.write(f"{u.tg_id} | {username} | {u.full_name} | {nickname} | {u.gender.value}\n")

    file_content = output.getvalue().encode("utf-8")
    file = BufferedInputFile(file_content, filename="users_list.txt")

    await message.answer_document(file, caption="List of all bot users 👥")


@router.message(F.text == Texts.ADD_ADMIN)
async def start_add_admin(message: types.Message, db: AsyncDatabase, state: FSMContext):
    if not await get_admin_status(message.from_user.id, db):
        return
    await message.answer(Texts.ENTER_ADMIN_USERNAME, parse_mode="HTML")
    await state.set_state(AdminStates.adding_admin)


@router.message(AdminStates.adding_admin)
async def process_adding_admin(message: types.Message, db: AsyncDatabase, state: FSMContext):
    if not await get_admin_status(message.from_user.id, db):
        return

    input_data = message.text.strip()
    target_user = None

    try:
        if input_data.isdigit():
            target_user = await repo.get_user_by_tg_id(db, int(input_data))
        else:
            username = input_data.replace("@", "")
            target_user = await repo.get_user_by_username(db, username)

        if not target_user:
            await message.answer(
                f"❌ <b>User not found.</b>\n\n"
                f"Tip: The user must have pressed /start in the bot at least once to be registered.",
                parse_mode="HTML"
            )
        else:
            await repo.update_user(db, target_user, is_admin=True)
            name = html.escape(target_user.nickname or target_user.full_name or "User")
            await message.answer(f"✅ <b>{name}</b> has been successfully added to the admin list.", parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ An error occurred: {html.escape(str(e))}", parse_mode="HTML")
    finally:
        await state.clear()
        await admin_panel(message, db)


@router.message(F.text == Texts.STATS)
async def view_stats(message: types.Message, db: AsyncDatabase):
    if not await get_admin_status(message.from_user.id, db):
        return

    total_users = await repo.count_users(db)
    active_matches = await repo.count_active_sessions(db)
    total_logs = await repo.count_logs(db)

    stats_text = (
        f"📊 <b>Bot Statistics:</b>\n\n"
        f"👥 <b>Total Users:</b> <code>{total_users}</code>\n"
        f"💬 <b>Active Chats:</b> <code>{active_matches}</code>\n"
        f"✉️ <b>Total Messages Exchanged:</b> <code>{total_logs}</code>"
    )
    await message.answer(stats_text, parse_mode="HTML")


@router.message(F.text == Texts.BROADCAST)
async def start_broadcast(message: types.Message, state: FSMContext, db: AsyncDatabase):
    if not await get_admin_status(message.from_user.id, db):
        return

    await message.answer(Texts.ENTER_BROADCAST_MSG, parse_mode="HTML")
    await state.set_state(AdminStates.broadcasting)


@router.message(AdminStates.broadcasting)
async def process_broadcast(message: types.Message, db: AsyncDatabase, bot: Bot, state: FSMContext):
    if not await get_admin_status(message.from_user.id, db):
        return

    user_ids = await repo.list_user_tg_ids(db)

    sent = 0
    failed = 0
    msg = await message.answer(f"⏳ <b>Sending to {len(user_ids)} users...</b>", parse_mode="HTML")

    try:
        for uid in user_ids:
            try:
                await bot.copy_message(chat_id=uid, from_chat_id=message.chat.id, message_id=message.message_id)
                sent += 1
            except Exception:
                failed += 1
            if (sent + failed) % 20 == 0:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=msg.message_id,
                    text=f"⏳ <b>Sending...</b>\n✅ Success: {sent}\n❌ Failed: {failed}",
                    parse_mode="HTML"
                )
            await asyncio.sleep(0.05)

        await message.answer(f"📢 <b>Broadcast finished:</b>\n✅ Success: {sent}\n❌ Failed: {failed}", parse_mode="HTML")
    finally:
        await state.clear()


@router.message(F.text == "Back 🔙")
async def back_to_main(message: types.Message, db: AsyncDatabase):
    is_admin = await get_admin_status(message.from_user.id, db)
    await message.answer(Texts.MAIN_MENU, reply_markup=main_menu_kb(is_admin=is_admin), parse_mode="HTML")