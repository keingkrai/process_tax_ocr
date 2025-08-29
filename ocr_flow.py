import re
import os
from typhoon_ocr import ocr_document
from dotenv import load_dotenv
from openai import OpenAI
from PyPDF2 import PdfReader
from collections import defaultdict
from prepro import ImageProcessor

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