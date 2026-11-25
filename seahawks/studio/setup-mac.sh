#!/bin/bash
# One-time setup for the Hawks War Room studio on Jesse's Mac.
# Safe to re-run: it only creates what's missing.
set -euo pipefail

ROOT="$HOME/Documents/07 Seahawks"
STUDIO="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$STUDIO/../.." && pwd)"

echo "== Folders in $ROOT"
for d in "01 Drop Videos Here" "02 Ready for Review" "03 Approved" "04 Raw Footage" "05 Prep Packs" "06 Music & Brand"; do
  mkdir -p "$ROOT/$d"
done
if [ ! -f "$ROOT/00 How this works.txt" ]; then
cat > "$ROOT/00 How this works.txt" <<'TXT'
HAWKS WAR ROOM STUDIO

1. Drop every file for an episode into "01 Drop Videos Here":
   your main recording, friends' clips or voice memos, footage from a second spot.
2. Each night Claude checks that folder. If there's anything new it builds:
   the edited full episode with graphics, 3-6 reels, thumbnail options,
   YouTube titles/description/chapters, and captions.
3. Open "02 Ready for Review/<episode>/review.html" and watch.
   Reply to Claude with notes ("drop reel 2", "cut 12:40-13:05") or "approve <episode>".
4. Approved episodes move to "03 Approved". Your original files move to "04 Raw Footage".
   Nothing is ever deleted and nothing is published without your OK.

"05 Prep Packs" has the pregame research and questions for the crew.
Put intro/outro music and art you own in "06 Music & Brand".
"Studio" holds the tools. You don't need to touch it.
TXT
fi

echo "== Tools"
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required. Install it from https://brew.sh, then re-run this script." >&2
  exit 1
fi
command -v ffmpeg >/dev/null 2>&1 || brew install ffmpeg
command -v node >/dev/null 2>&1 || brew install node
command -v python3 >/dev/null 2>&1 || brew install python

echo "== Python packages (Whisper transcription, face finder)"
[ -d "$STUDIO/.venv" ] || python3 -m venv "$STUDIO/.venv"
"$STUDIO/.venv/bin/pip" install -q --upgrade pip
"$STUDIO/.venv/bin/pip" install -q -r "$STUDIO/requirements.txt"

echo "== Graphics renderer"
(cd "$STUDIO" && npm install --silent && npx playwright install chromium)

if [ ! -f "$STUDIO/config.json" ]; then
  sed "s#~/Documents/07 Seahawks/Studio/site#$REPO#" "$STUDIO/config.example.json" > "$STUDIO/config.json"
fi

echo "== Check"
"$STUDIO/.venv/bin/python" "$STUDIO/studio.py" status
echo "Done. The first transcription downloads the Whisper model (about 1.5 GB) once."
