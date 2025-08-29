import mimetypes
import cv2
import re
import os
from typhoon_ocr import ocr_document
from dotenv import load_dotenv
from openai import OpenAI
from PyPDF2 import PdfReader
from collections import defaultdict
from pdf2image import convert_from_path

#python 3.12.1

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
        
class OCRService:
    def __init__(self):
        load_dotenv()
        self.client = OpenAI(
            api_key=os.getenv("TYPHOON_OCR_API_KEY"),
            base_url="https://api.opentyphoon.ai/v1"
        )

    def run_ocr(self, image_path):
        return ocr_document(
            pdf_or_image_path=image_path,
            task_type="default",
            page_num=1
        )
        
class TransactionExtractor:
    def __init__(self, ocr_service, output_dir="output", dpi=300):
        self.ocr_service = ocr_service
        self.data = defaultdict(list)
        self.output_dir = output_dir
        self.dpi = dpi
        os.makedirs(self.output_dir, exist_ok=True)

    def process_document(self, file_handler):
        file_type = file_handler.check_file_type()

        if file_type == "pdf":
            images = file_handler.pdf_to_images(dpi=self.dpi)
        elif file_type == "image":
            images = [file_handler.filepath]
        else:
            raise ValueError("ไฟล์ไม่รองรับ")
        
        print(images)

        for i, img in enumerate(images):
            try:
                if file_type == "pdf":
                    img_path = os.path.join(
                        self.output_dir,
                        f"{os.path.splitext(os.path.basename(file_handler.filepath))[0]}_page_{i+1}.png"
                    )
                    img.save(img_path, "PNG")                     
                else:
                    ext = os.path.splitext(file_handler.filepath)[1].lower()
                    img_path = os.path.join(
                        self.output_dir,
                        f"{os.path.splitext(os.path.basename(file_handler.filepath))[0]}{ext}"
                    )
                    if file_handler.filepath != img_path:
                        import shutil
                        shutil.copy(file_handler.filepath, img_path)

                    

                ImageProcessor.preprocess_image(img_path, img_path)
                markdown = self.ocr_service.run_ocr(img_path)
                tid = self.extract_transaction_id(markdown, f"unknown_{i+1}")
                self.data[tid].append(markdown)

            except Exception as e:
                print(f"❌ Error processing page {i+1}: {e}")

        return self.data
    
    @staticmethod
    def extract_transaction_id(text, default_value):
        """
        ดึงหมายเลขธุรกรรมจากข้อความ OCR
        """
        match = re.search(
            r"(?:เลขที่|Transaction\s*No|Ref|หมายเลขธุรกรรม)[:\s]*([A-Z0-9\-\/]+)",
            text, re.IGNORECASE
        )
        if match:
            return match.group(1).strip()
        return default_value
    