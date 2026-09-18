#!/usr/bin/env bash
# Install nginx + Let's Encrypt SSL for VStock API on GCE.
# Prerequisite: DNS A record vnstock-api.antunai.com → VM external IP (propagated).
#
# Usage (on the VM, from repo root):
#   chmod +x scripts/setup-nginx-https.sh
#   sudo ./scripts/setup-nginx-https.sh
#
# Optional env:
#   DOMAIN=vnstock-api.antunai.com
#   EMAIL=you@example.com   # Let's Encrypt notifications

set -euo pipefail

DOMAIN="${DOMAIN:-vnstock-api.antunai.com}"
EMAIL="${EMAIL:-}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NGINX_SITE="/etc/nginx/sites-available/vstock-api"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run with sudo: sudo $0" >&2
  exit 1
fi

echo "==> Checking DNS for ${DOMAIN}..."
RESOLVED="$(getent ahosts "${DOMAIN}" | awk '/STREAM/ { print $1; exit }' || true)"
if [[ -z "${RESOLVED}" ]]; then
  echo "ERROR: ${DOMAIN} does not resolve yet. Add GoDaddy A record and wait for propagation." >&2
  exit 1
fi
echo "    ${DOMAIN} → ${RESOLVED}"

echo "==> Installing nginx + certbot..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nginx certbot python3-certbot-nginx

echo "==> Installing nginx site config..."
cp "${REPO_ROOT}/deploy/nginx/vnstock-api.conf" "${NGINX_SITE}"
ln -sf "${NGINX_SITE}" /etc/nginx/sites-enabled/vstock-api
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl reload nginx

echo "==> Requesting Let's Encrypt certificate..."
CERTBOT_ARGS=(--nginx -d "${DOMAIN}" --non-interactive --agree-tos --redirect)
if [[ -n "${EMAIL}" ]]; then
  CERTBOT_ARGS+=(--email "${EMAIL}")
else
  CERTBOT_ARGS+=(--register-unsafely-without-email)
fi
certbot "${CERTBOT_ARGS[@]}"

echo ""
echo "Done. Verify:"
echo "  curl -sS https://${DOMAIN}/health"
echo ""
echo "App / EAS: EXPO_PUBLIC_API_URL=https://${DOMAIN}"
echo "Rebuild iOS/Android production after updating eas.json."
