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

            return [{"id": r.user_id, "username": r.username} for r in rows]

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching friends: {exc}",
        ) from exc


def get_pending_requests(user_id: int, engine: Engine) -> List[Dict[str, Any]]:
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text("CALL get_pending_friend_requests(:user_id_in)"),
                {"user_id_in": user_id},
            ).all()

            return [{"id": r.user_id, "username": r.username} for r in rows]

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching pending requests: {exc}",
        ) from exc


def add_friend(payload: FriendAddRequest, user_id: int, engine: Engine) -> Dict[str, Any]:
    friend_username = payload.friend_username.strip() if payload.friend_username else ""
    if not friend_username:
        raise HTTPException(status_code=400, detail="friend_username is required.")

    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("SELECT user_id FROM user WHERE username = :friend_username"),
                {"friend_username": friend_username},
            ).mappings().fetchone()

            if not result:
                raise HTTPException(status_code=404, detail="User not found.")

            addressee_id = result["user_id"]

            if addressee_id == user_id:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot send friend request to yourself.",
                )

            conn.execute(
                text(
                    """
                    CALL add_friend_by_username(
                        :user_id_in, :friend_username_in
                    )
                    """
                ),
                {
                    "user_id_in": user_id,
                    "friend_username_in": friend_username,
                },
            )

            return {
                "user_id": user_id,
                "friend_username": friend_username,
                "message": "Friend request sent.",
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


def accept_friend_request(requester_id: int, user_id: int, engine: Engine) -> Dict[str, Any]:
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    UPDATE friendships
                    SET status = 'accepted'
                    WHERE requester_id = :requester_id
                      AND addressee_id = :user_id
                      AND status = 'pending'
                    """
                ),
                {
                    "requester_id": requester_id,
                    "user_id": user_id,
                },
            )

            if result.rowcount == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Pending friend request not found.",
                )

            return {
                "message": "Friend request accepted.",
                "requester_id": requester_id,
                "user_id": user_id,
            }

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while accepting friend request: {exc}",
        ) from exc


def reject_friend_request(requester_id: int, user_id: int, engine: Engine) -> Dict[str, Any]:
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    DELETE FROM friendships
                    WHERE requester_id = :requester_id
                      AND addressee_id = :user_id
                      AND status = 'pending'
                    """
                ),
                {
                    "requester_id": requester_id,
                    "user_id": user_id,
                },
            )

            if result.rowcount == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Pending friend request not found.",
                )

            return {
                "message": "Friend request rejected.",
                "requester_id": requester_id,
                "user_id": user_id,
            }

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while rejecting friend request: {exc}",
        ) from exc

def search_usernames(prefix: str, user_id: int, engine: Engine) -> List[Dict[str, Any]]:
    prefix = (prefix or "").strip()

    if not prefix:
        return []

    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT user_id, username
                    FROM user
                    WHERE username LIKE :prefix
                      AND user_id <> :user_id
                      AND user_id NOT IN (
                          SELECT CASE
                              WHEN requester_id = :user_id THEN addressee_id
                              ELSE requester_id
                          END
                          FROM friendships
                          WHERE requester_id = :user_id
                             OR addressee_id = :user_id
                      )
                    ORDER BY username ASC
                    LIMIT 20
                    """
                ),
                {
                    "prefix": f"{prefix}%",
                    "user_id": user_id,
                },
            ).mappings().all()

            return [{"id": r["user_id"], "username": r["username"]} for r in rows]

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while searching usernames: {exc}",
        ) from exc

def delete_friend(user_id: int, friend_id: int, engine: Engine) -> Dict[str, Any]:
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    DELETE FROM friendships
                    WHERE (
                        requester_id = :user_id
                        AND addressee_id = :friend_id
                    ) OR (
                        requester_id = :friend_id
                        AND addressee_id = :user_id
                    )
                    """
                ),
                {
                    "user_id": user_id,
                    "friend_id": friend_id,
                },
            )

            if result.rowcount == 0:
                raise HTTPException(
                    status_code=404,
                    detail="Friendship not found.",
                )

            return {
                "message": "Friend deleted successfully.",
                "user_id": user_id,
                "friend_id": friend_id,
            }

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while deleting friend: {exc}",
        ) from exc



