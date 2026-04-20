import requests

# Point this to your running FastAPI server
API_URL = "https://identiflora-api.onrender.com/plant-species"

def load_plants(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    for line in lines:
        raw_label = line.strip()
        
        if not raw_label:
            continue
            
        # Split by underscore to isolate Genus, Species, and Author suffixes
        parts = raw_label.split("_")
        
        # Extract and reformat the Scientific Name
        if len(parts) >= 3 and parts[1] == '×':
            # Case for hybrids like Mentha_×_piperita_L -> "Mentha × piperita"
            clean_scientific_name = f"{parts[0]} {parts[1]} {parts[2]}"
            genus = parts[0]
            img_filename = f"{parts[0]}_{parts[2]}"
        elif len(parts) >= 2:
            # Standard case like Acer_negundo_L -> "Acer negundo"
            clean_scientific_name = f"{parts[0]} {parts[1]}"
            genus = parts[0]
            img_filename = f"{parts[0]}_{parts[1]}"
        else:
            # Fallback for single-word labels just in case
            clean_scientific_name = raw_label.replace('_', ' ')
            genus = parts[0]
            img_filename = parts[0]

        # Placeholder image url
        unique_img_url = f"https://placeholder.identiflora.app/{img_filename.lower()}.jpg"

        # Payload Creation
        payload = {
            "scientific_name": clean_scientific_name,
            "genus": genus,
            # Common name is just stubbed to be genus atm
            "common_name": genus,
            "img_url": unique_img_url
        }

        # Send to backend
        try:
            response = requests.post(API_URL, json=payload)
            if 200 <= response.status_code < 300:
                print(f"Successfully added: {clean_scientific_name}")
            else:
                print(f"Failed {clean_scientific_name}: {response.status_code} - {response.text}")
        except requests.exceptions.ConnectionError:
            print("Could not connect to the API.")
            break

if __name__ == "__main__":
    load_plants("C:/temp/flutter-app/assets/model/labels.txt")