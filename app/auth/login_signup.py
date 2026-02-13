from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from passlib.hash import argon2
from datetime import datetime, timedelta, timezone

from google.oauth2 import id_token
from google.auth.transport import requests
from google.auth import exceptions

import os
from dotenv import load_dotenv


# local imports
from app.models.requests import UserAddGoogleUsernameRequest, UserRegistrationRequest, UserLoginRequest
from app.auth.token import create_access_token

TOKEN_EXPIRATION_TIME_MINUTES = 10

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
            password_hash_2 = argon2.hash(payload.password_hash)

            # Write: insert the user account information with id and timestamp. This will also get the newly created user's ID.
            user = conn.execute(
                text("CALL add_user(:user_email_in, :username_in, :user_password_in)"),
                {
                    "user_email_in": payload.user_email,
                    "username_in": payload.username,
                    "user_password_in": password_hash_2
                },
            ).first()

        # Automatically log in the user after registration
        first_login_request = UserLoginRequest(
            user_email=payload.user_email,
            password_hash=payload.password_hash,
        )
        return user_login(first_login_request, engine) 
        
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

            if not argon2.verify(payload.password_hash, user.password_hash):
                raise HTTPException(status_code=401, detail="No user exists with these credentials.")

            token_input = {
                "sub": str(user.user_id),
                "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=TOKEN_EXPIRATION_TIME_MINUTES),
                "iat": datetime.now(tz=timezone.utc),
            }

            return {"token_type": "Bearer", "access_token": create_access_token(token_input), "expires_in": TOKEN_EXPIRATION_TIME_MINUTES}

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

def register_google_account(email: str, username: str, engine: Engine):
    if username != "" and email != "":
        # Add check for existing email/username
        with engine.begin() as conn:
            # Read-only duplicate guard to avoid duplicate usernames for submissions.
            username_existing = conn.execute(
                text("CALL check_username_exists(:username)"),
                {"username": username},
            ).first()

            if username_existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail="This username has already been recorded.",
                )

            # No email duplicate guard is needed as user would have been logged in if email was duplicate
            # Therefore, execute adding the user
            user = conn.execute(
                text("CALL add_google_user(:user_email_in, :username_in)"), # Add this function to database
                {
                    "user_email_in": email,
                    "username_in": username
                },
            ).first()

            if user is None:
                raise
    else:
        raise HTTPException(
            status_code=400,
            detail="Bad submission. Try verifying email and username are not null for google account registration."
        )

async def auth_google_login(payload: UserAddGoogleUsernameRequest, token: str, engine: Engine) -> Dict[str, Any]:
    try:
        load_dotenv()
        GOOGLE_ID = os.getenv("GOOGLE_SERVER_ID")
        user_info = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_ID)
        user_email = user_info['email']
        
        with engine.begin() as conn:
            user = conn.execute(
                text("CALL login_user(:user_email_in)"),
                {
                    "user_email_in": user_email,
                },
            ).first()

            # Attempt to create external google account if user doesn't exist
            if user is None:
                register_google_account(user_email, payload.username, engine)

            # If user does exist but is not flagged as external, flag them now to link their google account
            elif not user.external_login:
                user = conn.execute(
                    text("CALL set_user_external_login(:user_id_in)"), # Add this function to database
                    {
                        "user_id_in": user.user_id,
                    },
                ).first()
            
            token_input = {
                "sub": str(user.user_id),
                "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=TOKEN_EXPIRATION_TIME_MINUTES),
                "iat": datetime.now(tz=timezone.utc),
            }
        
            return {"token_type": "Bearer", "access_token": create_access_token(token_input), "expires_in": TOKEN_EXPIRATION_TIME_MINUTES}
    
    except exceptions.GoogleAuthError as exc:
        raise HTTPException(
            status_code=401,
            detail="No google user exists with these credentials."
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Google token verification failed."
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Username already registered.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while authenticating google login: {exc}",
        ) from exc