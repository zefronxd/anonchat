"""
Plain dataclasses that mirror the MongoDB documents.

Collections:
  users, blocks, message_logs, match_queue, match_sessions, settings
Every document uses Mongo's ObjectId as `_id`; in Python it is exposed as `.id`.
"""
import enum
from dataclasses import dataclass, fields
from datetime import datetime
from typing import Optional

from bson import ObjectId


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


def _build(cls, doc: dict):
    kwargs = {}
    for f in fields(cls):
        key = "_id" if f.name == "id" else f.name
        if key in doc:
            kwargs[f.name] = doc[key]
    if "gender" in kwargs and kwargs["gender"] is not None:
        kwargs["gender"] = Gender(kwargs["gender"])
    if "preferred_gender" in kwargs and kwargs["preferred_gender"] is not None:
        kwargs["preferred_gender"] = Gender(kwargs["preferred_gender"])
    return cls(**kwargs)


@dataclass
class User:
    id: ObjectId
    tg_id: int
    username: Optional[str] = None
    full_name: Optional[str] = None
    nickname: Optional[str] = None
    bio: Optional[str] = None
    gender: Gender = Gender.UNKNOWN
    link_token: Optional[str] = None
    is_admin: bool = False
    is_blocked: bool = False
    display_id: Optional[str] = None
    age: Optional[int] = None
    referred_by_id: Optional[ObjectId] = None
    referral_confirmed: bool = False
    referral_bonus_until: Optional[datetime] = None
    created_at: Optional[datetime] = None
    match_pref: Optional[str] = None  # last random-chat preference (used by 'Next')

    @classmethod
    def from_doc(cls, doc: Optional[dict]) -> Optional["User"]:
        return _build(cls, doc) if doc else None


@dataclass
class MatchSession:
    id: ObjectId
    user1_id: ObjectId
    user2_id: ObjectId
    is_active: bool = True
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    @classmethod
    def from_doc(cls, doc: Optional[dict]) -> Optional["MatchSession"]:
        return _build(cls, doc) if doc else None

    def partner_of(self, user_id: ObjectId) -> ObjectId:
        return self.user2_id if self.user1_id == user_id else self.user1_id


@dataclass
class MessageLog:
    id: ObjectId
    sender_id: ObjectId
    receiver_id: ObjectId
    content: Optional[str] = None
    content_type: Optional[str] = None
    context: Optional[str] = None  # 'link' | 'reply' | 'match'
    created_at: Optional[datetime] = None

    @classmethod
    def from_doc(cls, doc: Optional[dict]) -> Optional["MessageLog"]:
        return _build(cls, doc) if doc else None
