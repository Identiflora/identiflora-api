from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import HTTPException

from sqlalchemy import text
from sqlalchemy.engine import Engine, Row
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from datetime import datetime, timedelta, timezone
from jose import jwt

DATABASE_PASSWORD_PATH = "database_password.txt"
DATABASE_NAME = "identiflora_db"



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


# def build_base_url(host: str, port: int, path: str):
#     """
#     Construct a base url from the host, port, and path
    
#     Parameters
#     --------------------
#     host: str
#         host for the url
#     port: int
#         port for the url
#     path: str
#         path to desired location
    
#     Returns
#     ---------------------
#     str
#         url of format: http://host:port/path

#     """
#     path = path.lstrip('/')
#     host_port = f'{host}:{port}'
#     return os.path.join('http://', host_port, path)