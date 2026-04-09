from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.requests import FriendAddRequest


# Endpoint to get the list of friends for a user
def get_friends(user_id: int, engine: Engine) -> List[Dict[str, Any]]:
    try:
        with engine.begin() as conn:
            rows = conn.execute(
                text("CALL get_friends(:user_id_in)"),
                {"user_id_in": user_id},
            ).all()

            # Return the list of accepted friends
            return [{"id": r.user_id, "username": r.username} for r in rows]

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching friends: {exc}",
        ) from exc


# Endpoint to send a friend request
def add_friend(payload: FriendAddRequest, user_id: int, engine: Engine) -> Dict[str, Any]:
    friend_username = payload.friend_username.strip() if payload.friend_username else ""
    if not friend_username:
        raise HTTPException(status_code=400, detail="friend_username is required.")

    try:
        with engine.begin() as conn:
            # Check if the friend exists
            result = conn.execute(
                text("SELECT user_id FROM user WHERE username = :friend_username"),
                {"friend_username": friend_username},
            ).fetchone()

            if not result:
                raise HTTPException(status_code=404, detail="User not found.")

            addressee_id = result["user_id"]

            # Ensure the user is not trying to add themselves
            if addressee_id == user_id:
                raise HTTPException(status_code=400, detail="Cannot send friend request to yourself.")

            # Insert a pending friendship with both statuses as 'pending'
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


# Endpoint to accept a friend request
@app.post("/accept_friend_request")
async def accept_friend_request(requester_id: int, addressee_id: int, engine: Engine) -> Dict[str, Any]:
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    CALL accept_friend_request(:requester_id_in, :addressee_id_in)
                    """
                ),
                {"requester_id_in": requester_id, "addressee_id_in": addressee_id},
            )

            if result:
                return {"message": "Friend request accepted."}
            else:
                raise HTTPException(status_code=400, detail="Error accepting friend request.")

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while accepting friend request: {exc}",
        ) from exc
