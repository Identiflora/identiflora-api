from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from jose import jwt
from dotenv import load_dotenv

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1000000

if SECRET_KEY is None:
    raise RuntimeError("SECRET_KEY environment variable is not set")

def create_access_token(data: dict):
    to_encode = data.copy()
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_sub_from_token(given_token: str):
    claims = jwt.decode(token=given_token, key=SECRET_KEY, algorithms=[ALGORITHM])
    return claims.get("sub")