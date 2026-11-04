from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def gender_pref_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Boy 👦", callback_data="match_pref_male"),
                InlineKeyboardButton(text="Girl 👧", callback_data="match_pref_female"),
            ],
            [
                InlineKeyboardButton(
                    text="Doesn't matter 👫", callback_data="match_pref_any"
                )
            ],
        ]
    )
