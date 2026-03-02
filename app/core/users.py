from __future__ import annotations

import random
import string

from typing import Any, Dict

from fastapi import HTTPException, BackgroundTasks

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from passlib.hash import argon2

from app.models.requests import UserLeaderboardRequest, UserPointAddRequest, UserPasswordResetRequest
from app.auth.token import get_sub_from_token
from app.auth.email import otpMailMessage

def get_global_leaderboard(payload: UserLeaderboardRequest, engine: Engine) -> Dict[str, Any]:
    """
    Retrieve amount of sorted users defined in payload.

    Parameters
    ----------
    payload : UserLeaderboardRequest
        Request data containing leaderboard size.
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    dict
        Payload containing map of user ids, usernames, points, and badges sorted by points.

    Raises
    ------
    HTTPException
        If validation fails, there are no users or database errors occurred.
    """
    try:
        with engine.connect() as conn:
            leaderboard = conn.execute(
                text("CALL get_global_leaderboard_info(:leaderboard_size)"),
                {
                    "leaderboard_size": payload.leaderboard_size
                },
            ).fetchall()

            if leaderboard is None:
                raise HTTPException(status_code=404, detail="No users could be found.")
            
            users = {}
            for (id, username, points, badge) in leaderboard:
                users[id] = (username, points, badge)
            
            return users
    
    except IntegrityError as exc:
        raise HTTPException(
            status_code=404,
            detail="No users found.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while retrieving global leaderboard: {exc}",
        ) from exc
    
def get_regional_leaderboard(user_id: int, payload: UserLeaderboardRequest, engine: Engine) -> Dict[str, Any]:
    """
    Retrieve amount of sorted users dependent on user region defined in payload.

    Parameters
    ----------
    user_id : int
        Database id for user
    payload : UserLeaderboardRequest
        Request data containing leaderboard size.
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    dict
        Payload containing map of user ids, usernames, points, and badges sorted by points and filtered by user's region.

    Raises
    ------
    HTTPException
        If validation fails, there are no users or database errors occurred.
    """
    try:
        with engine.connect() as conn:
            leaderboard = conn.execute(
                text("CALL get_regional_leaderboard_info(:user_id_in, :leaderboard_size)"),
                {
                    "user_id_in": user_id,
                    "leaderboard_size": payload.leaderboard_size
                },
            ).fetchall()

            if leaderboard is None:
                raise HTTPException(status_code=404, detail="No users could be found for this region.")
            
            users = {}
            for (id, username, points, badge) in leaderboard:
                users[id] = (username, points, badge)
            
            return users
    
    except IntegrityError as exc:
        raise HTTPException(
            status_code=404,
            detail="No users found for this region.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while retrieving regional leaderboard: {exc}",
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

def add_user_global_points(user_id: int, add_points: int, engine: Engine) -> bool:
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
        with engine.connect() as conn:
            user = conn.execute(
                text("CALL add_user_global_points(:user_id_in, :add_points_in)"),
                {
                    "user_id_in": user_id,
                    "add_points_in": add_points
                },
            )
            conn.commit()

            if user is None:
                raise HTTPException(status_code=404, detail="User with this ID could not be found.")
            
            return True
    
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
        Request data containing user email and length of generated OTP.
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

def get_user_points(user_id: int, engine: Engine) -> int:
    """
    Fetch the global points for a user identified by their user_id in their auth token.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    int
        The global points associated with the user_id in the database

    Raises
    ------
    HTTPException
        404 if not found, 500 for database errors.
    """
    try:
        with engine.connect() as conn:
            payload = {"user_id": user_id}
            result = conn.execute(text('CALL get_user_points(:user_id)'), payload).first()
            if result is None:
                raise HTTPException(status_code=404, detail="Users points not found.")
            return result.global_points
        
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching users points: {exc}",
        ) from exc

def get_username(user_id: int, engine: Engine) -> str:
    """
    Fetch the username for a user identified by their user_id in their auth token.

    Parameters
    ----------
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    String
        The username associated with the user id input

    Raises
    ------
    HTTPException
        404 if not found, 500 for database errors.
    """
    try:
        with engine.connect() as conn:
            payload = {"user_id": user_id}
            result = conn.execute(text('CALL get_username(:user_id)'), payload).first()
            if result is None:
                raise HTTPException(status_code=404, detail="Username not found.")
            return result.username
        
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching username: {exc}",
        ) from exc
    
def set_user_badge(user_id: int, badge_path: str, engine: Engine) -> bool:
    """
    Set the Flutter asset file path to a user's selected badge that is identified by the user_id in their auth token.

    Parameters
    ----------
    user_id : int
        Database id for user
    badge_path : str
        File path to badge asset in Fluutter
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    bool
        Success or fail when setting user badge

    Raises
    ------
    HTTPException
        404 if not found, 500 for database errors.
    """
    try:
        with engine.connect() as conn:
            payload = {"user_id_in": user_id, "badge_file_path": badge_path}
            result = conn.execute(text('CALL set_user_badge(:user_id_in, :badge_file_path)'), payload)
            conn.commit()

            if result is None:
                raise HTTPException(status_code=404, detail="User not found when setting badge.")
            
            return True
        
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while setting selected badge: {exc}",
        ) from exc
    
def get_user_badge(user_id: int, engine: Engine) -> str:
    """
    Get the Flutter asset file path associated to a user's selected badge that is identified by the user_id in their auth token.

    Parameters
    ----------
    user_id : int
        Database id for user
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    String
        Selected badge Flutter file path

    Raises
    ------
    HTTPException
        404 if not found, 500 for database errors.
    """
    try:
        with engine.connect() as conn:
            payload = {"user_id_in": user_id}
            result = conn.execute(text('CALL get_user_badge(:user_id_in)'), payload).first()

            if result is None:
                raise HTTPException(status_code=404, detail="User not found when getting badge.")
            
            return result.selected_badge
        
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while getting selected badge: {exc}",
        ) from exc
    
def get_user_region(user_id: int, engine: Engine) -> str:
    """
    Get the region of the user that is identified by the user_id in their auth token.

    Parameters
    ----------
    user_id : int
        Database id for user
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    String
        User region

    Raises
    ------
    HTTPException
        404 if not found, 500 for database errors.
    """
    try:
        with engine.connect() as conn:
            payload = {"user_id_in": user_id}
            result = conn.execute(text('CALL get_user_region(:user_id_in)'), payload).first()

            if result is None:
                raise HTTPException(status_code=404, detail="User region not found.")
            
            return result.selected_badge
        
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while getting user's region: {exc}",
        ) from exc

