from sqlalchemy.engine import Engine
from sqlalchemy import create_engine

from fastapi import HTTPException

from urllib.parse import quote_plus

import os

DATABASE_NAME = 'identiflora_db'

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
        password = quote_plus(os.getenv("DB_PASSWORD"))
        host = os.getenv("DB_HOST")
        port = os.getenv("DB_PORT")
        db_name = os.getenv("DB_NAME", DATABASE_NAME)
        # Using PyMySQL dialect for compatibility.
        url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"
        return create_engine(url, future=True, pool_pre_ping=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Could not create database engine: {exc}") from exc