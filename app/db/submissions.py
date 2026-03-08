from __future__ import annotations
from sqlalchemy import text
import logging

from app.models.requests import PlantSubmissionRequest

def record_plant_submission(payload: PlantSubmissionRequest, user_id: int, engine):
    """
    Records a plant submission using database procedures and hopefully works now
    """
    try:
        with engine.begin() as conn:
            sub_result = conn.execute(
                text("CALL add_identification_submission(:uid, :lat, :lon, :img)"),
                {
                    "uid": user_id, 
                    "lat": payload.latitude, 
                    "lon": payload.longitude, 
                    "img": payload.img_url or ""
                }
            ).first()
            submission_id = sub_result.identification_id
            
            first_option_id = None

            for rank_idx, class_idx in enumerate(payload.prediction_ids):
                db_species_id = class_idx + 1 
                
                opt_result = conn.execute(
                    text("CALL add_identification_option(:iid, :sid, :rank)"),
                    {
                        "iid": submission_id, 
                        "sid": db_species_id, 
                        "rank": rank_idx + 1
                    }
                ).first()

                # Capture the database ID of the top-ranked prediction
                if rank_idx == 0:
                    first_option_id = opt_result.option_id

            if first_option_id:
                conn.execute(
                    text("CALL add_identification_result(:iid, :uid, :oid)"),
                    {"iid": submission_id, "uid": user_id, "oid": first_option_id}
                )

            return {"success": True, "identification_id": submission_id}
            
    except Exception as e:
        logging.error(f"Error recording submission for user {user_id}: {e}")
        return {"success": False, "error": str(e)}

def get_submission_history(user_id: int, engine) -> list:
    """
    Fetches all of a user's past plant submissions by calling the get_user_submission_history procedure
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("CALL get_user_submission_history(:uid)"), 
                {"uid": user_id}
            ).fetchall()
            
            history = []
            for row in result:
                history.append({
                    "identification_id": row.identification_id,
                    "time_submitted": str(row.time_submitted),
                    "latitude": float(row.latitude) if row.latitude else 0.0,
                    "longitude": float(row.longitude) if row.longitude else 0.0,
                    "species_name": row.common_name if row.common_name else row.scientific_name,
                    "scientific_name": row.scientific_name,
                    "submission_img": row.submission_img,
                    "species_img": row.species_img
                })
            return history
    except Exception as e:
        logging.error(f"Failed to fetch history for user {user_id}: {e}")
        return []