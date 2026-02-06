from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.requests import PlantSpeciesRequest

def record_plant_species(payload: PlantSpeciesRequest, engine: Engine) -> Dict[str, Any]:
    """
    Add a new plant species to database

    Parameters
    ----------
    payload : PlantSpeciesRequest
        Request data containing common_name, scientific_name, genus, and img_url

    Returns
    -------
    dict
        Confirmation payload mirroring the created row.

    Raises
    ------
    HTTPException
        If validation fails, referenced rows are missing, or database errors occur.
    """

    try:
        with engine.begin() as conn:

            # Read-only duplicate guard to avoid multiple plant species of same type.
            existing = conn.execute(
                text("CALL check_plant_species_exists(:scientific_name_in)"),
                {"scientific_name_in": payload.scientific_name},
            ).first()

            if existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail="This plant species already exists in the database.",
                )

            # Write: insert the new plant species record.
            conn.execute(
                text("CALL add_plant_species(:common_name_in, :scientific_name_in, :genus_in, :img_url_in)"),
                {
                    "common_name_in": payload.common_name,
                    "scientific_name_in": payload.scientific_name,
                    "genus_in": payload.genus,
                    "img_url_in": payload.img_url,
                },
            )

            return {
                    "common_name_in": payload.common_name,
                    "scientific_name_in": payload.scientific_name,
                    "genus_in": payload.genus,
                    "img_url_in": payload.img_url,
                }

    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="This plant species already exists.",
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while adding a new plant species: {exc}",
        ) from exc

def get_plant_species_url(scientific_name: str, engine: Engine) -> str:
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
            payload = {"scientific_name": scientific_name}
            row = conn.execute(text('CALL get_plant_species_img_url(:scientific_name)'), payload).first()
            if row is None:
                raise HTTPException(status_code=404, detail="Plant species not found.")
            return row['img_url']
        
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching plant species URL: {exc}",
        ) from exc