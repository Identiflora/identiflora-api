#!/usr/bin/env python3
from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database_api_helpers import build_engine, IncorrectIdentificationRequest, record_incorrect_identification, get_plant_species_url

HOST = "localhost"
PORT = 8000

PLANT_IMG_LOC = '/Users/jackson/Classes/plant-images'
PLANT_IMG_PATH = '/plant-images'

app = FastAPI(
    title="Identiflora Database API",
    version="0.1.0",
    description="Minimal API for interacting with the Identiflora MySQL database.",
)

engine = build_engine()


@app.post("/incorrect-identifications")
def add_incorrect_identification(payload: IncorrectIdentificationRequest):
    """Route handler that records an incorrect identification via helper logic."""
    return record_incorrect_identification(payload, engine)

@app.get("/plant-species-url")
def get_plant_species_url_router(sci_name: str):
    """Route handler that records a plant species img url request via helper logic."""
    return get_plant_species_url(sci_name, HOST, PORT, PLANT_IMG_PATH, engine)

# directory containing plant images. Calls to api: http://localhost:8000/plant-images/API_test_img.png
app.mount(
    "/plant-images",
    StaticFiles(directory=PLANT_IMG_LOC)
)


if __name__ == "__main__":
    uvicorn.run(
        "database_api:app",
        host=HOST,
        port=PORT,
        reload=False,
    )
