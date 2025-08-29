import os, re, json
from openai import OpenAI
from dotenv import load_dotenv
from json.decoder import JSONDecodeError


class InvoiceExtractor:
    def __init__(self, markdown):
        load_dotenv()
        self.client = OpenAI(
            api_key=os.getenv("TYPHOON_OCR_API_KEY"),
            base_url="https://api.opentyphoon.ai/v1"
        )
        self.markdown = markdown
        self.invoice_type = self.detect_invoice_type()  # ตรวจชนิดก่อน

        
    def detect_invoice_type(self) -> str:
        text = self.markdown
            # ตรวจสอบประเภทใบกำกับภาษี
        if "ใบกำกับภาษีแบบเต็ม" in text:
            print("✅ เป็นใบภาษีแบบเต็ม")
            return "Full Invoice"
        elif ("ใบกำกับภาษีแบบย่อ" in text) or ("ใบกำกับภาษี" in text):
            print("✅ เป็นใบกำกับภาษีแบบย่อ")
            return "Simple Invoice"
        else:
            print("ไม่ใช่ใบภาษีแบบเต็มหรือใบกำกับภาษีแบบย่อ")
            return "Unknown"
        
    def bulid_prompt(self) -> str:
        return f"""
    ต่อไปนี้คือข้อมูลจากใบเสร็จหรือใบกำกับภาษีที่ผ่านการทำ OCR แล้ว:

    {self.markdown}

    กรุณาวิเคราะห์ข้อความทั้งหมดและดึงข้อมูลสำคัญต่อไปนี้ออกมาในรูปแบบ JSON ห้ามมีการเปลี่ยนแปลงข้อมูลหรือเพิ่มข้อมูลใด ๆ นอกเหนือจากที่ระบุไว้ด้านล่าง:

    - "title": เป็นชื่อหัวเรื่องของเอกสาร
    - "invoice_type": {self.invoice_type} ,หัวข้อนนี้ไม่ต้องเปลี่ยนแปลง ใช้ตามค่าตัวแปล
    - "seller": ชื่อผู้ขาย (ชื่อบริษัทหรือบุคคล)
    - "seller_address": ที่อยู่ผู้ขาย (แยกเป็น number, street, subdistrict, district, province, postal_code)
    - "buyer": ชื่อผู้ซื้อ (ถ้ามี)
    - "buyer_address": ที่อยู่ผู้ซื้อ (แยกเป็น number, street, subdistrict, district, province, postal_code) 
    - "tax_id": เลขประจำตัวผู้เสียภาษี หรือ เลขทะเบียนบริษัท (ต้องมีครบ 13 หลัก เท่านั้น)
    - "date": วันที่ออกใบเสร็จ (แยกเป็น day month year ใช้ปี พ.ศ. เท่านั้น)
    - "invoice_no": เลขที่ใบเสร็จ / เลขที่ใบกำกับ (ถ้ามี)
    - "items": รายการสินค้า (name, quantity, unit_price, total_price ต่อรายการ)
    - "subtotal": ยอดรวมก่อนภาษี
    - "vat": ภาษีมูลค่าเพิ่ม (ถ้ามี)
    - "total": ยอดรวมสุทธิทั้งหมด
    - "amount_text": จำนวนเงินตัวอักษร (เช่น "=ห้าร้อยบาทถ้วน=")
    - "warranty_period": ระยะเวลารับประกัน เอาแค่ตัวเลข(ถ้ามี)

    หากข้อมูลบางส่วนไม่มี ให้ใส่เป็น null หรือเว้นว่างได้ เช่น "buyer": null
    หัวข้อใน JSON จะเป็นตามที่กำหนดไว้ เท่านั้น

    ตอบกลับเป็น JSON เท่านั้น โดยไม่มีคำอธิบายอื่นเพิ่มเติม
    """
       
    @staticmethod
    def _safe_json_loads(text: str) -> dict:
        try:
            return json.loads(text)
        except JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                return json.loads(m.group())
            raise
        
    def typhoon_extract(self) -> dict:
        prompt = self.bulid_prompt()
        resp = self.client.chat.completions.create(
            model="typhoon-v2-70b-instruct",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=1024,
        )
        raw = resp.choices[0].message.content

        fixed = re.sub(
            r'(?<=:\s)(\d{1,3}(?:,\d{3})+(?:\.\d+)?)(?=,|\n|\})',
            lambda m: m.group(1).replace(',', ''),
            raw
        )
        try:
            data = self._safe_json_loads(fixed)
        except Exception:
            data = {"_raw": raw, "_fixed": fixed, "_parse_error": True}

        return {"invoice_type": self.invoice_type, "raw": raw, "fixed": fixed, "json": data}