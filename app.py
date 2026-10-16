import html
import io
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
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

def captures_html() -> str:
    items = sorted(iter_capture_files(), key=lambda x: x["modified_utc"], reverse=True)
    cards = []
    for item in items:
        cid = html.escape(item["capture_id"])
        when = html.escape(item["modified_utc"].replace("T", " ").replace("+00:00", " UTC"))
        cards.append(
            f'<article class="card"><img src="/api/captures/{cid}/image" alt="{cid}" loading="lazy">'
            f'<div class="meta"><div>{when}</div>'
            f'<a href="/api/captures/{cid}/download">Download</a></div></article>'
        )
    body = "\n".join(cards) if cards else '<p class="empty">No images yet. Play the game and tap the button once.</p>'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gallery</title>
<style>
:root{{color-scheme:dark;font-family:system-ui,sans-serif}}
body{{margin:0;padding:20px;background:#0f1419;color:#eef2f8}}
h1{{margin:0 0 8px;font-size:1.35rem}}
.sub{{color:#9aa8bc;margin:0 0 16px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px}}
.card{{background:#1a222d;border:1px solid #2e3a4d;border-radius:12px;overflow:hidden}}
.card img{{display:block;width:100%;aspect-ratio:4/3;object-fit:cover;background:#080a0d}}
.meta{{padding:8px 10px;font-size:.75rem;color:#9aa8bc}}
.meta a{{color:#9eb4ff}}
.empty{{color:#9aa8bc}}
</style></head><body>
<h1>Gallery</h1>
<p class="sub">{len(items)} image(s) on this server · <a href="/">Back to game</a></p>
<div class="grid">{body}</div></body></html>"""

@app.get("/captures", response_class=HTMLResponse)
@app.get("/gallery", response_class=HTMLResponse)
def gallery_page():
    return captures_html()

def iter_capture_files():
    if not os.path.isdir(CAPTURE_DIR):
        return
    for root, _, files in os.walk(CAPTURE_DIR):
        for name in files:
            if not name.endswith(".jpg"):
                continue
            full = os.path.join(root, name)
            rel = os.path.relpath(full, CAPTURE_DIR)
            stat = os.stat(full)
            capture_id = name.removesuffix(".jpg")
            yield {
                "capture_id": capture_id,
                "path": rel.replace(os.sep, "/"),
                "size_bytes": stat.st_size,
                "modified_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }

def resolve_capture_path(capture_id: str) -> str:
    if not capture_id.isalnum() or len(capture_id) != 32:
        raise HTTPException(status_code=400, detail="Invalid capture id.")
    for root, _, files in os.walk(CAPTURE_DIR):
        target = f"{capture_id}.jpg"
        if target in files:
            return os.path.join(root, target)
    raise HTTPException(status_code=404, detail="Capture not found.")

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

@app.get("/api/captures")
def list_captures(request: Request, format: str | None = None):
    accept = request.headers.get("accept", "")
    wants_json = format == "json" or accept.startswith("application/json")
    wants_html = "text/html" in accept and not wants_json
    if wants_html:
        return RedirectResponse("/captures", status_code=302)
    items = sorted(iter_capture_files(), key=lambda x: x["modified_utc"], reverse=True)
    return {"captures": items}

@app.get("/api/captures/{capture_id}/image")
def view_capture(capture_id: str):
    path = resolve_capture_path(capture_id)
    return FileResponse(path, media_type="image/jpeg", filename=f"{capture_id}.jpg")

@app.get("/api/captures/{capture_id}/download")
def download_capture(capture_id: str):
    path = resolve_capture_path(capture_id)
    return FileResponse(path, media_type="image/jpeg", filename=f"{capture_id}.jpg")
