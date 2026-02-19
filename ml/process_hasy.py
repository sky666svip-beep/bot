import os
import urllib.request
import tarfile
import pandas as pd
from PIL import Image
import torch
import torchvision.transforms as transforms
from tqdm import tqdm
import shutil

# Configuration
HASY_URL = "https://zenodo.org/records/259444/files/HASYv2.tar.bz2"
DATA_DIR = "ml/data"
# Extraction seems to dump files directly into DATA_DIR, not a HASYv2 subfolder
HASY_DIR = DATA_DIR 
PROCESSED_FILE = os.path.join(DATA_DIR, "hasy_processed.pt")

# Symbols we want to extract
# Map LaTeX command to our internal class ID (starting from 62)
# EMNIST has 0-61. So we start from 62.
SYMBOL_MAP = {
    r"\plus": 62,
    r"\minus": 63,
    r"\ast": 64,        # *
    r"\forwardslash": 65, # /
    r"\equal": 66,
    r"\lp": 67,         # (
    r"\rp": 68,         # )
    r"\sqrt": 69,
    # Can add more later: \alpha, \beta, \pi, etc.
}

def download_and_extract():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    tar_path = os.path.join(DATA_DIR, "HASYv2.tar.bz2")
    
    if not os.path.exists(tar_path) and not os.path.exists(HASY_DIR):
        print(f"Downloading HASYv2 from {HASY_URL}...")
        urllib.request.urlretrieve(HASY_URL, tar_path)
        print("Download complete.")
    
    if not os.path.exists(HASY_DIR):
        print("Extracting HASYv2...")
        with tarfile.open(tar_path, "r:bz2") as tar:
            tar.extractall(path=DATA_DIR)
        print("Extraction complete.")

def process_images():
    print("Processing images...")
    
    # Load labels csv
    labels_csv = os.path.join(HASY_DIR, "hasy-data-labels.csv")
    df = pd.read_csv(labels_csv)
    
    # Filter for symbols we want
    # latex column contains the symbol command
    filtered_df = df[df['latex'].isin(SYMBOL_MAP.keys())]
    
    print(f"Found {len(filtered_df)} images for selected symbols.")
    
    # Transformation pipeline
    transform = transforms.Compose([
        transforms.Resize((28, 28)),
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,))
    ])
    
    data = []
    targets = []
    
    # EMNIST is Black Background (ink=255), White Text.
    # HASY is Black Ink on White Background.
    # We need to invert HASY images.
    from PIL import ImageOps

    for idx, row in tqdm(filtered_df.iterrows(), total=len(filtered_df)):
        # HASYv2 structure: hasy-data/image_name.png
        # BUT the csv path column usually includes parent dir 'hasy-data/...'
        # Let's check if we need to join with HASY_DIR or just DATA_DIR
        # Usually extraction creates a folder "HASYv2" or just files.
        # Let's assume standard extraction.
        
        # The tar usually extracts a folder "HASYv2" or similar.
        # We need to be careful about paths.
        
        # Adjust path based on extraction
        # If extraction puts everything in DATA_DIR/HASYv2-1.2/... then we need to find it.
        # For simplicity, let's assume relative path in CSV is correct relative to where we extracted?
        # Actually HASY csv paths are like "hasy-data/v2-00000.png"
        
        # We extracted to DATA_DIR. So likely DATA_DIR/HASYv2-1.2/hasy-data/...
        # Let's search for the image file if simple join fails.
        
        # BETTER: Just use relative path from the dir where csv located.
        img_name = row['path']
        img_path = os.path.join(os.path.dirname(labels_csv), img_name)
        
        if not os.path.exists(img_path):
             # Try one level up?
             continue

        try:
            img = Image.open(img_path).convert('L')
            img = ImageOps.invert(img) # Invert to match EMNIST (White on Black)
            img_tensor = transform(img)
            label = SYMBOL_MAP[row['latex']]
            data.append(img_tensor)
            targets.append(label)
        except Exception as e:
            print(f"Error processing {img_path}: {e}")
        
    # Stack
    data_tensor = torch.stack(data)
    targets_tensor = torch.tensor(targets)
    
    print(f"Saving processed data to {PROCESSED_FILE}...")
    torch.save((data_tensor, targets_tensor, SYMBOL_MAP), PROCESSED_FILE)
    print("Done.")

if __name__ == "__main__":
    download_and_extract()
    process_images()
