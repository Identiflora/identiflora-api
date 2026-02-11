from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from jose import jwt
from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1000000

if SECRET_KEY is None:
    raise RuntimeError("SECRET_KEY environment variable is not set")

def create_access_token(data: dict):
    """
    Creates a JWT access token with the given data as the payload.
    
    :param data: Data should contain at least a "sub" field representing the subject (e.g., user ID) and can include other claims as needed, such as expiration time ("exp") and issued at time ("iat").
    :type data: dict
    """
    to_encode = data.copy()
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """
    Verifies a given JWT token and returns the decoded payload if valid, or None if invalid.
    
    :param token: JWT token string to be verified.
    :type token: str
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.JWTError:
        return None

def get_current_user(authorization: str = Header(None)):
    """
    Dependency function for FastAPI routes that extracts and verifies a JWT token from the Authorization header, returning the decoded payload if valid.
    
    :param authorization: The value of the Authorization header, expected to be in the format "Bearer
    :type authorization: str
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    # ensure token is Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid token format")
    
    token = parts[1]
    
    payload = verify_token(token)
    
    # If payload is None, the token was invalid or expired
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return payload