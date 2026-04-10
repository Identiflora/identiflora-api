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
                raise HTTPException(status_code=400, detail="Cannot send friend request to yourself.")

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


@app.get("/friends")
async def friends(user_id: int, engine: Engine) -> Dict[str, Any]:
    return {"friends": get_friends(user_id, engine)}


@app.get("/friends/pending")
async def pending_friends(user_id: int, engine: Engine) -> Dict[str, Any]:
    return {"pending_requests": get_pending_requests(user_id, engine)}


@app.post("/friends/add")
async def add_friend_endpoint(payload: FriendAddRequest, user_id: int, engine: Engine) -> Dict[str, Any]:
    return add_friend(payload, user_id, engine)


@app.post("/friends/accept")
async def accept_friend_request(requester_id: int, addressee_id: int, engine: Engine) -> Dict[str, Any]:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CALL accept_friend_request(:requester_id_in, :addressee_id_in)
                    """
                ),
                {
                    "requester_id_in": requester_id,
                    "addressee_id_in": addressee_id,
                },
            )

            return {"message": "Friend request accepted."}

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while accepting friend request: {exc}",
        ) from exc


@app.post("/friends/reject")
async def reject_friend_request(requester_id: int, addressee_id: int, engine: Engine) -> Dict[str, Any]:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CALL reject_friend_request(:requester_id_in, :addressee_id_in)
                    """
                ),
                {
                    "requester_id_in": requester_id,
                    "addressee_id_in": addressee_id,
                },
            )

            return {"message": "Friend request rejected."}

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while rejecting friend request: {exc}",
        ) from exc


@app.delete("/friends")
async def delete_friend(friend_id: int, user_id: int, engine: Engine) -> Dict[str, Any]:
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CALL remove_friend(:user_id_in, :friend_id_in)
                    """
                ),
                {
                    "user_id_in": user_id,
                    "friend_id_in": friend_id,
                },
            )

            return {"message": "Friend deleted."}

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while deleting friend: {exc}",
        ) from exc
