"""All MongoDB reads/writes live here so handlers stay free of query code."""
import random
import uuid
from datetime import datetime
from typing import Iterable, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from database.models import Gender, MatchSession, MessageLog, User
from utils.helpers import utcnow


def new_link_token() -> str:
    return str(uuid.uuid4())[:8]


def parse_oid(value: str) -> Optional[ObjectId]:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


# ───────────────────────── users ─────────────────────────

async def get_user(db: AsyncDatabase, user_id: ObjectId) -> Optional[User]:
    return User.from_doc(await db.users.find_one({"_id": user_id}))


async def get_user_by_tg_id(db: AsyncDatabase, tg_id: int) -> Optional[User]:
    return User.from_doc(await db.users.find_one({"tg_id": tg_id}))


async def get_user_by_link_token(db: AsyncDatabase, token: str) -> Optional[User]:
    return User.from_doc(await db.users.find_one({"link_token": token}))


async def get_user_by_ref_token(db: AsyncDatabase, token: str) -> Optional[User]:
    return User.from_doc(await db.users.find_one({"ref_token": token}))


async def get_user_by_username(db: AsyncDatabase, username: str) -> Optional[User]:
    return User.from_doc(await db.users.find_one({"username": username}))


async def get_or_create_user(db: AsyncDatabase, tg_user) -> Optional[User]:
    """Atomic fetch-or-create (no race when two updates arrive at once)."""
    existing = await get_user_by_tg_id(db, tg_user.id)
    if existing:
        return existing

    for _ in range(5):
        defaults = {
            "username": tg_user.username,
            "full_name": tg_user.full_name,
            "nickname": None,
            "bio": None,
            "gender": Gender.UNKNOWN.value,
            "link_token": new_link_token(),
            "is_admin": False,
            "is_blocked": False,
            "display_id": f"U{random.randint(10000, 99999)}",
            "age": None,
            "referred_by_id": None,
            "referral_confirmed": False,
            "referral_bonus_until": None,
            "created_at": utcnow(),
        }
        try:
            doc = await db.users.find_one_and_update(
                {"tg_id": tg_user.id},
                {"$setOnInsert": defaults},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            return User.from_doc(doc)
        except DuplicateKeyError:
            # Either a parallel update created this user, or display_id/link_token collided.
            existing = await get_user_by_tg_id(db, tg_user.id)
            if existing:
                return existing
    return None


async def update_user(db: AsyncDatabase, user: User, **fields) -> None:
    """$set the given fields in Mongo and mirror them on the in-memory object."""
    doc = {k: (v.value if isinstance(v, Gender) else v) for k, v in fields.items()}
    await db.users.update_one({"_id": user.id}, {"$set": doc})
    for k, v in fields.items():
        setattr(user, k, v)


async def count_users(db: AsyncDatabase) -> int:
    return await db.users.count_documents({})


async def list_users(db: AsyncDatabase) -> List[User]:
    return [User.from_doc(d) async for d in db.users.find({})]


async def list_user_tg_ids(db: AsyncDatabase) -> List[int]:
    return [d["tg_id"] async for d in db.users.find({}, {"tg_id": 1})]


async def count_confirmed_referrals(db: AsyncDatabase, user_id: ObjectId) -> int:
    return await db.users.count_documents(
        {"referred_by_id": user_id, "referral_confirmed": True}
    )


# ───────────────────────── blocks ─────────────────────────

async def add_block(db: AsyncDatabase, blocker_id: ObjectId, blocked_id: ObjectId) -> None:
    await db.blocks.update_one(
        {"blocker_id": blocker_id, "blocked_id": blocked_id},
        {"$setOnInsert": {"created_at": utcnow()}},
        upsert=True,
    )


async def remove_block(db: AsyncDatabase, blocker_id: ObjectId, blocked_id: ObjectId) -> bool:
    res = await db.blocks.delete_one({"blocker_id": blocker_id, "blocked_id": blocked_id})
    return res.deleted_count > 0


async def list_blocked_users(db: AsyncDatabase, blocker_id: ObjectId) -> List[User]:
    ids = [d["blocked_id"] async for d in db.blocks.find({"blocker_id": blocker_id})]
    if not ids:
        return []
    return [User.from_doc(d) async for d in db.users.find({"_id": {"$in": ids}})]


async def blocked_either_way(db: AsyncDatabase, user_id: ObjectId) -> set:
    """IDs of users I blocked + users who blocked me."""
    out = set()
    async for d in db.blocks.find({"$or": [{"blocker_id": user_id}, {"blocked_id": user_id}]}):
        out.add(d["blocked_id"] if d["blocker_id"] == user_id else d["blocker_id"])
    return out


# ───────────────────────── match queue / sessions ─────────────────────────

async def get_active_session(db: AsyncDatabase, user_id: ObjectId) -> Optional[MatchSession]:
    doc = await db.match_sessions.find_one(
        {"is_active": True, "$or": [{"user1_id": user_id}, {"user2_id": user_id}]}
    )
    return MatchSession.from_doc(doc)


async def create_session(db: AsyncDatabase, user1_id: ObjectId, user2_id: ObjectId) -> MatchSession:
    doc = {
        "user1_id": user1_id,
        "user2_id": user2_id,
        "is_active": True,
        "started_at": utcnow(),
        "ended_at": None,
    }
    res = await db.match_sessions.insert_one(doc)
    doc["_id"] = res.inserted_id
    return MatchSession.from_doc(doc)


async def end_session(db: AsyncDatabase, session: MatchSession) -> None:
    now = utcnow()
    await db.match_sessions.update_one(
        {"_id": session.id}, {"$set": {"is_active": False, "ended_at": now}}
    )
    session.is_active = False
    session.ended_at = now


async def is_in_queue(db: AsyncDatabase, user_id: ObjectId) -> bool:
    return await db.match_queue.count_documents({"user_id": user_id}, limit=1) > 0


async def enqueue(db: AsyncDatabase, user: User, preferred_gender: Gender) -> bool:
    """Returns False if the user was already waiting."""
    try:
        await db.match_queue.insert_one(
            {
                "user_id": user.id,
                "gender": user.gender.value,
                "preferred_gender": preferred_gender.value,
                "created_at": utcnow(),
            }
        )
        return True
    except DuplicateKeyError:
        return False


async def leave_queue(db: AsyncDatabase, user_id: ObjectId) -> bool:
    res = await db.match_queue.delete_one({"user_id": user_id})
    return res.deleted_count > 0


async def pop_match(
    db: AsyncDatabase, user: User, preferred_gender: Gender
) -> Optional[ObjectId]:
    """
    Atomically claim the oldest compatible person from the queue
    (find_one_and_delete, so two users can never grab the same partner).
    """
    excluded: Iterable[ObjectId] = await blocked_either_way(db, user.id)
    query = {
        "user_id": {"$nin": list(excluded) + [user.id]},
        # their preference must accept MY gender (or be "any")
        "preferred_gender": {"$in": [Gender.UNKNOWN.value, user.gender.value]},
    }
    # MY preference must match THEIR gender
    if preferred_gender != Gender.UNKNOWN:
        query["gender"] = preferred_gender.value

    doc = await db.match_queue.find_one_and_delete(query, sort=[("created_at", 1)])
    return doc["user_id"] if doc else None


# ───────────────────────── message logs ─────────────────────────

async def log_message(
    db: AsyncDatabase,
    sender_id: ObjectId,
    receiver_id: ObjectId,
    content_type: str,
    content: Optional[str],
    context: str,
) -> None:
    await db.message_logs.insert_one(
        {
            "sender_id": sender_id,
            "receiver_id": receiver_id,
            "content": content,
            "content_type": content_type,
            "context": context,
            "created_at": utcnow(),
        }
    )


async def recent_logs_for(db: AsyncDatabase, user_id: ObjectId, limit: int = 50) -> List[MessageLog]:
    cursor = (
        db.message_logs.find({"$or": [{"sender_id": user_id}, {"receiver_id": user_id}]})
        .sort("created_at", -1)
        .limit(limit)
    )
    return [MessageLog.from_doc(d) async for d in cursor]


async def count_logs(db: AsyncDatabase) -> int:
    return await db.message_logs.count_documents({})


async def count_active_sessions(db: AsyncDatabase) -> int:
    return await db.match_sessions.count_documents({"is_active": True})


# ───────────────────────── settings (key/value) ─────────────────────────

async def get_setting(db: AsyncDatabase, key: str) -> Optional[str]:
    doc = await db.settings.find_one({"_id": key})
    return doc["value"] if doc else None


async def set_setting(db: AsyncDatabase, key: str, value: str) -> None:
    await db.settings.update_one({"_id": key}, {"$set": {"value": value}}, upsert=True)
