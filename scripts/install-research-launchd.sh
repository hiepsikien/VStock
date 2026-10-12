#!/usr/bin/env bash
# Install a launchd job on macOS that runs one research session after the close:
# Monday–Friday at 15:30 and 20:00, plus Tuesday–Saturday at 08:00, local time. Entrade adds the
# daily bar only some time after the close, so the later runs retry and rewrite the same session
# from the same closed bars; the morning run is the last chance before the next session opens.
# The machine clock must be on Asia/Ho_Chi_Minh.
#
# Run once from the repo:
#   bash scripts/install-research-launchd.sh
# Remove:
#   launchctl bootout "gui/$(id -u)/com.vstock.research-session"
#   rm ~/Library/LaunchAgents/com.vstock.research-session.plist
#
# TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, when set in the shell that runs this script, are
# copied into the job so a failed run sends an alert.

set -euo pipefail

LABEL="com.vstock.research-session"
VSTOCK_DIR="${VSTOCK_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
RESEARCH_DIR="${VSTOCK_DIR}/research"
PYTHON="${RESEARCH_DIR}/.venv/bin/python"
PLIST="${HOME}/Library/LaunchAgents/${LABEL}.plist"
LOG="${HOME}/Library/Logs/vstock-research-session.log"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing ${PYTHON}: create the research venv first (see README)." >&2
  exit 1
fi

if [[ "$(date +%z)" != "+0700" ]]; then
  echo "Warning: the system clock is $(date +%Z) ($(date +%z)), not Asia/Ho_Chi_Minh." >&2
  echo "         launchd uses local time, so 15:30 here is not 15:30 in Vietnam." >&2
fi

xml_escape() {
  local value="$1"
  value="${value//&/&amp;}"
  value="${value//</&lt;}"
  value="${value//>/&gt;}"
  printf '%s' "$value"
}

TELEGRAM_ENV=""
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
  TELEGRAM_ENV="    <key>TELEGRAM_BOT_TOKEN</key><string>$(xml_escape "$TELEGRAM_BOT_TOKEN")</string>
    <key>TELEGRAM_CHAT_ID</key><string>$(xml_escape "$TELEGRAM_CHAT_ID")</string>"
fi

INTERVALS=""
add_interval() {
  INTERVALS+="    <dict><key>Weekday</key><integer>$1</integer><key>Hour</key><integer>$2</integer><key>Minute</key><integer>$3</integer></dict>
"
}
for weekday in 1 2 3 4 5; do
  add_interval "$weekday" 15 30
  add_interval "$weekday" 20 0
done
for weekday in 2 3 4 5 6; do
  add_interval "$weekday" 8 0
done

mkdir -p "$(dirname "$PLIST")" "$(dirname "$LOG")"
umask 077
cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(xml_escape "$PYTHON")</string>
    <string>-m</string>
    <string>app.scheduled</string>
    <string>--after-close</string>
  </array>
  <key>WorkingDirectory</key><string>$(xml_escape "$RESEARCH_DIR")</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key><string>.</string>
${TELEGRAM_ENV}
  </dict>
  <key>StartCalendarInterval</key>
  <array>
${INTERVALS}  </array>
  <key>StandardOutPath</key><string>$(xml_escape "$LOG")</string>
  <key>StandardErrorPath</key><string>$(xml_escape "$LOG")</string>
</dict>
</plist>
EOF

plutil -lint "$PLIST" >/dev/null
launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "Installed ${PLIST}"
echo "Log: ${LOG}"
echo
echo "Run it now (skips during trading hours):"
echo "  launchctl kickstart gui/$(id -u)/${LABEL}"
echo
echo "A sleeping Mac runs a missed job when it wakes; a Mac that is shut down misses it."
echo "To wake the machine before the first run each weekday:"
echo "  sudo pmset repeat wakeorpoweron MTWRF 15:25:00"
