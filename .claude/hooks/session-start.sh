#!/bin/bash
set -euo pipefail

# Only needed in Claude Code on the web containers; local machines manage
# their own ffmpeg/espeak-ng installs (see README).
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

export DEBIAN_FRONTEND=noninteractive

# System deps: ffmpeg (clip cutting/probing) and espeak-ng (offline demo audio)
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v espeak-ng >/dev/null 2>&1; then
  # `|| true`: unreachable third-party apt sources must not fail the hook
  apt-get update -qq || true
  apt-get install -y -qq ffmpeg espeak-ng
fi

# Python deps (yt-dlp)
python3 -m pip install --quiet --disable-pip-version-check -r "$CLAUDE_PROJECT_DIR/requirements.txt"

echo "clip pipeline environment ready: $(ffmpeg -version | head -1 | cut -d' ' -f1-3), espeak-ng $(espeak-ng --version | cut -d' ' -f4), yt-dlp $(yt-dlp --version)"
