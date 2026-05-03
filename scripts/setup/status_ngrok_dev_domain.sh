#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="$ROOT_DIR/logs/ngrok.pid"
LABEL="taxupdater-ngrok"

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  PID="$(pgrep -x ngrok | head -1 || true)"
  if [[ -n "$PID" ]]; then
    echo "ngrok process: running (pid $PID)"
  else
    echo "ngrok process: launchctl job active"
  fi
else
  echo "ngrok process: not running"
fi

if curl -fsS http://127.0.0.1:4040/api/tunnels >/tmp/taxupdater-ngrok-tunnels.json; then
  python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("/tmp/taxupdater-ngrok-tunnels.json").read_text())
tunnels = data.get("tunnels", [])
if tunnels:
    print(f"public url: {tunnels[0].get('public_url')}")
else:
    print("public url: unavailable")
PY
else
  echo "public url: unavailable"
fi
