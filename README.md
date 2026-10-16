# Camera capture (local storage)

## Behavior
Opening the page requests camera permission, captures one front-camera frame without showing a video preview, and saves it on the server filesystem through FastAPI.

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

## Deploy on Render (personal GitHub + Docker)

Render builds from the **`Dockerfile`** in your **personal** repo (not a company org).

1. Create or use repo `subhadipb7679/camera-capture-app` and set `origin` to it.
2. Push `main`.
3. Render service `camera-capture` uses **Runtime: Docker**, health check `/health`.
4. Set `ADMIN_DOWNLOAD_KEY` in Render env vars to download captures remotely.

One-command deploy after `export RENDER_API_KEY=...`:

```bash
chmod +x deploy-render.sh
./deploy-render.sh
```

Or manually:

```bash
git push origin main
render deploys create srv-db8vjtss728c73b8e4l0 --wait --confirm
```

Live URL: `https://quote-pop.onrender.com` (HTTPS for camera access).

Captures on the free tier use ephemeral disk; files are lost on restart or spin-down.

## Docker (local)
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
