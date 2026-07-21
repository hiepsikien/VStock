#!/usr/bin/env bash
# Deploy / update VStock API + Companion on the GCE VM.
# Run ON the VM after SSH:
#   cd ~/VStock && ./scripts/deploy-companion-gce.sh
#
# Prerequisites:
#   - .env with GEMINI_API_KEY or GCP_PROJECT (see .env.gce.example)
#   - git repo cloned at ~/VStock
#   - Docker + docker compose

set -euo pipefail

VSTOCK_DIR="${VSTOCK_DIR:-$HOME/VStock}"
BRANCH="${DEPLOY_BRANCH:-main}"

cd "$VSTOCK_DIR"

if [[ ! -f docker-compose.yml ]]; then
  echo "ERROR: docker-compose.yml not found in $VSTOCK_DIR"
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "ERROR: missing .env — copy .env.gce.example and set GEMINI_API_KEY or GCP_PROJECT"
  exit 1
fi

# shellcheck disable=SC1091
set -a
source .env
set +a

if [[ -z "${GEMINI_API_KEY:-}" && -z "${GCP_PROJECT:-}" ]]; then
  echo "ERROR: set GEMINI_API_KEY or GCP_PROJECT in .env for Companion"
  exit 1
fi

echo "[$(date -Is)] Fetch $BRANCH…"
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

echo "[$(date -Is)] Rebuild api container…"
docker compose up -d --build

echo "[$(date -Is)] Wait for health…"
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "--- API health ---"
curl -s http://127.0.0.1:8000/health | python3 -m json.tool 2>/dev/null || curl -s http://127.0.0.1:8000/health

echo "--- Companion health ---"
COMP=$(curl -s -w "\nHTTP:%{http_code}" http://127.0.0.1:8000/v1/companion/health)
echo "$COMP"
if echo "$COMP" | grep -q 'HTTP:404'; then
  echo "ERROR: /v1/companion/health still 404 — branch may not include Companion. Try DEPLOY_BRANCH=feature/companion-ai"
  exit 1
fi

if echo "$COMP" | grep -q '"configured":false'; then
  echo "WARN: Companion routes exist but Gemini not configured — check .env"
  exit 1
fi

echo "[$(date -Is)] Smoke nudge…"
curl -s -X POST http://127.0.0.1:8000/v1/companion/nudge \
  -H 'Content-Type: application/json' \
  -d "{\"events\":[{\"type\":\"view_detail\",\"symbol\":\"FPT\",\"ts\":$(($(date +%s)*1000))}],\"context\":{\"screen\":\"Watchlist\",\"watchlistSymbols\":[\"FPT\",\"VNM\"]}}" \
  | python3 -m json.tool 2>/dev/null || true

echo "[$(date -Is)] Done. External: curl http://$(curl -s -H Metadata-Flavor:Google http://metadata.google.internal/computeMetadata/v1/instance/network-interfaces/0/access-configs/0/external-ip 2>/dev/null || echo 'EXTERNAL_IP'):8000/v1/companion/health"
