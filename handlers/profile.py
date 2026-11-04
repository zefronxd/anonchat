from aiogram import Router, types, F
from aiogram.filters import Command
from pymongo.asynchronous.database import AsyncDatabase
from database.models import User, Gender
from database import repo
from utils.texts import Texts
from keyboards.reply import gender_kb, main_menu_kb
import html
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from utils.helpers import get_admin_status

router = Router()


class ProfileStates(StatesGroup):
    editing_bio = State()
    editing_nickname = State()
    editing_age = State()


class GenderChangeState(StatesGroup):
    choosing_gender = State()


@router.message(F.text == Texts.PROFILE)
async def view_profile(message: types.Message, db_user: User):
    gender_text = (
        Texts.GENDER_MALE
        if db_user.gender == Gender.MALE
        else Texts.GENDER_FEMALE
        if db_user.gender == Gender.FEMALE
        else "Unknown"
    )
    bio = db_user.bio or "Not set"
    display_name = db_user.nickname or db_user.full_name or "No name"
    age = db_user.age or "Unknown"

    profile_text = (
        f"<b>👤 Your Profile:</b>\n\n"
        f"🏷 <b>Display Name:</b> {html.escape(display_name)}\n"
        f"🎂 <b>Age:</b> {age}\n"
        f"🚻 <b>Gender:</b> {gender_text}\n"
        f"📝 <b>Bio:</b> {html.escape(bio)}\n"
        f"🔑 <b>Link Token:</b> <code>{db_user.link_token}</code>\n\n"
        f"Send /reset_link to change your anonymous link."
    )

    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text=Texts.EDIT_PROFILE)],
            [types.KeyboardButton(text=Texts.REFERRAL_MENU)],
            [types.KeyboardButton(text="Back 🔙")],
        ],
        resize_keyboard=True,
    )
    await message.answer(profile_text, parse_mode="HTML", reply_markup=kb)


@router.message(F.text == Texts.EDIT_PROFILE)
async def edit_profile_menu(message: types.Message):
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(text=Texts.EDIT_NICKNAME),
                types.KeyboardButton(text=Texts.EDIT_AGE),
            ],
            [types.KeyboardButton(text=Texts.CHANGE_GENDER)],
            [types.KeyboardButton(text=Texts.EDIT_BIO)],
            [types.KeyboardButton(text=Texts.BLOCK_LIST)],
            [types.KeyboardButton(text="Back 🔙")],
        ],
        resize_keyboard=True,
    )
    await message.answer("🛠 What would you like to edit?", reply_markup=kb)


@router.message(F.text == Texts.EDIT_AGE)
async def start_edit_age(message: types.Message, state: FSMContext):
    await message.answer(Texts.ENTER_AGE)
    await state.set_state(ProfileStates.editing_age)


@router.message(ProfileStates.editing_age)
async def process_edit_age(
    message: types.Message, db: AsyncDatabase, state: FSMContext, db_user: User
):
    if not message.text.isdigit():
        await message.answer("❌ Please enter numbers only.")
        return

    age = int(message.text)
    if age < 10 or age > 99:
        await message.answer("❌ Age must be between 10 and 99.")
        return

    await repo.update_user(db, db_user, age=age)

    await state.clear()
    await message.answer(Texts.AGE_UPDATED)
    await view_profile(message, db_user)


@router.message(F.text == Texts.EDIT_NICKNAME)
async def start_edit_nickname(message: types.Message, state: FSMContext):
    await message.answer(Texts.ENTER_NICKNAME)
    await state.set_state(ProfileStates.editing_nickname)


@router.message(ProfileStates.editing_nickname)
async def process_edit_nickname(
    message: types.Message, db: AsyncDatabase, state: FSMContext, db_user: User
):
    # Validation: check length
    if len(message.text) > 32:
        await message.answer("❌ Nickname is too long (maximum 32 characters).")
        return

    # Validation: only allow alphanumeric and spaces
    if not all(c.isalnum() or c.isspace() for c in message.text):
        await message.answer(
            "❌ Nickname can only contain letters, numbers, and spaces."
        )
        return

    await repo.update_user(db, db_user, nickname=message.text.strip())

    await state.clear()
    await message.answer(Texts.NICKNAME_UPDATED)
    await view_profile(message, db_user)


@router.message(F.text == Texts.CHANGE_GENDER)
@router.message(Command("gender"))
async def change_gender_cmd(message: types.Message, state: FSMContext):
    await message.answer(Texts.CHOOSE_GENDER, reply_markup=gender_kb())
    await state.set_state(GenderChangeState.choosing_gender)


@router.message(GenderChangeState.choosing_gender)
async def process_gender_change(
    message: types.Message, db: AsyncDatabase, state: FSMContext, db_user: User
):
    # Only accept gender buttons
    if message.text == Texts.GENDER_MALE:
        new_gender = Gender.MALE
    elif message.text == Texts.GENDER_FEMALE:
        new_gender = Gender.FEMALE
    else:
        await message.answer(
            "❌ Please choose either Male or Female from the keyboard."
        )
        return

    await repo.update_user(db, db_user, gender=new_gender)

    await state.clear()
    gender_text = (
        Texts.GENDER_MALE if new_gender == Gender.MALE else Texts.GENDER_FEMALE
    )
    await message.answer(f"✅ Your gender has been changed to {gender_text}.")
    await view_profile(message, db_user)


@router.message(F.text == Texts.EDIT_BIO)
async def start_edit_bio(message: types.Message, state: FSMContext):
    await message.answer(Texts.ENTER_BIO)
    await state.set_state(ProfileStates.editing_bio)


@router.message(ProfileStates.editing_bio)
async def process_edit_bio(
    message: types.Message, db: AsyncDatabase, state: FSMContext, db_user: User
):
    if len(message.text) > 100:
        await message.answer("❌ Bio is too long (maximum 100 characters).")
        return

    await repo.update_user(db, db_user, bio=message.text)

    await state.clear()
    await message.answer(Texts.BIO_UPDATED)
    await view_profile(message, db_user)


@router.message(Command("reset_link"))
async def reset_link(message: types.Message, db: AsyncDatabase, db_user: User):
    await repo.update_user(db, db_user, link_token=repo.new_link_token())

    await message.answer("✅ Your anonymous link has been reset successfully!")


@router.message(F.text == Texts.BLOCK_LIST)
async def view_block_list(message: types.Message, db: AsyncDatabase, db_user: User):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    blocked_users = await repo.list_blocked_users(db, db_user.id)

    if not blocked_users:
        await message.answer(Texts.NO_BLOCKS)
        return

    for u in blocked_users:
        name = html.escape(u.nickname or u.display_id or f"User {u.id}")
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Unblock 🔓", callback_data=f"unblock_{u.id}"
                    )
                ]
            ]
        )
        await message.answer(f"🚫 <b>{name}</b>", reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("unblock_"))
async def unblock_user_callback(
    callback: types.CallbackQuery, db: AsyncDatabase, db_user: User
):
    blocked_id = repo.parse_oid(callback.data.split("_", 1)[1])
    removed = await repo.remove_block(db, db_user.id, blocked_id) if blocked_id else False

    if removed:
        await callback.message.edit_text(
            callback.message.text + "\n✅ Unblocked.", reply_markup=None
        )
        await callback.answer("User has been unblocked.")
    else:
        await callback.answer("This user is not in your block list.", show_alert=True)


@router.message(F.text == "Back 🔙")
async def back_to_main_from_profile(
    message: types.Message, db: AsyncDatabase, state: FSMContext
):
    await state.clear()
    is_admin = await get_admin_status(message.from_user.id, db)
    await message.answer(
        Texts.MAIN_MENU, reply_markup=main_menu_kb(is_admin=is_admin), parse_mode="HTML"
    )


@router.message(F.text == Texts.HELP)
async def help_cmd(message: types.Message):
    help_text = (
        "<b>📚 Bot Guide:</b>\n\n"
        "🔗 <b>My Anonymous Link:</b> Get a link you can put in your Instagram bio or channel.\n\n"
        "🎲 <b>Random Chat:</b> Get connected to a random anonymous person.\n\n"
        "🚫 <b>Blocked Users:</b> Manage the people you have blocked.\n\n"
        "👤 <b>My Profile:</b> View and edit your account information."
    )
    await message.answer(help_text, parse_mode="HTML")
