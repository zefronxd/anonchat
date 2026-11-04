from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from utils.texts import Texts

def main_menu_kb(is_admin=False):
    kb = [
        [KeyboardButton(text=Texts.MY_LINK), KeyboardButton(text=Texts.REFERRAL_MENU)],
        [KeyboardButton(text=Texts.RANDOM_CHAT)],
        [KeyboardButton(text=Texts.PROFILE), KeyboardButton(text=Texts.HELP)]
    ]
    if is_admin:
        kb.append([KeyboardButton(text=Texts.ADMIN_PANEL)])
    
    return ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True
    )

def gender_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=Texts.GENDER_MALE), KeyboardButton(text=Texts.GENDER_FEMALE)]
        ],
        resize_keyboard=True
    )


def chat_kb():
    """Shown while chatting with a stranger."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=Texts.STOP_CHAT), KeyboardButton(text=Texts.NEXT_CHAT)],
            [KeyboardButton(text=Texts.BLOCK_USER), KeyboardButton(text=Texts.SEND_PROFILE)],
        ],
        resize_keyboard=True
    )

def searching_kb():
    """Shown while waiting in the queue."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=Texts.CANCEL_SEARCH), KeyboardButton(text=Texts.STOP_SEARCH)],
            [KeyboardButton(text=Texts.NEXT_CHAT)],
        ],
        resize_keyboard=True
    )
