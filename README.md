## Database API (FastAPI)
The Python API in `Database/api/database_api.py` exposes a minimal endpoint to record incorrect identifications in MySQL.

### Requirements
- Python 3.10+
- Install dependencies:
  ```bash 
  pip install -r requirements.txt
  ```
- Running MySQL instance with the schema from `Database/schema/initialize_database.sql`

### Configuration
Connection settings are read from environment variables (defaults in parentheses):
- `DB_HOST` (`localhost`)
- `DB_PORT` (`3306`)
- `DB_USER` (`root`)
- `DB_PASSWORD` (from `Database/api/database_password.txt` if not set)
- `DB_NAME` (`identiflora_testing_db`)
- `PORT` (`8000`, only for the dev server in `__main__`)

### Run locally
Start the API (from repo root):
```
uvicorn Database.api.database_api:app --host localhost --port 8000
```
or run the file directly, change the global variable HOST to desired host: `python Database/api/database_api.py`

### Endpoint: Report incorrect identification
- **Method/Path**: `POST /incorrect-identifications`
- **Purpose**: Record that a specific identification submission was wrong, linking the correct and incorrect species.
- **Request body** (`application/json`):
  ```
  {
    "identification_id": 1,
    "correct_species_id": 2,
    "incorrect_species_id": 3
  }
  ```
  - `identification_id`: Must already exist in `identification_submission`.
  - `correct_species_id` / `incorrect_species_id`: Must exist in `plant_species` and cannot be equal.
  - `incorrect_species_id` must also exist as an option in `identification_option` for that `identification_id` (composite FK).
- **Behavior**:
  - Validates referenced submission and species; ensures the incorrect species is one of the submission's options.
  - Inserts into `incorrect_identification` with `time_submitted = NOW()`; image URLs are available via joins if needed.
- **Responses** (examples):
  - `200 OK`:
    ```
    {
      "identification_id": 1,
      "correct_species_id": 2,
      "incorrect_species_id": 3,
      "message": "Incorrect identification recorded."
    }
    ```
  - `404 Not Found`: Missing submission or species rows.
  - `400 Bad Request`: Correct/incorrect species are the same, or required image URLs are missing.
  - `409 Conflict`: An incorrect identification already exists for this submission.
  - `500 Internal Server Error`: Database/connectivity issues.

### Endpoint: Get plant species img url
- **Method/Path**: `GET /plant-species-url`
- **Purpose**: Retrieve url associated with a certain plant species scientific name
- **Parameters**:
  - scientific_name: scientific name associated with the desired plant img_url
  - host: host associated with image server (same as api)
  - port: port associated with image server (same as api)
  - img_path: path to images. Currently '/plant-images'
  - engine: Engine
- **Behavior**:
  - Returns a working img_url that can be used to download or view the image
