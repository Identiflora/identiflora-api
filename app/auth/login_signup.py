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
from app.models.requests import GoogleUserRegisterRequest, UserRegistrationRequest, UserLoginRequest, UserOTPVerifyRequest
from app.auth.token import create_access_token, get_sub_from_token
from app.auth.email import OTP_EXPIRATION_TIME_MINUTES

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
            if payload.has_otp:
                conn.execute(
                    text("CALL replace_otp(:new_password_hash, :user_email_in)"),
                    {
                        "new_password_hash": argon2.hash(payload.password_hash),
                        "user_email_in": payload.user_email
                    },
                )

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

async def auth_google_account(token: str, engine: Engine) -> Dict[str, Any]:
    """
    Authenticate and login user via Google token to see if they exist in current database.

    Parameters
    ----------
    token : str
        Token from Google when using Google sign in on Flutter app.
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    dict
        Payload containing user generated token.

    Raises
    ------
    HTTPException
        If validation fails, Google token verification issues or database error occurs.
    """
    try:
        load_dotenv()
        GOOGLE_ID = os.getenv("GOOGLE_SERVER_ID")
        user_info = id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_ID)
        user_email = user_info['email']
        
        with engine.begin() as conn:
            # Attempt to login user to know if user exists
            user = conn.execute(
                text("CALL login_user(:user_email_in)"),
                {
                    "user_email_in": user_email,
                },
            ).first()

            # If user doesn't exist, send email back to app for account creation
            if user is None:
                token_input = {
                    "sub": str(user_email),
                    "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=TOKEN_EXPIRATION_TIME_MINUTES),
                    "iat": datetime.now(tz=timezone.utc),
                }

                return {"token_type": "Bearer", "access_token": create_access_token(token_input), "expires_in": TOKEN_EXPIRATION_TIME_MINUTES, "register": True}
    
            # If user does exist but is not flagged as external, flag them now to link their google account
            elif not user.external_login:
                conn.execute(
                    text("CALL set_user_external_login(:user_id_in)"), # Add this function to database
                    {
                        "user_id_in": user.user_id,
                    },
                )
                conn.commit()

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
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while authenticating Google login: {exc}",
        ) from exc
    
def add_google_account(token: str, payload: GoogleUserRegisterRequest, engine: Engine):
    """
    Register user via Google email and requested username in current database.

    Parameters
    ----------
    token : str
        Token from API function auth_google_account that was generated at the time of authentication that contains user email.
    payload : GoogleUserRegisterRequest
        Request data containing user email and username.
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    dict
        Payload containing user generated token.

    Raises
    ------
    HTTPException
        If validation fails, user already exists or database error occurs.
    """
    try:
        user_email = get_sub_from_token(token)

        # Add check for existing email/username
        with engine.begin() as conn:
            # Read-only duplicate guard to avoid duplicate usernames for submissions.
            username_existing = conn.execute(
                text("CALL check_username_exists(:username)"),
                {
                    "username": payload.username
                },
            ).first()

            if username_existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail="This username has already been recorded.",
                )

            # No email duplicate guard is needed as email would be blank string if email already existed.
            # Therefore, execute adding the user.
            user = conn.execute(
                text("CALL add_external_user(:user_email_in, :username_in)"), # Add this function to database
                {
                    "user_email_in": user_email,
                    "username_in": payload.username
                },
            ).first()

            if user is None:
                raise HTTPException(status_code=409, detail="User with username already registered.")
        
            token_input = {
                "sub": str(user.user_id),
                "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=TOKEN_EXPIRATION_TIME_MINUTES),
                "iat": datetime.now(tz=timezone.utc),
            }

            return {"token_type": "Bearer", "access_token": create_access_token(token_input), "expires_in": TOKEN_EXPIRATION_TIME_MINUTES}
    
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="User with username already registered.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while registering Google account: {exc}",
        ) from exc
    
def user_has_otp(payload: UserOTPVerifyRequest, engine: Engine) -> Dict[str, Any]:
    """
    Verify user's OTP is a match.

    Parameters
    ----------
    payload : UserOTPVerifyRequest
        Request data containing user's OTP and email.
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    dict
        Confirmation payload containing the user's ID.

    Raises
    ------
    HTTPException
        If validation fails, user does not exist or database errors occur.
    """
    try:
        with engine.begin() as conn:
            # Verify user exists with this OTP, if this is the most recent OTP requested by this user, and if the OTP is expired
            out = conn.execute(
                text("CALL verify_otp(:otp_exp_time_in, :user_email_in)"),
                {
                    "otp_exp_time_in": OTP_EXPIRATION_TIME_MINUTES,
                    "user_email_in": payload.user_email,
                },
            ).first()

            if out is None or out.otp is None or (out.result != -1 and not argon2.verify(payload.otp, out.otp)):
                raise HTTPException(status_code=401, detail="No user exists with these credentials.")
            
            # Result returns -1 on not OTP match, 0 on matched OTP but expired, and 1 on valid OTP
            return {"result": out.result}

    except IntegrityError as exc:
        raise HTTPException(
            status_code=401,
            detail="No user exists with these credentials.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while checking if user has OTP: {exc}",
        ) from exc