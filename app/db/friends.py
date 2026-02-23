from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.requests import FriendAddRequest


def get_friends(user_id: int, engine: Engine) -> List[Dict[str, Any]]:
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text("CALL get_friends(:user_id_in)"),
                {"user_id_in": user_id},
            ).all()

            return [{"id": r.id, "username": r.username} for r in rows]

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching friends: {exc}",
        ) from exc


def add_friend(payload: FriendAddRequest, user_id: int, engine: Engine) -> Dict[str, Any]:
    friend_username = payload.friend_username.strip() if payload.friend_username else ""
    if not friend_username:
        raise HTTPException(status_code=400, detail="friend_username is required.")

    try:
        with engine.begin() as conn:
            conn.execute(
                text("CALL add_friend_by_username(:user_id_in, :friend_username_in)"),
                {
                    "user_id_in": user_id,
                    "friend_username_in": friend_username,
                },
            )

            return {
                "user_id": user_id,
                "friend_username": friend_username,
                "message": "Friend added.",
            }

    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Friendship already exists (or constraint violation).",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while adding friend: {exc}",
        ) from exc
     
