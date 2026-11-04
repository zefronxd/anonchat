from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser
from typing import Callable, Dict, Any, Awaitable
import logging

from database import repo


class UserRegistrationMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        tg_user: TgUser = data.get("event_from_user")
        if not tg_user:
            return await handler(event, data)

        db = data.get("db")
        if db is None:
            return await handler(event, data)

        try:
            user = await repo.get_or_create_user(db, tg_user)
        except Exception as e:
            logging.error(f"Error during user registration: {e}")
            user = None

        if not user:
            logging.error(f"Failed to register user {tg_user.id}.")

        # Inject user into data for handlers to use
        data["db_user"] = user

        return await handler(event, data)
