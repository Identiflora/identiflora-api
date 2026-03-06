from fastapi import requests

# Point this to your locally running FastAPI server
API_URL = "http://localhost:8000/plant-species"

def load_plants(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    for line in lines:
        scientific_name = line.strip()
        
        # Skip empty lines (even though there shouldnt be any tbh)
        if not scientific_name:
            continue
            
        # Extract the Genus (The first word of the scientific name)
        genus = scientific_name.split(" ")[0]
        
        # Create a unique placeholder image URL to satisfy the img url field in the database

        safe_name = scientific_name.replace(' ', '_').lower()
        unique_img_url = f"https://placeholder.identiflora.app/{safe_name}.jpg"

        # Payload Creation
        payload = {
            "scientific_name": scientific_name,
            "genus": genus,
            "common_name": "Unknown",  # Placeholder for now
            "img_url": unique_img_url
        }

        # Send it to your FastAPI backend
        try:
            response = requests.post(API_URL, json=payload)
            if response.status_code >= 200 and response.status_code < 300:
                print(f"Successfully added: {scientific_name}")
            else:
                print(f"Failed to add {scientific_name}: {response.text}")
        except requests.exceptions.ConnectionError:
            print("Could not connect to the API.")
            break

if __name__ == "__main__":
    # Filepath to the labels file in identiflora "flutter-app/assets/model/labels.txt" is the in repo filepath
    load_plants("C:/temp/flutter-app/assets/model/labels.txt")