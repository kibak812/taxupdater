#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NGROK_URL="${1:-${NGROK_URL:-https://minnie-unfloured-premorbidly.ngrok-free.dev}}"
PID_FILE="$ROOT_DIR/logs/ngrok.pid"
LOG_FILE="$ROOT_DIR/logs/ngrok.log"
LABEL="taxupdater-ngrok"

if [[ "$NGROK_URL" != https://* ]]; then
  NGROK_URL="https://$NGROK_URL"
fi

mkdir -p "$ROOT_DIR/logs"

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  echo "ngrok is already running:"
  echo "  url: $NGROK_URL"
  exit 0
fi

pkill -x ngrok 2>/dev/null || true
rm -f "$PID_FILE"

echo "Starting ngrok tunnel:"
echo "  $NGROK_URL -> http://localhost:8001"
echo ""
launchctl submit -l "$LABEL" -- /bin/sh -lc "cd '$ROOT_DIR' && exec ngrok http 8001 --url '$NGROK_URL' --log stdout >> '$LOG_FILE' 2>&1"
sleep 3

if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  pgrep -x ngrok | head -1 > "$PID_FILE" || true
  echo "ngrok started."
  echo "  log: $LOG_FILE"
  echo "  status: ./scripts/setup/status_ngrok_dev_domain.sh"
else
  echo "ngrok failed to start. Recent log:"
  tail -n 40 "$LOG_FILE" || true
  exit 1
fi
