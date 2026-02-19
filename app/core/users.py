from __future__ import annotations

import random
import string

from typing import Any, Dict

from fastapi import HTTPException, BackgroundTasks

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from passlib.hash import argon2

from app.models.requests import UserPointAddRequest, UserPasswordResetRequest
from app.auth.token import get_sub_from_token
from app.auth.email import otpMailMessage

def get_user_username(user_id: int, engine: Engine) -> Dict[str, Any]:
    """
    Fetch user's username with their ID.

    Parameters
    ----------
    user_id : int
        User's verification ID.
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    dict
        Payload containing user's username.

    Raises
    ------
    HTTPException
        If validation fails, ID is not valid or database errors occurred.
    """
    try:
        with engine.connect() as conn:
            user = conn.execute(
                text("CALL get_user_leaderboard_info(:user_id_in)"),
                {
                    "user_id_in": user_id,
                },
            ).first()

            if user is None:
                raise HTTPException(status_code=404, detail="User with this ID could not be found.")
            
            return {"username": user.username}
    
    except IntegrityError as exc:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching username: {exc}",
        ) from exc

def get_points(user_id: int, engine: Engine) -> Dict[str, Any]:
    """
    Fetch user's points with their ID.

    Parameters
    ----------
    user_id : int
        User's verification ID.
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    dict
        Payload containing user's points.

    Raises
    ------
    HTTPException
        If validation fails, ID is not valid or database errors occurred.
    """
    try:
        with engine.connect() as conn:
            user = conn.execute(
                text("CALL get_user_leaderboard_info(:user_id_in)"),
                {
                    "user_id_in": user_id,
                },
            ).first()

            if user is None:
                raise HTTPException(status_code=404, detail="User with this ID could not be found.")
            
            return {"pts": user.global_points}
    
    except IntegrityError as exc:
        raise HTTPException(
            status_code=404,
            detail="User not found.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching user points: {exc}",
        ) from exc

def get_count_user(engine: Engine) -> Dict[str, Any]:
    """
    Fetch user count from database.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    dict
        Payload containing user count.

    Raises
    ------
    HTTPException
        If validation fails, there are no users or database errors occurred.
    """
    try:
        with engine.connect() as conn:
            count = conn.execute(
                text("CALL get_num_users()"),
            ).first()

            if count is None:
                raise HTTPException(status_code=404, detail="There are no users to count")
            
            return {"user_count": count[0]}
    
    except IntegrityError as exc:
        raise HTTPException(
            status_code=404,
            detail="No users found.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching user count: {exc}",
        ) from exc

def add_user_global_points(payload: UserPointAddRequest, engine: Engine) -> Dict[str, Any]:
    """
    Add points to user account in database.

    Parameters
    ----------
    payload : UserPointAddRequest
        Request data containing user token and points to add.
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    dict
        Payload containing success of if points were added.

    Raises
    ------
    HTTPException
        If validation fails, there are no users or database errors occurred.
    """
    try:
        user_id = int(get_sub_from_token(payload.user_token))

        with engine.connect() as conn:
            user = conn.execute(
                text("CALL add_user_global_points(:user_id_in, :add_points_in)"),
                {
                    "user_id_in": user_id,
                    "add_points_in": payload.add_points
                },
            )
            conn.commit()

            if user is None:
                raise HTTPException(status_code=404, detail="User with this ID could not be found.")
            
            return {"success": True}
    
    except IntegrityError as exc:
        raise HTTPException(
            status_code=404,
            detail="No users found.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while adding user points: {exc}",
        ) from exc
    
def password_reset_mail_request(payload: UserPasswordResetRequest, engine: Engine, backgroundTasks: BackgroundTasks) -> Dict[str, Any]:
    """
    Sends the user an email with temporary password to reset their account password.

    Parameters
    ----------
    token: str
        User d
    payload : UserPasswordResetRequest
        Request data containing user email.
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.
    backgroundTasks: BackgroundTasks
        Background task queue supplied by FastAPI initialization.

    Returns
    -------
    dict
        Payload containing success of if email was queued to send.

    Raises
    ------
    HTTPException
        If validation fails, there are is no matching email or database errors occurred.
    """
    try:
        with engine.connect() as conn:

            # Probably needs more verifiers than just email. Perhaps security question and/or region answer?
            # Check if email, and by extension the user, does exist
            user = conn.execute(
                text("CALL check_user_email_exists(:user_email_in)"),
                {
                    "user_email_in": payload.user_email
                },
            ).first()
            
            if user is None:
                raise HTTPException(status_code=404, detail="User with this email could not be found.")
            
            # Generate OTP (One Time Password) of defined length
            values = string.ascii_letters + string.digits
            otp = ''.join(random.choice(values) for _ in range(payload.otp_length))
            hashed_otp = argon2.hash(otp)
            
            # Call to database procedure which handles checking for external users, setting user password/flag to OTP, and all OTP security logs
            # Returns -1 on fail, 0 on external user found, and 1 on valid execution
            out = conn.execute(
                text("CALL otp_requested(:user_email_in, :otp_in)"),
                {
                    "user_email_in": payload.user_email,
                    "otp_in": hashed_otp
                },
            ).first()
            conn.commit()

            # If external user found then raise action denied exception
            if out.result == 0:
                raise HTTPException(status_code=403, detail="Action denied. User with this email is considered an external account.")

            # note: login count failed attempt to wipe OTP on database

            # Email OTP to user email and return response
            return otpMailMessage(payload.user_email, otp, backgroundTasks)
    
    except IntegrityError as exc:
        raise HTTPException(
            status_code=404,
            detail="No user with this email found.",
        ) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=403, 
            detail="Action denied. User with this email is considered an external account."
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while resetting user password: {exc}",
        ) from exc