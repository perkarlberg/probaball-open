#!/usr/bin/env bash
# Probaball deploy helper.
#   ./deploy.sh frontend   - build + prerender + deploy the SPA to Firebase Hosting
#   ./deploy.sh backend    - deploy the API to Cloud Run
#   ./deploy.sh reseed     - recompute the canonical snapshot, then redeploy frontend
#   ./deploy.sh all        - backend, reseed, frontend, publish
#   ./deploy.sh publish    - push a clean snapshot to the public GitHub mirror
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT="probaball"
REGION="europe-west1"
API_URL="https://vm2026-api-704772753584.europe-west1.run.app"
GCLOUD_ACCT="perkarlberg@gmail.com"

deploy_backend() {
  echo "==> Deploying backend to Cloud Run"
  gcloud run deploy vm2026-api --source "$ROOT/backend" \
    --project "$PROJECT" --region "$REGION" --quiet
}

reseed() {
  echo "==> Reseeding canonical snapshot (50k computed locally, result uploaded)"
  local token
  token=$(gcloud secrets versions access latest --secret=vm2026-admin-token --project "$PROJECT")
  python3 "$ROOT/backend/reseed_local.py" "$API_URL" "$token"
}

deploy_frontend() {
  echo "==> Building frontend"
  cd "$ROOT/frontend"
  printf 'VITE_API_BASE=%s\n' "$API_URL" > .env.production
  npm run build
  echo "==> Prerendering static SEO content"
  python3 prerender.py "$API_URL" dist/index.html
  echo "==> Deploying to Firebase Hosting"
  local access
  access=$(gcloud auth print-access-token --account="$GCLOUD_ACCT")
  python3 "$ROOT/deploy_hosting.py" "$PROJECT" dist "$access" "$PROJECT"
  indexnow_ping
}

# Tell IndexNow (Bing/Yandex) the per-language home pages changed, so they
# re-crawl promptly. Key file lives at /<key>.txt on the host.
indexnow_ping() {
  local key="f13b0ab379e54d69ac0e015096717eec"
  echo "==> Pinging IndexNow"
  curl -s -X POST "https://api.indexnow.org/indexnow" \
    -H "Content-Type: application/json; charset=utf-8" \
    -d "{\"host\":\"probaball.online\",\"key\":\"$key\",\"keyLocation\":\"https://probaball.online/$key.txt\",\"urlList\":[\"https://probaball.online/\",\"https://probaball.online/en/\",\"https://probaball.online/es/\",\"https://probaball.online/fr/\",\"https://probaball.online/pt/\",\"https://probaball.online/de/\"]}" \
    -o /dev/null -w "    indexnow: HTTP %{http_code}\n" || true
}

# Push a clean snapshot of the committed source to the public GitHub mirror.
# Best-effort: never fail a deploy because publishing hiccuped.
publish_mirror() {
  echo "==> Publishing source to public GitHub mirror"
  "$ROOT/publish.sh" || echo "    publish skipped/failed (non-fatal)"
}

case "${1:-frontend}" in
  backend) deploy_backend ;;
  reseed) reseed; deploy_frontend ;;
  frontend) deploy_frontend ;;
  publish) publish_mirror ;;
  all) deploy_backend; reseed; deploy_frontend; publish_mirror ;;
  *) echo "usage: $0 [frontend|backend|reseed|all|publish]"; exit 1 ;;
esac
echo "==> Done."
