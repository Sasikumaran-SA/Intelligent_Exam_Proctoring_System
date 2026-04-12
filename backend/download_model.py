import os
import requests
import zipfile
import io

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_DIR = "model"

def download_and_extract():
    if os.path.exists(MODEL_DIR):
        print(f"Model directory '{MODEL_DIR}' already exists. Skipping download.")
        return

    print(f"Downloading model from {MODEL_URL}...")
    response = requests.get(MODEL_URL)
    if response.status_code == 200:
        print("Download successful. Extracting...")
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
            zip_ref.extractall(".")
        
        # Rename the extracted folder to 'model' for easier access
        extracted_folder = "vosk-model-small-en-us-0.15"
        if os.path.exists(extracted_folder):
            os.rename(extracted_folder, MODEL_DIR)
        print("Success! Model is ready in 'backend/model'.")
    else:
        print(f"Failed to download model. Status code: {response.status_code}")

if __name__ == "__main__":
    download_and_extract()
