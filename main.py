#!/usr/bin/env python3
from __future__ import annotations

from dotenv import load_dotenv

import uvicorn

from fastapi import FastAPI, BackgroundTasks, Depends, Request
from typing import Annotated


from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models.requests import IncorrectIdentificationRequest, PlantSpeciesRequest, UserBadgeSetRequest, UserRegistrationRequest, UserLoginRequest, UserLeaderboardRequest, UserPointAddRequest, GoogleUserRegisterRequest, UserPasswordResetRequest, UserOTPVerifyRequest

from app.auth.login_signup import auth_google_account, add_google_account, user_login, record_user_registration, user_has_otp
from app.auth.token import get_current_user

from app.core.db_connection import build_engine
from app.core.users import get_global_leaderboard, get_count_user, add_user_global_points, get_regional_leaderboard, get_user_badge, password_reset_mail_request, get_user_points, get_username, set_user_badge, get_user_region

from app.db.incorrect_identification import record_incorrect_identification
from app.db.plant_species import record_plant_species, get_plant_species_url, get_species_id

# from app.db.friends import get_friends, add_friend
from app.models.requests import FriendAddRequest

import logging

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

logging.basicConfig(level=logging.INFO)

HOST = "localhost"
PORT = 8000



load_dotenv()

limiter = Limiter(key_func=get_remote_address, default_limits=["50/minute"])
app = FastAPI(
    title="Identiflora Database API",
    version="0.1.0",
    description="Minimal API for interacting with the Identiflora MySQL database.",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

engine = build_engine()

@app.post("/authenticate-token")
# @limiter.limit("5/minute")
async def authenticate_token_router(token_claims: Annotated[dict, Depends(get_current_user)]):
    """Authenticates user token and returns boolean"""
    logging.info(f"User: {token_claims.get('sub')} authenticated")
    return True

@app.post("/incorrect-identifications")
async def add_incorrect_identification(payload: IncorrectIdentificationRequest, token_claims: Annotated[dict, Depends(get_current_user)]):
    """Route handler that records an incorrect identification via helper logic."""
    logging.info(f"Incorrect identification recorded by user {token_claims.get('sub')}: {payload.identification_id}")
    return record_incorrect_identification(payload, engine)

@app.get("/species-id/{scientific_name}")
async def species_id(scientific_name: str):
    """Route handler that returns a species id via helper logic."""
    return get_species_id(scientific_name, engine)

@app.post("/plant-species")
async def add_plant_species(payload: PlantSpeciesRequest):
    """Route handler that records a new plant species via helper logic."""
    logging.info("HIT /plant-species: %s", payload.scientific_name)
    return record_plant_species(payload, engine)

@app.get("/plant-species-url/{scientific_name}")
async def get_plant_species_url_router(scientific_name: str): 
    """Route handler that returns a plant species img url using query parameters."""
    return get_plant_species_url(scientific_name, engine)

@app.post("/user/register")
async def add_registered_user(payload: UserRegistrationRequest):
    """Route handler that records user registration data via helper logic."""
    return record_user_registration(payload, engine)

@app.post("/user/login")
async def login_user(payload: UserLoginRequest):
    """Route handler that records user registration data via helper logic."""
    return user_login(payload, engine)

@app.post("/global-leaderboard")
async def load_global_leaderboard(payload: UserLeaderboardRequest):
    """Route handler that returns users on the global leaderboard via helper logic."""
    return get_global_leaderboard(payload, engine)

@app.post("/regional-leaderboard")
async def load_regional_leaderboard(payload: UserLeaderboardRequest, token_claims: Annotated[dict, Depends(get_current_user)]):
    """Route handler that returns users on the global leaderboard via helper logic."""
    user_id = token_claims.get('sub')
    return get_regional_leaderboard(user_id, payload, engine)

@app.post("/user-count")
async def get_user_count(token_claims: Annotated[dict, Depends(get_current_user)]):
    """Route handler that gets user count via helper logic."""
    logging.info(f"User {token_claims.get('sub')} user count request")
    return get_count_user(engine)

@app.post("/add-global-user-pts")
async def add_user_global_points_router(payload: UserPointAddRequest, token_claims: Annotated[dict, Depends(get_current_user)]):
    """Route handler that adds global points to user via helper logic."""
    user_id = token_claims.get('sub')
    logging.info(f"User {user_id} add global points request")
    add_points = payload.add_points
    return add_user_global_points(user_id, add_points, engine)

@app.post("/google/auth")
async def google_auth(auth: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    """Route handler that attempts to decode and authenticate Google user with their token."""
    token = auth.credentials
    return await auth_google_account(token, engine)

@app.post("/google/register")
async def google_auth(payload: GoogleUserRegisterRequest, auth: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    """Route handler that attempts to record user Google data via helper logic."""
    token = auth.credentials
    return add_google_account(token, payload, engine)

@app.post("/pwd-reset/otp-request")
async def google_auth(payload: UserPasswordResetRequest, backgroundTasks: BackgroundTasks):
    """Route handler that sends the user a password reset one time password via helper logic."""
    return password_reset_mail_request(payload, engine, backgroundTasks)

@app.post("/pwd-reset/otp-check")
async def google_auth(payload: UserOTPVerifyRequest):
    """Route handler that attempts to check and verify the user's one time password via helper logic."""
    return user_has_otp(payload, engine)

@app.post("/user-points")
async def get_user_points_router(token_claims: Annotated[dict, Depends(get_current_user)]):
    """Route handler that returns a users global points"""
    user_id = token_claims.get('sub')
    return get_user_points(user_id, engine)

# @app.get("/friends")
# def get_friends_router(token_claims: Annotated[dict, Depends(get_current_user)]):
#     user_id = int(token_claims.get("sub"))
#     return get_friends(user_id=user_id, engine=engine)

# @app.post("/friends/add")
# def add_friend_router(payload: FriendAddRequest, token_claims: Annotated[dict, Depends(get_current_user)]):
#     user_id = int(token_claims.get("sub"))
#     return add_friend(payload=payload, user_id=user_id, engine=engine)

@app.post('/username')
async def get_username_router(token_claims: Annotated[dict, Depends(get_current_user)]):
    """Route handler that returns a users username"""
    user_id = token_claims.get('sub')
    return get_username(user_id, engine)

@app.post("/set-user-badge")
async def set_user_badge_router(payload: UserBadgeSetRequest, token_claims: Annotated[dict, Depends(get_current_user)]):
    """Route handler that sets a user's selected badge."""
    user_id = token_claims.get('sub')
    badge_file_path = payload.badge_file_path
    return set_user_badge(user_id, badge_file_path, engine)

@app.post('/get-user-badge')
async def get_user_badge_router(token_claims: Annotated[dict, Depends(get_current_user)]):
    """Route handler that returns a Flutter file path to a user's badge."""
    user_id = token_claims.get('sub')
    return get_user_badge(user_id, engine)

@app.post('/get-user-region')
async def get_user_region_router(token_claims: Annotated[dict, Depends(get_current_user)]):
    """Route handler that returns a user region."""
    user_id = token_claims.get('sub')
    return get_user_region(user_id, engine)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=HOST,
        port=PORT,
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )
