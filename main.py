#!/usr/bin/env python3
from __future__ import annotations

from dotenv import load_dotenv

import uvicorn

from fastapi import FastAPI, BackgroundTasks, Depends
from typing import Annotated

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models.requests import IncorrectIdentificationRequest, PlantSpeciesRequest, UserRegistrationRequest, UserLoginRequest, UserGlobalLeaderboardRequest, UserPointAddRequest, GoogleUserRegisterRequest, UserPasswordResetRequest, UserOTPVerifyRequest

from app.auth.login_signup import auth_google_account, add_google_account, user_login, record_user_registration, user_has_otp
from app.auth.token import get_current_user

from app.core.db_connection import build_engine
from app.core.users import get_global_leaderboard, get_count_user, add_user_global_points, password_reset_mail_request

from app.db.incorrect_identification import record_incorrect_identification
from app.db.plant_species import record_plant_species, get_plant_species_url

import logging
logging.basicConfig(level=logging.INFO)

HOST = "localhost"
PORT = 8000



load_dotenv()

app = FastAPI(
    title="Identiflora Database API",
    version="0.1.0",
    description="Minimal API for interacting with the Identiflora MySQL database.",
)

engine = build_engine()

@app.post("/incorrect-identifications")
def add_incorrect_identification(payload: IncorrectIdentificationRequest, token_claims: Annotated[dict, Depends(get_current_user)]):
    """Route handler that records an incorrect identification via helper logic."""
    logging.info(f"Incorrect identification recorded by user {token_claims.get('sub')}: {payload.identification_id}")
    return record_incorrect_identification(payload, engine)

@app.post("/plant-species")
def add_plant_species(payload: PlantSpeciesRequest):
    """Route handler that records a new plant species via helper logic."""
    logging.info("HIT /plant-species: %s", payload.scientific_name)
    return record_plant_species(payload, engine)

@app.get("/plant-species-url/{scientific_name}")
def get_plant_species_url_router(scientific_name: str): 
    """Route handler that returns a plant species img url using query parameters."""
    return get_plant_species_url(scientific_name, engine)

@app.post("/user/register")
def add_registered_user(payload: UserRegistrationRequest):
    """Route handler that records user registration data via helper logic."""
    return record_user_registration(payload, engine)

@app.post("/user/login")
def login_user(payload: UserLoginRequest):
    """Route handler that records user registration data via helper logic."""
    return user_login(payload, engine)

@app.post("/global-leaderboard")
def load_global_leaderboard(payload: UserGlobalLeaderboardRequest):
    """Route handler that returns users on the global leaderboard via helper logic."""
    return get_global_leaderboard(payload, engine)

@app.post("/user-count")
def get_user_count():
    """Route handler that gets user count via helper logic."""
    return get_count_user(engine)

@app.post("/add-global-user-pts")
def get_user_count(payload: UserPointAddRequest):
    """Route handler that adds global points to user via helper logic."""
    return add_user_global_points(payload, engine)

@app.post("/google/auth")
async def google_auth(auth: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    """Route handler that attempts to decode and authenticate Google user with their token."""
    token = auth.credentials
    return await auth_google_account(token, engine)

@app.post("/google/register")
def google_auth(payload: GoogleUserRegisterRequest, auth: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    """Route handler that attempts to record user Google data via helper logic."""
    token = auth.credentials
    return add_google_account(token, payload, engine)

@app.post("/pwd-reset/otp-request")
def google_auth(payload: UserPasswordResetRequest, backgroundTasks: BackgroundTasks):
    """Route handler that sends the user a password reset one time password via helper logic."""
    return password_reset_mail_request(payload, engine, backgroundTasks)

@app.post("/pwd-reset/otp-check")
def google_auth(payload: UserOTPVerifyRequest):
    """Route handler that attempts to check and verify the user's one time password via helper logic."""
    return user_has_otp(payload, engine)

# directory containing plant images. Calls to api: http://localhost:8000/plant-images/API_test_img.png
# app.mount(
#     "/plant-images",
#     StaticFiles(directory=PLANT_IMG_LOC)
# )

# if __name__ == "__main__":
#     uvicorn.run(
#         "main:app",
#         host=HOST,
#         port=PORT,
#         reload=False,
#     )