from datetime import datetime, timezone

from pymongo.asynchronous.database import AsyncDatabase

from config import config


def utcnow() -> datetime:
    """Naive UTC timestamp (same convention the old SQLite code used)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def get_admin_status(tg_id: int, db: AsyncDatabase) -> bool:
    if tg_id in config.ADMIN_IDS:
        return True
    return await db.users.count_documents({"tg_id": tg_id, "is_admin": True}, limit=1) > 0
