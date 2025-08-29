import mimetypes
import cv2
from pdf2image import convert_from_path
from PyPDF2 import PdfReader

class FileHandler:
    
    def __init__(self, filepath):
        self.filepath = filepath
    
    def check_file_type(self):
        mime_type, _ = mimetypes.guess_type(self.filepath)
        if mime_type == "application/pdf":
            return "pdf"
        elif mime_type and mime_type.startswith("image/"):
            return "image"
        else:
            return "unknown"
        
        # ฟังก์ชันนับหน้าจาก PDF
    def count_pages(self):
        reader = PdfReader(self.filepath)
        return len(reader.pages)
    
    def pdf_to_images(self, dpi=300):
        return convert_from_path(self.filepath, dpi=dpi)
    
class ImageProcessor:
    
    @staticmethod
    def preprocess_image(input_path, output_path):
        img = cv2.imread(input_path)
        if img is None:
            raise ValueError(f"❌ ไม่สามารถโหลดภาพจาก: {input_path}")

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Resize 2x (Upscale)
        resized = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        # Adaptive Threshold
        thresh = cv2.adaptiveThreshold(
            resized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        # Invert image
        inverted = cv2.bitwise_not(thresh)

        # Save result
        cv2.imwrite(output_path, inverted)