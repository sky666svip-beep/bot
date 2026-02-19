import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from app.services.paddle_service import paddle_service
from PIL import Image, ImageDraw, ImageFont
import io
import base64

def test_ocr():
    print("Generating test image...")
    # Create a dummy image with text "1+2=3"
    # White background, black text
    img = Image.new('RGB', (300, 100), color = (255, 255, 255))
    d = ImageDraw.Draw(img)
    
    # Use default font
    try:
        # Drawing text directly
        d.text((50, 25), "1 + 2 = 3", fill=(0,0,0))
    except Exception as e:
        print(e)

    # Convert to base64
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

    print("Sending to PaddleOCR service...")
    try:
        result = paddle_service.recognize_formula(b64)
        print("-" * 30)
        print(f"OCR Result: '{result}'")
        print("-" * 30)
        
        if "1" in result and "2" in result:
            print("SUCCESS: Recognized numbers correctly.")
        else:
            print("WARNING: Result might be inaccurate (could be due to default font rendering).")
            
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    test_ocr()
