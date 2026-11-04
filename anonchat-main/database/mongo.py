import logging

from pymongo import ASCENDING, AsyncMongoClient

from config import config

client: AsyncMongoClient = AsyncMongoClient(config.MONGO_URI)
database = client[config.MONGO_DB]


async def init_db() -> None:
    """Create all indexes (safe to call on every start)."""
    db = database

    # users
    await db.users.create_index("tg_id", unique=True)
    await db.users.create_index("link_token", unique=True)
    await db.users.create_index(
        "display_id", unique=True, partialFilterExpression={"display_id": {"$type": "string"}}
    )
    await db.users.create_index("username")
    await db.users.create_index([("referred_by_id", ASCENDING), ("referral_confirmed", ASCENDING)])

    # blocks
    await db.blocks.create_index([("blocker_id", ASCENDING), ("blocked_id", ASCENDING)], unique=True)
    await db.blocks.create_index("blocked_id")

    # match queue / sessions
    await db.match_queue.create_index("user_id", unique=True)
    await db.match_queue.create_index("created_at")
    await db.match_sessions.create_index([("user1_id", ASCENDING), ("is_active", ASCENDING)])
    await db.match_sessions.create_index([("user2_id", ASCENDING), ("is_active", ASCENDING)])

    # message logs
    await db.message_logs.create_index([("sender_id", ASCENDING), ("created_at", -1)])
    await db.message_logs.create_index([("receiver_id", ASCENDING), ("created_at", -1)])

    logging.info("MongoDB indexes ready.")


async def close_db() -> None:
    await client.close()
