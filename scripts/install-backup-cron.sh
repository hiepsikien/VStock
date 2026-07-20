#!/usr/bin/env bash
# Install weekly cron for SQLite backup (Sundays 03:00 VN / Asia/Ho_Chi_Minh).
# Run once on the GCE VM:
#   bash ~/VStock/scripts/install-backup-cron.sh

set -euo pipefail

VSTOCK_DIR="${VSTOCK_DIR:-$HOME/VStock}"
BACKUP_SCRIPT="${VSTOCK_DIR}/scripts/backup-sqlite.sh"
CRON_LINE="0 3 * * 0 cd ${VSTOCK_DIR} && /bin/bash ${BACKUP_SCRIPT} >> ${HOME}/backups/cron.log 2>&1"

if [[ ! -x "$BACKUP_SCRIPT" ]]; then
  chmod +x "$BACKUP_SCRIPT"
fi

mkdir -p "$HOME/backups"

# Ensure Asia/Ho_Chi_Minh if possible (cron uses system TZ)
if [[ -f /usr/share/zoneinfo/Asia/Ho_Chi_Minh ]]; then
  echo "Tip: system timezone should be Asia/Ho_Chi_Minh for 03:00 VN."
  echo "     sudo timedatectl set-timezone Asia/Ho_Chi_Minh"
fi

EXISTING="$(crontab -l 2>/dev/null || true)"
if echo "$EXISTING" | grep -Fq "$BACKUP_SCRIPT"; then
  echo "Cron already installed for ${BACKUP_SCRIPT}"
else
  {
    echo "$EXISTING"
    echo "# VStock SQLite backup — weekly Sunday 03:00"
    echo "$CRON_LINE"
  } | grep -v '^$' | crontab -
  echo "Installed cron:"
  echo "  $CRON_LINE"
fi

echo
echo "Run a backup now:"
echo "  ${BACKUP_SCRIPT}"
echo
crontab -l | grep -F "$BACKUP_SCRIPT" || true
