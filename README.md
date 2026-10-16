# Camera capture (local storage)

## Behavior
Opening the page requests camera permission, shows a short preview, captures one front-camera frame, and saves it on the server filesystem through FastAPI.

## Local setup
Requires Python 3.12+.
```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export CAPTURE_STORAGE_DIR="./captures"   # optional; default is ./captures
uvicorn app:app --reload
```
Open `http://127.0.0.1:8000` to test. Localhost is allowed for camera access. Saved files appear under `captures/YYYY/MM/DD/<id>.jpg`.

## Docker
```bash
docker build -t authorized-s3-security-checkin .
docker run --rm -p 8000:8000 \
  -v "$(pwd)/captures:/app/captures" \
  authorized-s3-security-checkin
```
Mount a volume on `/app/captures` (or set `CAPTURE_STORAGE_DIR`) so uploads persist outside the container.

## Security controls
- Backend limits image size and accepted content types.
- Images are decoded/re-encoded to JPEG to remove EXIF/GPS metadata.
- Files use unpredictable names under `captures/`; they are not served over HTTP by default.
- Restrict filesystem permissions on the capture directory and define retention/deletion on the host or volume.

## API
- `GET /` page
- `GET /health` health check
- `POST /api/capture` multipart field `image`
