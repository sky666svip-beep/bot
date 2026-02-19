from paddleocr import PaddleOCR
import cv2
import numpy as np
import base64
import io
from PIL import Image

class PaddleService:
    def __init__(self):
        print("Initializing PaddleOCR (this may take a while to download models on first run)...")
        # use_angle_cls=True: Detect rotated text
        # lang='ch': Chinese & English model (Good for mixed formulas)
        # device='gpu': Enable GPU acceleration (newer paddlex style)
        # ocr_version: Removed to use default Server model (better accuracy)
        try:
            self.ocr = PaddleOCR(use_angle_cls=True, lang="ch", device='gpu')
        except ValueError:
            # Fallback if device arg is also not supported, try without
             print("Warning: GPU init failed, falling back to CPU or auto-detect")
             self.ocr = PaddleOCR(use_angle_cls=True, lang="ch")
        print("PaddleOCR Initialized.")

    def preprocess_image(self, base64_str):
        if not base64_str:
            return None
            
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]
        
        try:
            image_data = base64.b64decode(base64_str)
            image = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB (Paddle expects RGB/BGR)
            img_np = np.array(image.convert('RGB'))
            
            # Convert RGB to BGR (OpenCV standard, just in case, though Paddle might handle RGB)
            # PaddleOCR uses cv2.imread which is BGR. Let's provide BGR.
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            return img_bgr
        except Exception as e:
            print(f"Image processing error: {e}")
            return None

    def recognize_formula(self, image_data_base64):
        img_array = self.preprocess_image(image_data_base64)
        if img_array is None:
            return "Error: Invalid image"
            
        # Run OCR
        # cls=True enables angle classification
        # With newer paddleocr/paddlex, cls arg might be implicit or different
        try:
             result = self.ocr.ocr(img_array, cls=True)
        except TypeError:
             # Fallback if cls arg is not supported
             result = self.ocr.ocr(img_array)
        
        # PaddleOCR returns None or empty list if nothing found
        if not result or result[0] is None:
            return ""
            
        # Parse results
        # New PaddleOCR/PaddleX structure: [{'rec_texts': ['text1', ...], 'rec_scores': [...]}, ...]
        detected_texts = []
        for res in result:
            # res is a dictionary for each image
            if isinstance(res, dict) and 'rec_texts' in res:
                texts = res['rec_texts']
                if texts:
                    detected_texts.extend(texts)
            elif isinstance(res, list): 
                # Fallback for old list structure [[box, (text, score)], ...]
                for prediction in res:
                    if isinstance(prediction, (list, tuple)) and len(prediction) >= 2:
                        text_content = prediction[1][0]
                        detected_texts.append(text_content)
        
        # Join with space
        full_text = " ".join(detected_texts)
        return full_text

# Singleton instance
paddle_service = PaddleService()
