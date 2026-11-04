from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any, Awaitable


class DbSessionMiddleware(BaseMiddleware):
    """Injects the MongoDB database object into every handler as `db`."""

    def __init__(self, database):
        super().__init__()
        self.database = database

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        data["db"] = self.database
        return await handler(event, data)
