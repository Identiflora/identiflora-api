from __future__ import annotations
from sqlalchemy import text
import logging

from app.models.requests import PlantSubmissionRequest

def record_plant_submission(payload: PlantSubmissionRequest, user_id: int, engine):
    try:
        with engine.begin() as conn:
            # Insert into identification_submission
            sub_result = conn.execute(
                text("""
                    INSERT INTO identification_submission (user_id, latitude, longitude, img_url) 
                    VALUES (:uid, :lat, :lon, :img)
                """),
                {"uid": user_id, "lat": payload.latitude, "lon": payload.longitude, "img": payload.img_url}
            )
            submission_id = sub_result.lastrowid
            
            final_option_id = None

            # Loops through payload to get each plant option
            for rank_minus_one, class_idx in enumerate(payload.prediction_ids):
                # Fix off by one difference
                db_species_id = class_idx + 1 
                
                opt_result = conn.execute(
                    text("""
                        INSERT INTO identification_option (identification_id, species_id, option_rank) 
                        VALUES (:iid, :sid, :rank)
                    """),
                    {"iid": submission_id, "sid": db_species_id, "rank": rank_minus_one + 1}
                )

                # Check if this species matches the user's through string comparison
                # Probably a better way of doing this
                species_check = conn.execute(
                    # Has functionality for if we change the main way to refer to the plants by common name
                    text("SELECT species_id FROM plant_species WHERE scientific_name = :n OR common_name = :n"),
                    {"n": payload.user_guess}
                ).first()

                if species_check and species_check.species_id == db_species_id:
                    final_option_id = opt_result.lastrowid

            # Record final result
            if final_option_id:
                conn.execute(
                    text("INSERT INTO identification_result (identification_id, user_id, option_id) VALUES (:iid, :uid, :oid)"),
                    {"iid": submission_id, "uid": user_id, "oid": final_option_id}
                )

            return {"success": True, "identification_id": submission_id}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_submission_history(user_id: int, engine) -> list:
    """
    Fetches all of a user's past plant submissions by joining the submission
    directly to the top AI prediction
    """
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT 
                    s.identification_id,
                    s.time_submitted,
                    s.latitude,
                    s.longitude,
                    s.img_url AS submission_img,
                    p.common_name,
                    p.scientific_name,
                    p.img_url AS species_img
                FROM identification_submission s
                -- Join directly to the AI's #1 choice for every submission
                JOIN identification_option o ON s.identification_id = o.identification_id AND o.option_rank = 1
                JOIN plant_species p ON o.species_id = p.species_id
                WHERE s.user_id = :uid
                ORDER BY s.time_submitted DESC;
            """)
            result = conn.execute(query, {"uid": user_id}).fetchall()
            
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