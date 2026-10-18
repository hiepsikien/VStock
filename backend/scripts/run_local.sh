#!/bin/sh
# Local API for the Expo app. Bind every interface so a phone on Metro can reach it.
set -eu
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate
pip install -q -r requirements.txt

export VSTOCK_AUDIO_DIR="${VSTOCK_AUDIO_DIR:-$(pwd)/var/audio}"
mkdir -p "$VSTOCK_AUDIO_DIR"

python - << 'PY'
from app.sonify.audio import find_musescore, general_soundfont

binary = find_musescore()
font = general_soundfont()
print(f"MuseScore: {binary or 'NOT FOUND'}")
print(f"Soundfont: {font or 'MuseScore built-in'}")
if binary is None:
    raise SystemExit(
        "Install MuseScore, then run this again.\n"
        "  brew install --cask musescore\n"
        "  brew install ffmpeg"
    )
PY

echo "API: http://0.0.0.0:8000  (audio cache: $VSTOCK_AUDIO_DIR)"
echo "In another terminal, from the repo root: npm run start:local"
exec uvicorn app.main:app --reload --host 0.0.0.0 --port "${PORT:-8000}"
