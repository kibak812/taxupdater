#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="$ROOT_DIR/logs/ngrok.pid"
LABEL="taxupdater-ngrok"

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  launchctl remove "$LABEL"
  rm -f "$PID_FILE"
  echo "ngrok stopped."
  exit 0
fi

if pkill -x ngrok 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "ngrok stopped."
else
  echo "ngrok is not running."
fi
