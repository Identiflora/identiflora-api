from __future__ import annotations

import os
from typing import Any, Dict
from urllib.parse import quote_plus, urljoin

from fastapi import HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Row
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from passlib.hash import bcrypt

DATABASE_PASSWORD_PATH = "database_password.txt"
DATABASE_NAME = "identiflora_testing_db"

# Resolve password from file at import time; environment variable DB_PASSWORD still overrides in build_engine.
try:
    with open(DATABASE_PASSWORD_PATH) as file:
        db_password = file.read().strip()
except FileNotFoundError:
    db_password = ""

class IncorrectIdentificationRequest(BaseModel):
    """
    Request body for reporting an incorrect identification.
    """

    identification_id: int = Field(..., gt=0, description="FK to identification_submission")
    correct_species_id: int = Field(..., gt=0, description="Species that should have been returned")
    incorrect_species_id: int = Field(..., gt=0, description="Species the model predicted")

class PlantSpeciesURLRequest(BaseModel):
    """
    Request body for requesting a plant img url.
    """
    scientific_name: str = Field(..., description="Scientific (Latin) name of the plant to query.")
    host: str = Field(..., description="image server host")
    port: int = Field(..., description="port to access image server")
    img_path: str = Field(..., description="path to access images (eg. /plant-images)")

class UserRegistrationRequest(BaseModel):
    """
    Request body for reporting user registration. Ensures empty strings trigger invalid requests.
    """

    user_email: str = Field(..., min_length=1, description="Email from user input")
    username: str = Field(..., min_length=1, description="Username from user input")
    password_hash: str = Field(..., min_length=1, description="Password hash created by Flutter with user input")

class UserLoginRequest(BaseModel):
    """
    Request body for reporting user login. Ensures empty strings trigger invalid requests.
    """

    user_email: str = Field(..., min_length=1, description="Email from user input")
    password_hash: str = Field(..., min_length=1, description="Password hash created by Flutter with user input")

def build_engine() -> Engine:
    """
    Create a SQLAlchemy engine using environment-driven configuration.

    Returns
    -------
    sqlalchemy.engine.Engine
        Engine configured for the target MySQL database.

    Raises
    ------
    HTTPException
        If engine creation fails.
    """
    try:
        user = quote_plus(os.getenv("DB_USER", "root"))
        password = quote_plus(os.getenv("DB_PASSWORD", db_password))
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "3306")
        db_name = os.getenv("DB_NAME", DATABASE_NAME)
        # Using PyMySQL dialect for compatibility.
        url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"
        return create_engine(url, future=True, pool_pre_ping=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Could not create database engine: {exc}") from exc


def ensure_row(conn, query: str, params: Dict[str, Any], missing_message: str, status: int = 404) -> Row:
    """
    Execute a query and ensure a single row exists.

    Parameters
    ----------
    conn : sqlalchemy.engine.Connection
        Active connection to run the query.
    query : str
        Query that should return exactly one row.
    params : dict
        Parameters for the query.
    missing_message : str
        Error message if no row is found.
    status : int, optional
        HTTP status code to use for the not-found case, by default 404.

    Returns
    -------
    sqlalchemy.engine.Row
        Row data accessible by column name.

    Raises
    ------
    HTTPException
        If the query returns no rows.
    """
    result = conn.execute(text(query), params)
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=status, detail=missing_message)
    return row


def record_incorrect_identification(payload: IncorrectIdentificationRequest, engine: Engine) -> Dict[str, Any]:
    """
    Persist an incorrect identification, validating referenced rows and constraints.

    Parameters
    ----------
    payload : IncorrectIdentificationRequest
        Request data containing identification, correct species, and incorrect species.

    Returns
    -------
    dict
        Confirmation payload mirroring the created row.

    Raises
    ------
    HTTPException
        If validation fails, referenced rows are missing, or database errors occur.
    """
    if payload.correct_species_id == payload.incorrect_species_id:
        raise HTTPException(status_code=400, detail="Correct and incorrect species IDs must differ.")

    try:
        with engine.begin() as conn:
            # Read-only validation of submission existence.
            ensure_row(
                conn,
                "CALL check_ident_id_exists(:id)",
                {"id": payload.identification_id},
                "Identification submission not found.",
            )
            # Read-only validation of species rows.
            ensure_row(
                conn,
                "CALL check_species_id_exists(:id)",
                {"id": payload.correct_species_id},
                "Correct species not found.",
            )
            ensure_row(
                conn,
                "CALL check_species_id_exists(:id)",
                {"id": payload.incorrect_species_id},
                "Incorrect species not found.",
            )

            # Read-only duplicate guard to avoid multiple incorrect records per submission.
            existing = conn.execute(
                text("CALL check_incorrect_sub_exists(:id)"),
                {"id": payload.identification_id},
            ).first()

            if existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail="An incorrect identification has already been recorded for this submission.",
                )

            # Write: insert the incorrect identification record with timestamp.
            conn.execute(
                text("CALL add_incorrect_id(:ident_id_in, :correct_species_id_in, :inc_species_id_in)"),
                {
                    "ident_id_in": payload.identification_id,
                    "correct_species_id_in": payload.correct_species_id,
                    "inc_species_id_in": payload.incorrect_species_id,
                },
            )

            return {
                "identification_id": payload.identification_id,
                "correct_species_id": payload.correct_species_id,
                "incorrect_species_id": payload.incorrect_species_id,
                "message": "Incorrect identification recorded.",
            }

    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="An incorrect identification already exists for this submission.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while creating incorrect identification: {exc}",
        ) from exc



def get_plant_species_url(scientific_name: str, host: str, port: int, img_path: str, engine: Engine) -> str:
    """
    Fetch the image URL for a plant species identified by its scientific name. Assumes img_url is more like img_name (eg. test_img.png).

    Parameters
    ----------
    scientific_name : str
        Scientific (Latin) name of the plant to query.
    host : str
        Host serving the images.
    port : int
        Port for the image server.
    img_path : str
        Path prefix where images are served (e.g. /plant-images).
    engine : sqlalchemy.engine.Engine
        Database engine used to perform the query.

    Returns
    -------
    str
        The img_url associated with the plant species. Url is ready to be executed on return.

    Raises
    ------
    HTTPException
        400 if the name is empty, 404 if not found, 500 for database errors.
    """
    # make sure scientific name has characters and is not an invalid name such as " "
    if not scientific_name or not scientific_name.strip():
        raise HTTPException(status_code=400, detail="Scientific name must be provided.")

    try:
        with engine.connect() as conn:
            row = ensure_row(
                conn,
                """
                CALL get_plant_species_img_url(:scientific_name)
                """,
                {"scientific_name": scientific_name},
                "Plant species not found.",
            )
            # join base path with image name
            img_path = os.path.join(img_path, row['img_url'])
            return build_base_url(host, port, img_path)
        
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching plant species URL: {exc}",
        ) from exc

def build_base_url(host: str, port: int, path: str):
    """
    Construct a base url from the host, port, and path
    
    Parameters
    --------------------
    host: str
        host for the url
    port: int
        port for the url
    path: str
        path to desired location
    
    Returns
    ---------------------
    str
        url of format: http://host:port/path

    """
    path = path.lstrip('/')
    host_port = f'{host}:{port}'
    return os.path.join('http://', host_port, path)

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
                text("CALL get_user(:user_id_in)"),
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
