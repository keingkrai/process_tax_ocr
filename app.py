from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os, json, re

# import workflow modules
try:
    from prepro import FileHandler
    from ocr_flow import OCRService, TransactionExtractor
    from extraction import InvoiceExtractor as ex
    from predict_category import prediction
    from find_company import FindInvoiceCompany
    from condition import check_condition
    WORKFLOW_AVAILABLE = True
except Exception:
    WORKFLOW_AVAILABLE = False

APP_DIR = os.path.dirname(__file__)
FRONTEND_DIR = os.path.abspath(os.path.join(APP_DIR, "..", "frontend"))
UPLOAD_DIR = os.path.join(APP_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="/")
CORS(app)

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/api/process", methods=["POST"])
def process_file():
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file uploaded"}), 400

    f = request.files["file"]
    if not f or f.filename.strip() == "":
        return jsonify({"ok": False, "error": "Empty filename"}), 400

    user_name = (request.form.get("user_name") or "").strip()
    filename = f.filename
    save_path = os.path.join(UPLOAD_DIR, filename)
    f.save(save_path)

    if not WORKFLOW_AVAILABLE:
        demo = {
            "file": filename,
            "pages": {
                "1": {
                    "title": "เดโม",
                    "invoice_type": "Simple Invoice",
                    "seller": "บริษัทเดโม จำกัด",
                    "buyer": user_name or "ไม่ระบุ",
                    "tax_id": "1234567890123",
                    "date": {"day": "16", "month": "08", "year": "2568"},
                    "items": [
                        {"name": "เบี้ยประกันสุขภาพ", "category": "การออมการลงทุนและประกัน",
                         "sub_category": "เบี้ยประกันสุขภาพ", "deduction_status": "สามารถลดหย่อนได้"}
                    ],
                    "deduction_status": "ผ่านเงื่อนไขเบื้องต้น"
                }
            }
        }
        return jsonify({"ok": True, "result": demo})
    
    def normalize_page_key(p):
        if isinstance(p, int):
            return p
        s = str(p).strip()
        # ดึงเลขหน้าด้านซ้ายของรูปแบบ "x/y"
        m = re.match(r'^(\d+)(?:/\d+)?$', s)
        if m:
            return int(m.group(1))
        # เผื่อรูปแบบอื่น ๆ เช่น "page-3"
        m = re.search(r'(\d+)', s)
        return int(m.group(1)) if m else 1  # fallback

    try:
        file_handler = FileHandler(save_path)
        ocr_service = OCRService()
        extractor = TransactionExtractor(ocr_service)
        ocr_result = extractor.process_document(file_handler)  # {page: text}
        print(ocr_result.items())

        pages = {}
        base = os.path.splitext(filename)[0]

        for raw_page, text in ocr_result.items():
            print(raw_page)
            page = normalize_page_key(raw_page)
            invoice = ex(text)
            out = invoice.typhoon_extract()        # dict; บางเวอร์ชันเป็น {"json": {...}}
            payload = out.get("json", out)         # รองรับทั้งสองแบบ

            pred = prediction(payload).run()
            finder = FindInvoiceCompany(input_json=pred, file_name=base, num=page)
            verified = finder.invoice_company()
            checked = check_condition(verified, file_name=base, num=page, user_name=user_name).check()

            pages[str(page)] = checked   # << เก็บ dict ตรง ๆ

        return jsonify({"ok": True, "result": {"file": filename, "pages": pages}})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
