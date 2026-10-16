import io
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CAPTURE_DIR = os.path.abspath(
    os.getenv("CAPTURE_STORAGE_DIR", os.path.join(APP_DIR, "captures"))
)
MAX_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
RATE_LIMIT = int(os.getenv("RATE_LIMIT_PER_MINUTE", "5"))

app = FastAPI(title="Camera capture")
app.mount("/static", StaticFiles(directory=os.path.join(APP_DIR, "static")), name="static")
requests_by_ip = defaultdict(deque)

@app.get("/")
def home():
    return FileResponse(os.path.join(APP_DIR, "static", "index.html"))

@app.get("/health")
def health():
    return {"status": "ok"}

def enforce_rate_limit(ip: str):
    now = time.time()
    q = requests_by_ip[ip]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    q.append(now)

@app.post("/api/capture")
async def upload_capture(
    request: Request,
    image: UploadFile = File(...),
):
    ip = request.client.host if request.client else "unknown"
    enforce_rate_limit(ip)
    if image.content_type not in ("image/jpeg", "image/jpg", "image/png", "image/webp"):
        raise HTTPException(status_code=415, detail="Upload a JPEG, PNG, or WebP image.")

    raw = await image.read(MAX_BYTES + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="Empty image.")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds the upload limit.")

    # Decode/re-encode to strip EXIF and GPS metadata.
    try:
        with Image.open(io.BytesIO(raw)) as im:
            im.verify()
        with Image.open(io.BytesIO(raw)) as im:
            im = im.convert("RGB")
            im.thumbnail((2560, 2560))
            output = io.BytesIO()
            im.save(output, format="JPEG", quality=88, optimize=True)
            cleaned = output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid image.")

    rel_key = f"{datetime.now(timezone.utc):%Y/%m/%d}/{uuid.uuid4().hex}.jpg"
    dest_path = os.path.join(CAPTURE_DIR, rel_key)
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(cleaned)
    except OSError:
        raise HTTPException(status_code=502, detail="Storage write failed.")

    capture_id = rel_key.rsplit("/", 1)[-1].removesuffix(".jpg")
    return {"status": "uploaded", "capture_id": capture_id, "path": rel_key}
