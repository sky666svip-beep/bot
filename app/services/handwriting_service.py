import torch
import torch.nn as nn
import torchvision.transforms as transforms
from PIL import Image
import io
import base64
import numpy as np
import os

# Define the same model architecture as in training
class EMNISTCNN(nn.Module):
    def __init__(self, num_classes=62):
        super(EMNISTCNN, self).__init__()
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

class HandwritingService:
    def __init__(self, model_path='ml/models/emnist_cnn.pth'):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = EMNISTCNN(num_classes=62).to(self.device)
        self.model_path = model_path
        self.model_loaded = False
        
        # Mapping for EMNIST ByClass: 0-9, A-Z, a-z
        self.classes = (
            [str(i) for i in range(10)] + 
            [chr(i) for i in range(ord('A'), ord('Z') + 1)] + 
            [chr(i) for i in range(ord('a'), ord('z') + 1)]
        )

        self._load_model()

    def _load_model(self):
        if os.path.exists(self.model_path):
            try:
                self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
                self.model.eval()
                self.model_loaded = True
                print(f"Handwriting model loaded from {self.model_path}")
            except Exception as e:
                print(f"Failed to load model: {e}")
        else:
            print(f"Model file not found at {self.model_path}")

    def preprocess_image(self, image_data):
        """
        Convert base64 or bytes image to tensor suitable for model
        input: White background, black text (Canvas default)
        model expects: Black background, white text (EMNIST default)
        """
        if isinstance(image_data, str) and ',' in image_data:
            image_data = base64.b64decode(image_data.split(',')[1])
        
        image = Image.open(io.BytesIO(image_data)).convert('L')
        
        # Resize to 28x28
        image = image.resize((28, 28), Image.Resampling.BILINEAR)
        
        # Invert colors (Canvas is white bg, black ink -> EMNIST is black bg, white ink)
        # Use numpy to invert
        img_array = np.array(image)
        img_array = 255 - img_array
        image = Image.fromarray(img_array)
        
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize((0.1307,), (0.3081,))
        ])
        
        return transform(image).unsqueeze(0).to(self.device)

    def predict(self, image_data, top_k=3):
        if not self.model_loaded:
            self._load_model()
            if not self.model_loaded:
                return {"error": "Model not loaded"}

        try:
            tensor = self.preprocess_image(image_data)
            
            with torch.no_grad():
                outputs = self.model(tensor)
                probabilities = torch.nn.functional.softmax(outputs, dim=1)
                
                top_prob, top_idx = torch.topk(probabilities, top_k)
                
                results = []
                for i in range(top_k):
                    idx = top_idx[0][i].item()
                    prob = top_prob[0][i].item()
                    results.append({
                        "char": self.classes[idx],
                        "confidence": float(f"{prob:.4f}")
                    })
                
                return results
                
        except Exception as e:
            print(f"Prediction error: {e}")
            return {"error": str(e)}

# Singleton instance
handwriting_service = HandwritingService()
