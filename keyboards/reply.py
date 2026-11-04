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
