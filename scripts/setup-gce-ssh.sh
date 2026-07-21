#!/usr/bin/env bash
# One-time SSH setup: Mac terminal → GCE VM vstock-api
# Usage: ./scripts/setup-gce-ssh.sh

set -euo pipefail

PROJECT="${GCP_PROJECT:-vstock-prod}"
ZONE="${GCP_ZONE:-asia-southeast1-a}"
INSTANCE="${GCE_INSTANCE:-vstock-api}"
KEY="${GCE_SSH_KEY:-$HOME/.ssh/gce_vstock_ed25519}"
LOCAL_USER="$(whoami)"

echo "Project: $PROJECT  VM: $INSTANCE  Key: $KEY"

if ! command -v gcloud >/dev/null; then
  echo "Install gcloud: https://cloud.google.com/sdk/docs/install"
  exit 1
fi

gcloud config set project "$PROJECT" >/dev/null

if [[ ! -f "$KEY" ]]; then
  echo "Generating ed25519 key (Ubuntu 22+ thường từ chối RSA cũ)…"
  ssh-keygen -t ed25519 -f "$KEY" -N "" -C "${LOCAL_USER}@vstock-gce"
fi

PUB="$(cat "${KEY}.pub")"
DEPLOY_USER="${GCE_DEPLOY_USER:-anh_nguyendinh_cs}"

echo "Adding SSH keys for: $LOCAL_USER (Mac user) + $DEPLOY_USER (repo/Docker on VM)"
gcloud compute instances add-metadata "$INSTANCE" \
  --zone="$ZONE" \
  --project="$PROJECT" \
  --metadata "ssh-keys=${LOCAL_USER}:${PUB},${DEPLOY_USER}:${PUB}"

echo "Waiting for guest agent to apply keys…"
sleep 5

IP="$(gcloud compute instances describe "$INSTANCE" --zone="$ZONE" --project="$PROJECT" --format='get(networkInterfaces[0].accessConfigs[0].natIP)')"
gcloud compute config-ssh --project="$PROJECT" --quiet

ALIAS="${INSTANCE}.${ZONE}.${PROJECT}"
echo ""
echo "=== SSH commands ==="
echo ""
echo "# Deploy user (~/VStock, docker compose):"
echo "ssh -i $KEY ${DEPLOY_USER}@${IP}"
echo ""
echo "# Mac username on VM:"
echo "ssh -i $KEY ${LOCAL_USER}@${IP}"
echo ""
echo "# gcloud (Mac user):"
echo "gcloud compute ssh $INSTANCE --zone=$ZONE --project=$PROJECT --ssh-key-file=$KEY"
echo ""
echo "# Alias (add IdentityFile $KEY to ~/.ssh/config if needed):"
echo "ssh $ALIAS"
