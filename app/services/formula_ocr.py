import cv2
import numpy as np
import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image
import os
import base64
import io

# Model Definition (Must match training script)
class FormulaCNN(nn.Module):
    def __init__(self, num_classes):
        super(FormulaCNN, self).__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            nn.Dropout(0.25)
        )
        self.classifier = nn.Sequential(
            nn.Linear(128 * 7 * 7, 256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, num_classes)
        )

    def forward(self, x):
        x = self.features(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x

class FormulaOCR:
    def __init__(self, model_path='ml/models/formula_cnn.pth'):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model_path = model_path
        self.model = None
        self.symbol_map = {}
        self.loaded = False
        
        # EMNIST Classes (0-61)
        self.emnist_chars = (
            [str(i) for i in range(10)] + 
            [chr(i) for i in range(ord('A'), ord('Z') + 1)] + 
            [chr(i) for i in range(ord('a'), ord('z') + 1)]
        )

    def load_model(self):
        if not os.path.exists(self.model_path):
            print("Formula model not found.")
            return False
            
        try:
            checkpoint = torch.load(self.model_path, map_location=self.device)
            # Checkpoint format: {model_state_dict, num_classes, symbol_map}
            
            num_classes = checkpoint.get('num_classes', 71) # Default to 62+9 if not stored
            self.model = FormulaCNN(num_classes).to(self.device)
            self.model.load_state_dict(checkpoint['model_state_dict'])
            self.model.eval()
            
            self.symbol_map = checkpoint.get('symbol_map', {})
            # Reverse symbol map: ID -> LaTeX
            self.id_to_latex = {v: k for k, v in self.symbol_map.items()}
            
            self.loaded = True
            print("Formula OCR model loaded.")
            return True
        except Exception as e:
            print(f"Error loading formula model: {e}")
            return False

    def decode_label(self, label_idx):
        if label_idx < 62:
            return self.emnist_chars[label_idx]
        else:
            return self.id_to_latex.get(label_idx, '?')

    def preprocess_image(self, base64_str):
        if ',' in base64_str:
            base64_str = base64_str.split(',')[1]
        
        image_data = base64.b64decode(base64_str)
        image = Image.open(io.BytesIO(image_data))
        
        # Convert to CV2 format (RGB) then Grayscale
        # PIL (RGB) -> CV2 (BGR)
        img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
        
        # Threshold: Assuming white background, black ink
        # Invert -> Black background, white ink
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
        
        return thresh

    def segment_characters(self, thresh_img):
        # Find contours
        contours, _ = cv2.findContours(thresh_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter small noise
        valid_contours = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w * h > 50: # Minimum area
                valid_contours.append((x, y, w, h, cnt))
        
        # Sort by X coordinate (Left to Right)
        valid_contours.sort(key=lambda x: x[0])
        
        # Extract ROIs
        rois = []
        for (x, y, w, h, cnt) in valid_contours:
            # Crop
            roi = thresh_img[y:y+h, x:x+w]
            
            # Make it square with padding (preserve aspect ratio)
            max_dim = max(w, h)
            pad_w = (max_dim - w) // 2
            pad_h = (max_dim - h) // 2
            
            # Add extra padding for better recognition (centering)
            # Create a black square canvas
            square_size = max_dim + 20 
            canvas = np.zeros((square_size, square_size), dtype=np.uint8)
            
            # Paste constraints
            start_y = (square_size - h) // 2
            start_x = (square_size - w) // 2
            canvas[start_y:start_y+h, start_x:start_x+w] = roi

            rois.append(canvas)
            
        return rois

    def identify_chars(self, rois):
        if not self.loaded:
            if not self.load_model():
                return []
        
        transform = transforms.Compose([
            transforms.Resize((28, 28)),
            transforms.ToTensor(),
            transforms.Normalize((0.1307,), (0.3081,))
        ])
        
        dataset = []
        for roi in rois:
            # ROI is numpy array (uint8). Convert to PIL
            pil_img = Image.fromarray(roi)
            tensor = transform(pil_img)
            dataset.append(tensor)
            
        if not dataset:
            return []
            
        batch = torch.stack(dataset).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(batch)
            _, predicted = torch.max(outputs, 1)
            
        results = []
        for idx in predicted:
            char = self.decode_label(idx.item())
            results.append(char)
            
        return results

    def recognize_formula(self, base64_image):
        thresh = self.preprocess_image(base64_image)
        rois = self.segment_characters(thresh)
        chars = self.identify_chars(rois)
        
        # Simple Join
        # Advanced: Detect sup/sub scripts based on Y deviations
        formula = "".join(chars)
        
        # Post-processing replacements
        # E.g. replace 's' 'q' 'r' 't' with \sqrt if separate
        # But our model predicts tokens.
        
        # Correct LaTeX formatting
        # e.g. \plus -> +
        clean_formula = formula.replace(r'\plus', '+').replace(r'\minus', '-').replace(r'\ast', '*').replace(r'\forwardslash', '/').replace(r'\equal', '=')
        clean_formula = clean_formula.replace(r'\lp', '(').replace(r'\rp', ')')
        
        return clean_formula

# Singleton
formula_ocr = FormulaOCR()
