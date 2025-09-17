from rapidfuzz import fuzz
import re, json

# ไม่จำเป็นต้องใช้ Selenium, TimeoutException, หรือ time อีกต่อไป

class FindInvoiceCompany:
    def __init__(self, input_json: dict, file_name: str, num: int, fuzzy_threshold: int = 95):
        self.data = input_json.get("json", input_json)
        self.file_name = file_name
        self.page = num
        self.fuzzy_threshold = fuzzy_threshold

    def _normalize_tax_id(self, tax_id: str) -> str:
        return re.sub(r"\D", "", tax_id or "")

    def invoice_company(self) -> dict:
        tax_id_raw = self.data.get("tax_id")
        tax_id = self._normalize_tax_id(tax_id_raw)
        
        # 1. ตรวจสอบความถูกต้องของ Tax ID ก่อนเป็นอันดับแรก (ยังคงเป็นสิ่งที่ดี)
        if not tax_id or len(tax_id) != 13:
            self._write_out(verified={
                "matched": None,
                "seller_from_receipt": (self.data.get("seller") or "").strip(),
                "seller_from_tax_id": None, # ทำให้สอดคล้องกันว่าไม่มีข้อมูลจาก Tax ID
                "reason": "invalid_or_missing_tax_id"
            })
            return self.data
        
        # 2. ลบ try...except...finally ที่ไม่จำเป็นออกทั้งหมด
        # เพราะการทำงานส่วนนี้ปลอดภัยและไม่เกิด Error ร้ายแรง
        
        print(f"--- [Page {self.page}] Comparing names for Tax ID: {tax_id} ---")

        # 3. ดึงข้อมูลชื่อจากใบเสร็จ และชื่อที่ได้จาก Tax ID (ที่ส่งมาใน input)
        seller_name = (self.data.get("seller") or "").strip()
        company_name_from_tax_id = (self.data.get("name_company") or "").strip()
        
        # 4. ทำการเปรียบเทียบชื่อโดยตรง
        # ถ้าไม่มีชื่อบริษัทที่ส่งมาด้วย ให้ similarity เป็น 0
        similarity = fuzz.ratio(company_name_from_tax_id, seller_name) if company_name_from_tax_id else 0
        
        verified = {
            "matched": similarity >= self.fuzzy_threshold,
            "seller_from_receipt": seller_name,
            "seller_from_tax_id": company_name_from_tax_id # ใช้ชื่อที่ได้รับมาโดยตรง
        }
        
        self._write_out(verified=verified)
        print(f"--- [Page {self.page}] Comparison finished. ---")
        return self.data

    def _write_out(self, verified: dict):
        self.data["verified_seller_name"] = verified
        out_path = f"{self.file_name}_output_page_{self.page}.json"
        # with open(out_path, "w", encoding="utf-8") as f:
        #     json.dump(self.data, f, ensure_ascii=False, indent=2)
