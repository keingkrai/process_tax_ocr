from datetime import datetime
import json

class check_condition:
    def __init__(self, input_json: dict, file_name: str, num: int, user_name: str):
        self.input_json_raw = input_json or {}
        self.file_name = file_name
        self.page = num
        self.user_name = user_name

    @staticmethod
    def _safe_int(x, default=None):
        try:
            return int(x)
        except Exception:
            return default

    def _write_out(self):
        with open(f"{self.file_name}_output_page_{self.page}.json", "w", encoding="utf-8") as f:
            json.dump(self.input_json_raw, f, ensure_ascii=False, indent=2)

    def check(self) -> dict:
        now = datetime.now()
        data = self.input_json_raw

        buyer = (data.get("buyer") or "").strip()
        verified = data.get("verified_seller_name") or {}
        comfirm_company = verified.get("matched")

        date_obj = data.get("date") or {}
        d = self._safe_int(date_obj.get("day"))
        m = self._safe_int(date_obj.get("month"))
        y = self._safe_int(date_obj.get("year"))

        print("ชื่อผู้ใช้:", buyer,
              "ปีที่ลดหย่อน:", y,
              "ชื่อบริษัท:", comfirm_company,
              "วันที่รับเอกสาร:", date_obj,
              now.year + 542)

        reason = ""
        # เทียบชื่อ
        if buyer != self.user_name:
            reason = "ชื่อผู้ซื้อไม่ตรงกับชื่อผู้ใช้"
        # เทียบการยืนยันบริษัท
        elif not comfirm_company:
            reason = "ไม่สามารถยืนยันชื่อบริษัทกับฐานข้อมูล"
        # เทียบปี (ระวังชนิดข้อมูลให้เป็น int ทั้งคู่)
        elif y != (now.year + 542):
            reason = f"ปีภาษีไม่ตรง (ต้องเป็น {now.year + 542})"

        # กรณีผ่านเงื่อนไขพื้นฐาน
        if not reason:
            # ป้องกัน crash ถ้าไม่มี items หรือ warranty_period เป็นค่าว่าง
            items = data.get("items") or []
            wp = self._safe_int(data.get("warranty_period"), 0)

            for it in items:
                sub = it.get("sub_category")
                cat = it.get("category")  # อาจไม่มี ให้ใช้ .get เพื่อลดโอกาส KeyError

                # *** หมายเหตุ: ตรรกะช่วงวัน/เดือนตามโค้ดเดิม อาจต้องทบทวนวงเล็บ ***
                if sub == "เบี้ยประกันชีวิต" and not (wp >= 10):
                    it["deduction_status"] = "ไม่สามารถลดหย่อนได้"
                    break
                elif sub == "เบี้ยประกันชีวิตแบบบำนาญ" and not (wp >= 10):
                    it["deduction_status"] = "ไม่สามารถลดหย่อนได้"
                    break
                elif sub == "ค่าซื้อหน่วยลงทุนเพื่อการเลี้ยงชีพ (RMF)" and not (wp >= 5):
                    it["deduction_status"] = "ไม่สามารถลดหย่อนได้"
                    break
                elif sub == "ค่าซื้อหน่วยลงทุนในกองทุนรวมเพื่อการออม SSF" and not (wp >= 10 and d is not None and m is not None and y is not None and d >= 1 and m >= 1 and y >= 2563):
                    # เดิมคุณตั้งให้ not(...) -> "สามารถลดหย่อนได้" ซึ่งกลับขั้ว
                    it["deduction_status"] = "ไม่สามารถลดหย่อนได้"
                    break
                elif sub == "ค่าซื้อหน่วยลงทุนในกองทุนรวมไทยเพื่อความยั่งยืน (Thai ESG)" and not (d is not None and m is not None and y is not None and d >= 1 and m >= 1 and y >= (now.year + 542)):
                    it["deduction_status"] = "ไม่สามารถลดหย่อนได้"
                    break
                elif sub == "เงินบริจาคพรรคการเมือง" and not (d is not None and m is not None and y is not None and d >= 1 and m >= 1 and y >= 2561):
                    it["deduction_status"] = "ไม่สามารถลดหย่อนได้"
                    break
                elif sub == "ค่าท่องเที่ยวภายในประเทศ" and (
                    (not (d is not None and m is not None and y is not None and d >= 1 and m >= 5 and y >= (now.year + 542)))
                    or (d is not None and m is not None and y is not None and d <= 30 and m <= 11 and y <= (now.year + 542))
                ):
                    it["deduction_status"] = "ไม่สามารถลดหย่อนได้"
                    break
                elif sub == "ค่าจ้างก่อสร้างอาคารเพื่ออยู่อาศัยขึ้นใหม่ให้แก่ผู้รับจ้างซึ่งเป็นผู้ประกอบการจดทะเบียนภาษีมูลค่าเพิ่ม" and (
                    (not (d is not None and m is not None and y is not None and d >= 9 and m >= 4 and y >= (now.year + 542)))
                    or (d is not None and m is not None and y is not None and d <= 31 and m <= 12 and y <= (now.year + 542))
                ):
                    it["deduction_status"] = "ไม่สามารถลดหย่อนได้"
                    break
                elif sub == "ค่าซ่อมบ้านจากอุทกภัย" and (
                    (not (d is not None and m is not None and y is not None and d >= 16 and m >= 8 and y == (now.year + 542)))
                    or (d is not None and m is not None and y is not None and d <= 31 and m <= 12 and y == (now.year + 542))
                ):
                    it["deduction_status"] = "ไม่สามารถลดหย่อนได้"
                    break
                elif sub == "ค่าซ่อมรถจากอุทกภัย" and (
                    (not (d is not None and m is not None and y is not None and d >= 16 and m >= 8 and y == (now.year + 542)))
                    or (d is not None and m is not None and y is not None and d <= 31 and m <= 12 and y == (now.year + 542))
                ):
                    it["deduction_status"] = "ไม่สามารถลดหย่อนได้"
                    break
                elif cat == "Easy E-Receipt" and (
                    (not (d is not None and m is not None and y is not None and d >= 1 and m >= 1 and y == (now.year + 542)))
                    and (d is not None and m is not None and y is not None and d <= 15 and m <= 2 and y == (now.year + 542))
                ):
                    it["deduction_status"] = "ไม่สามารถลดหย่อนได้"
                    break
                else:
                    it["deduction_status"] = "สามารถลดหย่อนได้"

            # (ตัวอย่างนี้) ให้เอกสาร “ผ่านเบื้องต้น”
            data["deduction_status"] = "ผ่านเงื่อนไขเบื้องต้น"
            self._write_out()
            print("✅ สามารถลดหย่อนได้")
            print("="*20)

        else:
            data["deduction_status"] = "ไม่สามารถลดหย่อนได้"
            data["reason"] = f"ไม่สามารถลดหย่อนได้ เพราะ: {reason}"
            self._write_out()
            print(f"❌ ไม่สามารถลดหย่อนได้ เพราะ: {reason}")
            print("="*20)

        return data
