from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from passlib.hash import bcrypt

# local imports
from app.models.requests import UserRegistrationRequest, UserLoginRequest

def record_user_registration(payload: UserRegistrationRequest, engine: Engine) -> Dict[str, Any]:
    """
    Persist a user registration, validating referenced rows and constraints.

    Parameters
    ----------
    payload : UserRegistrationRequest
        Request data containing username, email, and password hash.
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    dict
        Confirmation payload containing the user's ID.

    Raises
    ------
    HTTPException
        If validation fails, referenced rows are missing, or database errors occur.
    """
    try:
        with engine.begin() as conn:
            # Read-only duplicate guard to avoid duplicate emails for submissions.
            email_existing = conn.execute(
                text("CALL check_user_email_exists(:email)"),
                {"email": payload.user_email},
            ).first()

            if email_existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail="This email has already been recorded.",
                )
            
            # Read-only duplicate guard to avoid duplicate usernames for submissions.
            username_existing = conn.execute(
                text("CALL check_username_exists(:username)"),
                {"username": payload.username},
            ).first()

            if username_existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail="This username has already been recorded.",
                )
            
            # Second hashing of password (recommended for extra security) 
            # This is done after user existing checks to avoid unnecessary runtime
            password_hash_2 = bcrypt.hash(payload.password_hash)

            # Write: insert the user account information with id and timestamp. This will also get the newly created user's ID.
            user = conn.execute(
                text("CALL add_user(:user_email_in, :username_in, :user_password_in)"),
                {
                    "user_email_in": payload.user_email,
                    "username_in": payload.username,
                    "user_password_in": password_hash_2
                },
            ).first()

            return {"user_id": user.user_id}

    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Email or username already registered.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while creating user registration: {exc}",
        ) from exc
    
def user_login(payload: UserLoginRequest, engine: Engine) -> Dict[str, Any]:
    """
    Persist a user login, validating referenced rows and constraints.

    Parameters
    ----------
    payload : UserLoginRequest
        Request data containing email and password hash.
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    dict
        Confirmation payload containing the user's ID.

    Raises
    ------
    HTTPException
        If validation fails, referenced rows are missing, or database errors occur.
    """
    try:
        with engine.begin() as conn:
            user = conn.execute(
                text("CALL login_user(:user_email_in)"),
                {
                    "user_email_in": payload.user_email,
                },
            ).first()

            if user is None:
                raise HTTPException(status_code=401, detail="No user exists with these credentials.")

            if not bcrypt.verify(payload.password_hash, user.password_hash):
                raise HTTPException(status_code=401, detail="No user exists with these credentials.")

            return {"user_id": user.user_id}

    except IntegrityError as exc:
        raise HTTPException(
            status_code=401,
            detail="No user exists with these credentials.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while logging in user: {exc}",
        ) from exc