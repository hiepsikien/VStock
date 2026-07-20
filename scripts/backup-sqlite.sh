#!/usr/bin/env bash
# Backup VStock SQLite from the running Docker Compose API container.
# Usage (on GCE VM):
#   ~/VStock/scripts/backup-sqlite.sh
# Env overrides:
#   VSTOCK_DIR      — repo root (default: ~/VStock)
#   BACKUP_DIR      — where to store copies (default: ~/backups)
#   KEEP_DAYS       — delete backups older than N days (default: 14)

set -euo pipefail

VSTOCK_DIR="${VSTOCK_DIR:-$HOME/VStock}"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${BACKUP_DIR}/vstock-${STAMP}.db"
LOG="${BACKUP_DIR}/backup.log"

mkdir -p "$BACKUP_DIR"
cd "$VSTOCK_DIR"

if ! docker compose ps -q api >/dev/null 2>&1 || [[ -z "$(docker compose ps -q api)" ]]; then
  echo "[$(date -Is)] ERROR: api container not running" | tee -a "$LOG" >&2
  exit 1
fi

CID="$(docker compose ps -q api)"

docker compose exec -T api python -c "
from pathlib import Path
import os, shutil, sqlite3

src = Path(os.environ['VSTOCK_DB_PATH'])
if not src.is_file():
    raise SystemExit(f'missing db: {src}')

# Consistent snapshot via SQLite backup API
dest = Path('/tmp/vstock-backup.db')
if dest.exists():
    dest.unlink()
with sqlite3.connect(str(src)) as src_conn:
    with sqlite3.connect(str(dest)) as dst_conn:
        src_conn.backup(dst_conn)
print(dest)
"

docker cp "${CID}:/tmp/vstock-backup.db" "$DEST"
docker compose exec -T api rm -f /tmp/vstock-backup.db >/dev/null 2>&1 || true

SIZE="$(du -h "$DEST" | awk '{print $1}')"
echo "[$(date -Is)] OK ${DEST} (${SIZE})" | tee -a "$LOG"

# Retention
find "$BACKUP_DIR" -maxdepth 1 -name 'vstock-*.db' -type f -mtime "+${KEEP_DAYS}" -delete
find "$BACKUP_DIR" -maxdepth 1 -name 'vstock-*.db' -type f | wc -l | xargs -I{} echo "[$(date -Is)] kept {} backup file(s)" | tee -a "$LOG"
