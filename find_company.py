from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from rapidfuzz import fuzz
import time, re, json

class FindInvoiceCompany:
    def __init__(self, input_json: dict, file_name: str, num: int, fuzzy_threshold: int = 95):
        # input_json ควรเป็น dict “ตัวในสุด” แล้ว (ไม่ใช่ wrapper)
        self.data = input_json.get("json", input_json)  # รองรับทั้งกรณีมี key "json" หรือไม่มี
        self.file_name = file_name
        self.page = num
        self.fuzzy_threshold = fuzzy_threshold

    def _normalize_tax_id(self, tax_id: str) -> str:
        digits = re.sub(r"\D", "", tax_id or "")
        return digits

    def invoice_company(self) -> dict:
        tax_id_raw = self.data.get("tax_id")
        tax_id = self._normalize_tax_id(tax_id_raw)

        # validate 13 หลักก่อน
        if not tax_id or len(tax_id) != 13:
            # บันทึกสถานะตรวจไม่ได้ แล้วคืน dict กลับไปให้โค้ดส่วนอื่นใช้งานต่อ
            self._write_out(verified={
                "matched": None,
                "seller_from_receipt": (self.data.get("seller") or "").strip(),
                "seller_from_tax_id": None,
                "reason": "invalid_or_missing_tax_id"
            })
            return self.data

        # options = webdriver.ChromeOptions()
        options = Options()
        options.add_experimental_option("detach", False)  # ให้ปิดอัตโนมัติ
        driver = webdriver.Chrome(options=options)

        try:
            wait = WebDriverWait(driver, 15)
            driver.get("https://datawarehouse.dbd.go.th/index")

            # ปิด popup / ยอมรับ
            try:
                wait.until(EC.element_to_be_clickable((By.ID, "btnWarning"))).click()
            except Exception:
                pass  # บางครั้งไม่มีปุ่มนี้

            # กล่องค้นหา
            box = wait.until(EC.presence_of_element_located((By.ID, "key-word")))
            box.clear()
            box.send_keys(tax_id + Keys.ENTER)

            # รอผลลัพธ์/โปรไฟล์ขึ้น
            time.sleep(1)  # กันโหลด dynamic
            # ตำแหน่ง h3 เดิมที่คุณใช้
            try:
                h3 = wait.until(EC.presence_of_element_located(
                    (By.XPATH, '//*[@id="companyProfileTab1"]/div[1]/div[1]/div/div/h3')
                ))
                company_text = h3.text.strip()
            except Exception:
                company_text = ""

            # ตัดชื่อบริษัท
            m = re.search(r"ชื่อนิติบุคคล\s*[:：]\s*(.+)", company_text)
            if m:
                company_name = m.group(1).strip()
            else:
                # fallback: ถ้าไม่มี prefix ก็ใช้ข้อความตรง ๆ
                company_name = company_text or None

            print(company_name)
            seller_name = (self.data.get("seller") or "").strip()
            if company_name:
                similarity = fuzz.ratio(company_name.strip(), seller_name)
                matched = similarity >= self.fuzzy_threshold
            else:
                matched = None

            verified = {
                "matched": matched,
                "seller_from_receipt": seller_name,
                "seller_from_tax_id": company_name
            }

            self._write_out(verified=verified)
            return self.data

        except Exception as e:
            # เขียนสถานะผิดพลาดไว้ด้วย จะได้ debug ย้อนหลังได้
            self._write_out(verified={
                "matched": None,
                "seller_from_receipt": (self.data.get("seller") or "").strip(),
                "seller_from_tax_id": None,
                "error": str(e)
            })
            return self.data
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    def _write_out(self, verified: dict):
        self.data["verified_seller_name"] = verified
        #print(self.page) # 👈 แสดงผลหน้าจอ (stdout)
        out_path = f"{self.file_name}_output_page_{self.page}.json"
        # with open(out_path, "w", encoding="utf-8") as f:
        #     json.dump(self.data, f, ensure_ascii=False, indent=2)
