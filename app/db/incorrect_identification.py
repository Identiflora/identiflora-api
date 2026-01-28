from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.requests import IncorrectIdentificationRequest


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