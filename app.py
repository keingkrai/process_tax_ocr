from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from datetime import datetime
from database.conn import DatabaseConnection
import os, re, mimetypes, time, json
from PIL import Image, ImageDraw, ImageFont
import io
import textwrap
from dotenv import load_dotenv

# Load environment variables from the .env file located up one directory and then in src/app
dotenv_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'app', 'local.env')
load_dotenv(dotenv_path=dotenv_path)


app = FastAPI(title="Nani Tax Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # TODO: restrict in production
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ---- Settings ----
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ---- Optional workflow imports ----
try:
    from prepro import FileHandler
    from ocr_flow import OCRService, TransactionExtractor
    from extraction import InvoiceExtractor as ex
    from predict_category import prediction
    from find_company import FindInvoiceCompany
    from condition import check_condition
    WORKFLOW_AVAILABLE = True
except Exception as e:
    import traceback
    print("[WORKFLOW IMPORT ERROR]", repr(e))
    traceback.print_exc()
    WORKFLOW_AVAILABLE = False
    
ALLOWED_MIME = {"application/pdf", "image/jpeg", "image/png"}
MAX_BYTES = 15 * 1024 * 1024  # 15MB

BASE_DIR = os.path.dirname(__file__)
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
SAVED_DIR  = os.path.join(BASE_DIR, "saved_records")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(SAVED_DIR, exist_ok=True)

def validate_file_upload(file: UploadFile, content: bytes):
    mt = file.content_type or ""
    if mt not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail=f"Unsupported type: {mt}")
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large")
    
def normalize_page_key(p):
    """Accepts keys like 1, "1", "1/2", "page-3" and returns int page number."""
    if isinstance(p, int):
        return p
    s = str(p).strip()
    m = re.match(r"^(\d+)(?:/\d+)?$", s)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else 1


@app.get("/create/table")
async def create_table():
    create_table = DatabaseConnection()
    return create_table.create_table()

@app.post("/api/insert_employee")
async def insert_employee(
    payload: dict = Body(...)
):
    name = payload.get("name")
    email = payload.get("email")
    password_hash = payload.get("password_hash")
    role = payload.get("role", "user")

    db = DatabaseConnection()
    emp_id = db.insert_employee(name, email, password_hash, role)
    if emp_id:
        return {"ok": True, "id": emp_id}
    return {"ok": False}

@app.get("/api/get_employees")
async def get_employees():
    db = DatabaseConnection()
    employees = db.get_employees()
    return {"ok": True, "employees": employees}

@app.get("/api/get_pre_employees")
async def get_pre_employees(email: str, password_hash: str):
    db = DatabaseConnection()
    employee = db.get_pre_employee(email, password_hash)
    if employee:
        return {"ok": True, "employee": employee}
    return {"ok": False, "error": "Invalid email or password"}

@app.post("/api/insert_document")
async def insert_document(
    employee_id: int = Query(...),
    member_name: str = Query(...),
    body: dict = Body(...)
):
    meta = body.get("meta", {})
    result_json = body.get("result_json", {})
    db = DatabaseConnection()
    doc_id = db.insert_document(employee_id, member_name, meta, result_json)
    return {"ok": bool(doc_id), "id": doc_id}

@app.get("/api/get_all_document")
async def get_all_document(
    employee_id: int = Query(...)
):
    db = DatabaseConnection()
    documents = db.get_all_document(employee_id)
    return {"ok": True, "documents": documents}

@app.get("/api/get_per_document")
async def get_per_document(doc_id: int):
    db = DatabaseConnection()
    document = db.get_per_document(doc_id)
    if document:
        return {"ok": True, "document": document}
    return {"ok": False}

@app.delete("/api/delete_document")
async def delete_document(document_id: int):
    db = DatabaseConnection()
    ok = db.delete_document(document_id)
    return {"ok": bool(ok)}


@app.get("/ping")
def ping():
    return {"ok": True}


@app.get("/status")
def status():
    return {
        "ok": True,
        "workflow_available": WORKFLOW_AVAILABLE,
        "env": {
            "TYPHOON_API_KEY": bool(os.getenv("TYPHOON_OCR_API_KEY"))
        }
    }


@app.get("/thumb_text")
def thumb_text(text: str = Query(...)):
    width, height = 600, 400
    img = Image.new("RGB", (width, height), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    font_path = os.path.join("fonts", "Sarabun-Italic.ttf")
    font = ImageFont.truetype(font_path, 32)

    # wrap ข้อความไม่ให้ยาวเกิน 25 ตัวอักษรต่อบรรทัด
    wrapped = textwrap.fill(text, width=25)

    # คำนวณตำแหน่ง
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=6)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.multiline_text(((width - text_w) / 2, (height - text_h) / 2),
                        wrapped, font=font, fill=(0, 0, 0), spacing=6)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


#ดาวน์โหลดไฟล์ต้นฉบับ
@app.get("/download/{filename}")
def download_file(filename: str):
    safe = os.path.basename(filename)
    path = os.path.join(UPLOAD_DIR, safe)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    mt, _ = mimetypes.guess_type(path)
    return FileResponse(path, media_type=mt or "application/octet-stream", filename=safe)

# บันทึกสรุปผลสู่ระบบ
@app.post("/api/save")
def save_record(payload: dict = Body(...)):
    now = datetime.utcnow().isoformat() + "Z"
    rid = str(int(time.time() * 1000))
    record = {
        "id": rid,
        "savedAt": now,
        **payload,
    }
    path = os.path.join(SAVED_DIR, f"{rid}.json")
    with open(path, "w", encoding="utf-8") as f:
        # ตรงนี้ใช้ ensure_ascii=False ได้ เพราะเราคุม json.dump เอง
        json.dump(record, f, ensure_ascii=False, indent=2)

    return JSONResponse({"ok": True, "id": rid, "savedAt": now, "record": record})

# ดึงรายการที่บันทึกทั้งหมด (สรุป)
@app.get("/api/saved")
def list_saved():
    items = []
    for name in sorted(os.listdir(SAVED_DIR), reverse=True):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(SAVED_DIR, name), "r", encoding="utf-8") as f:
            data = json.load(f)
        items.append({
            "id": data.get("id"),
            "savedAt": data.get("savedAt"),
            "fileName": data.get("fileName"),
            "memberName": data.get("memberName"),
            "title": data.get("title") or data.get("raw", {}).get("title"),
            "seller": data.get("seller"),
            "dateStr": data.get("dateStr"),
            "total": data.get("total"),
            "deduction_status": data.get("deduction_status"),
            "reason": data.get("reason"),
        })
    return JSONResponse({"ok": True, "items": items}, ensure_ascii=False)

# ดึงรายการที่บันทึกตาม id (เต็มก้อน)
@app.get("/api/saved/{rid}")
def get_saved(rid: str):
    path = os.path.join(SAVED_DIR, f"{os.path.basename(rid)}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Not found")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return JSONResponse({"ok": True, "record": data}, ensure_ascii=False)

@app.post("/api/process")
async def process_file(file: UploadFile = File(...)):
    """
    Accepts multipart/form-data with fields:
      - file: PDF or image
      - user_name: optional string (buyer name)
    Returns a normalized JSON suitable for the Next.js frontend.
    """
    try:
        # Validate
        if not file or not file.filename or file.filename.strip() == "":
            raise HTTPException(status_code=400, detail="No file uploaded or empty filename")

        safe_name = os.path.basename(file.filename)
        save_path = os.path.join(UPLOAD_DIR, safe_name)

        # Persist to disk if downstream expects a path
        content = await file.read()
        validate_file_upload(file, content)
        with open(save_path, "wb") as f:
            f.write(content)

        # Demo path when optional workflow modules aren't installed
        if not WORKFLOW_AVAILABLE:
            demo = {
                "file": safe_name,
                "pages": {
                    "1": {
                        "title": "เดโม",
                        "invoice_type": "Simple Invoice",
                        "seller": "บริษัทเดโม จำกัด",
                        "tax_id": "1234567890123",
                        "date": {"day": "16", "month": "08", "year": "2568"},
                        "items": [
                            {
                                "name": "เบี้ยประกันสุขภาพ",
                                "category": "การออมการลงทุนและประกัน",
                                "sub_category": "เบี้ยประกันสุขภาพ",
                                "deduction_status": "สามารถลดหย่อนได้",
                            }
                        ],
                        "deduction_status": "ผ่านเงื่อนไขเบื้องต้น",
                    }
                },
            }
            return {"ok": True, "result": demo}

        # --- Real workflow ---
        file_handler = FileHandler(save_path)
        ocr_service = OCRService()
        extractor = TransactionExtractor(ocr_service)

        # Expecting dict like { page: text }
        ocr_result = extractor.process_document(file_handler)

        pages = {}
        base = os.path.splitext(safe_name)[0]

        for raw_page, text in ocr_result.items():
            page = normalize_page_key(raw_page)

            invoice = ex(text)
            out = invoice.typhoon_extract()  # may return dict or {"json": {...}}
            payload = out.get("json", out)

            pred = prediction(payload).run()
            finder = FindInvoiceCompany(input_json=pred, file_name=base, num=page)
            verified = finder.invoice_company()
            checked = check_condition(verified, file_name=base, num=page).check()

            pages[str(page)] = checked

        return JSONResponse({"ok": True, "result": {"file": safe_name, "pages": pages, "download_path": f"/download/{safe_name}"}})

    except HTTPException:
        raise
    except Exception as e:
        # You can also return JSONResponse(..., status_code=500)
        raise HTTPException(status_code=500, detail=str(e))


# --- How to run ---
# uvicorn app:app --reload --port 8000
