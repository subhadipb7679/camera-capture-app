#!/usr/bin/env bash
# Deploy updates: push personal GitHub repo, then trigger Render (Dockerfile build).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PATH="${HOME}/.local/bin:${PATH}"

: "${RENDER_API_KEY:?Set RENDER_API_KEY}"
: "${RENDER_SERVICE_ID:=srv-db8u7cnavr4c73ccgi70}"

git add -A
if ! git diff --cached --quiet; then
  git commit -m "Deploy update"
fi
git push origin main

render workspace set tea-db8tvk6q1p3s739cu3vg -o text >/dev/null
render deploys create "$RENDER_SERVICE_ID" --wait --confirm -o text
echo "Live: https://camera-capture-4glb.onrender.com"
