from __future__ import annotations

import os
from typing import Any, Dict

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from fastapi import HTTPException

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.requests import IncorrectIdentificationRequest
from app.db.plant_species import get_species_id


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
        Confirmation payload mirroring the created row, including a presigned S3 upload URL.

    Raises
    ------
    HTTPException
        If validation fails, referenced rows are missing, or database errors occur.
    """
    correct_species_id = get_species_id(payload.correct_species, engine=engine)
    incorrect_species_id = get_species_id(payload.incorrect_species, engine=engine)

    try:
        presigned_url = create_presigned_url(str(payload.identification_id))
    except ClientError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate upload URL: {exc}",
        ) from exc

    if correct_species_id == incorrect_species_id:
        raise HTTPException(status_code=400, detail="Correct and incorrect species IDs must differ.")

    try:
        with engine.begin() as conn:
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
                    "correct_species_id_in": correct_species_id,
                    "inc_species_id_in": incorrect_species_id,
                },
            )

            return {
                "identification_id": payload.identification_id,
                "correct_species_id": correct_species_id,
                "incorrect_species_id": incorrect_species_id,
                "message": "Incorrect identification recorded.",
                "url": presigned_url,
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


def create_presigned_url(object_key: str, expiration: int = 3600) -> str:
    """Generate a presigned S3 PUT URL for the identiflora-images bucket."""
    s3 = boto3.client(
        "s3",
        region_name="us-west-1",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        config=Config(signature_version="s3v4"),
    )
    return s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": "identiflora-images", "Key": object_key},
        ExpiresIn=expiration,
        HttpMethod="PUT",
    )
