"""
One-time migration: old SQLite DB  ->  MongoDB.

Usage (from project root, with .env filled in):
    python scripts/migrate_sqlite_to_mongo.py ./data/db.sqlite3

It never touches the SQLite file. It refuses to run if the target Mongo
`users` collection is not empty (so you can't double-import by accident).
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def _dt(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _gender(value):
    # SQLAlchemy's Enum stored the member NAME ("MALE"); normalise to "male"
    return str(value).lower() if value else "unknown"


def build_docs(sqlite_path, new_id):
    """Pure function: read SQLite, return documents ready for insert_many."""
    con = sqlite3.connect(sqlite_path)
    con.row_factory = sqlite3.Row

    def rows(table):
        try:
            return con.execute(f"SELECT * FROM {table}").fetchall()
        except sqlite3.OperationalError:
            return []

    idmap = {}  # old int id -> new ObjectId
    users = []
    user_rows = rows("users")
    for r in user_rows:
        idmap[r["id"]] = new_id()

    keys = lambda r: r.keys()
    for r in user_rows:
        k = keys(r)
        users.append({
            "_id": idmap[r["id"]],
            "tg_id": r["tg_id"],
            "username": r["username"],
            "full_name": r["full_name"],
            "nickname": r["nickname"],
            "bio": r["bio"],
            "gender": _gender(r["gender"]),
            "link_token": r["link_token"],
            "is_admin": bool(r["is_admin"]),
            "is_blocked": bool(r["is_blocked"]),
            "display_id": r["display_id"],
            "age": r["age"] if "age" in k else None,
            "referred_by_id": idmap.get(r["referred_by_id"]),
            "referral_confirmed": bool(r["referral_confirmed"]) if "referral_confirmed" in k else False,
            "referral_bonus_until": _dt(r["referral_bonus_until"]),
            "created_at": _dt(r["created_at"]),
        })

    blocks = [
        {
            "blocker_id": idmap[r["blocker_id"]],
            "blocked_id": idmap[r["blocked_id"]],
            "created_at": _dt(r["created_at"]),
        }
        for r in rows("blocks")
        if r["blocker_id"] in idmap and r["blocked_id"] in idmap
    ]
    # de-duplicate (old schema allowed duplicates, Mongo has a unique index)
    seen, uniq_blocks = set(), []
    for b in blocks:
        key = (b["blocker_id"], b["blocked_id"])
        if key not in seen:
            seen.add(key)
            uniq_blocks.append(b)

    gender_by_user = {u["_id"]: u["gender"] for u in users}
    queue = [
        {
            "user_id": idmap[r["user_id"]],
            "gender": gender_by_user[idmap[r["user_id"]]],
            "preferred_gender": _gender(r["preferred_gender"]),
            "created_at": _dt(r["created_at"]),
        }
        for r in rows("match_queue")
        if r["user_id"] in idmap
    ]

    sessions = [
        {
            "user1_id": idmap[r["user1_id"]],
            "user2_id": idmap[r["user2_id"]],
            "is_active": bool(r["is_active"]),
            "started_at": _dt(r["started_at"]),
            "ended_at": _dt(r["ended_at"]),
        }
        for r in rows("match_sessions")
        if r["user1_id"] in idmap and r["user2_id"] in idmap
    ]

    logs = [
        {
            "sender_id": idmap[r["sender_id"]],
            "receiver_id": idmap[r["receiver_id"]],
            "content": r["content"],
            "content_type": r["content_type"],
            "context": r["context"],
            "created_at": _dt(r["created_at"]),
        }
        for r in rows("message_logs")
        if r["sender_id"] in idmap and r["receiver_id"] in idmap
    ]

    settings = [{"_id": r["key"], "value": r["value"]} for r in rows("settings")]

    con.close()
    return {
        "users": users,
        "blocks": uniq_blocks,
        "match_queue": queue,
        "match_sessions": sessions,
        "message_logs": logs,
        "settings": settings,
    }


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sqlite_path = Path(sys.argv[1])
    if not sqlite_path.exists():
        sys.exit(f"SQLite file not found: {sqlite_path}")

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from bson import ObjectId
    from pymongo import MongoClient
    from config import config

    docs = build_docs(sqlite_path, ObjectId)

    client = MongoClient(config.MONGO_URI)
    db = client[config.MONGO_DB]
    if db.users.count_documents({}, limit=1):
        sys.exit(f"Mongo database '{config.MONGO_DB}' already has users — aborting.")

    # Same indexes as the bot (so duplicates are caught while importing)
    db.users.create_index("tg_id", unique=True)
    db.users.create_index("link_token", unique=True)
    db.users.create_index(
        "display_id", unique=True, partialFilterExpression={"display_id": {"$type": "string"}}
    )

    for name, items in docs.items():
        if items:
            db[name].insert_many(items, ordered=False)
        print(f"{name:15} {len(items)} documents")
    print("Done. Start the bot once so it creates the remaining indexes.")


if __name__ == "__main__":
    main()
