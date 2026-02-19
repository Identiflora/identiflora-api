from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from app.models.requests import UserPointAddRequest, UserPasswordResetRequest
from app.auth.token import get_user_id_from_token

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
        user_id = get_user_id_from_token(payload.user_token)

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
    
def password_reset_mail_request(payload: UserPasswordResetRequest, engine: Engine) -> Dict[str, Any]:
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
            # Attempt to log user in to get user details
            user = conn.execute(
                text("CALL login_user(:user_email_in)"),
                {
                    "user_email_in": payload.user_email
                },
            )

            # Simple user doesn't exist catch
            if user is None:
                raise HTTPException(status_code=404, detail="User with this email could not be found.")
            
            # Check if user can login using external account, if so deny password reset
            elif user.external_login:
                raise HTTPException(status_code=403, detail="Action denied. User with this email is considered an external account.")
            
            # Generate OTP (One Time Password)

            # Set OTP database flag and expiration timer (note: add OTP failed attempt count before OTP is wipped on database)

            # Change user password to OTP

            # Email OTP to user email

            return {"success": True}
    
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