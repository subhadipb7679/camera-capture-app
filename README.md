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

## Deploy on Render (free tier, no GitHub)

Use a **personal Docker Hub** (or other registry) account. Do not connect a work or org GitHub repo.

From this project directory:

```bash
export DOCKER_USER="your-dockerhub-username"
docker build -t "$DOCKER_USER/camera-capture:latest" .
docker login
docker push "$DOCKER_USER/camera-capture:latest"
```

In [Render Dashboard](https://dashboard.render.com/):

1. **New** → **Web Service** → **Deploy an existing image from a registry**.
2. Image URL: `docker.io/your-dockerhub-username/camera-capture:latest`
3. **Plan:** Free
4. **Health check path:** `/health`
5. **Environment variable:** `CAPTURE_STORAGE_DIR` = `/app/captures` (already set in the Dockerfile; optional to override)

After deploy, open the `*.onrender.com` URL. HTTPS is included so the camera works in the browser.

Captures on the free tier use ephemeral disk; files are lost on restart or spin-down.

Optional [Render CLI](https://render.com/docs/cli) (personal API key from your Render account):

```bash
export RENDER_API_KEY="rnd_..."
export DOCKER_USER="your-dockerhub-username"
render services create \
  --name camera-capture \
  --type web_service \
  --image "docker.io/${DOCKER_USER}/camera-capture:latest" \
  --plan free \
  --region oregon \
  --health-check-path /health \
  --confirm -o json
```

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
