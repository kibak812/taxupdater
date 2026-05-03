#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LABEL="taxupdater-ngrok-starter"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
NGROK_URL="${1:-${NGROK_URL:-https://minnie-unfloured-premorbidly.ngrok-free.dev}}"
NGROK_BIN="$(command -v ngrok)"
LOG_FILE="$HOME/Library/Logs/taxupdater-ngrok.log"

if [[ "$NGROK_URL" != https://* ]]; then
  NGROK_URL="https://$NGROK_URL"
fi

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs" "$ROOT_DIR/logs"

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl remove "$LABEL" >/dev/null 2>&1 || true

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>-lc</string>
    <string>/usr/bin/pgrep -x ngrok >/dev/null || exec "$NGROK_BIN" http 8001 --url "$NGROK_URL" --log stdout</string>
  </array>
  <key>StandardOutPath</key>
  <string>$LOG_FILE</string>
  <key>StandardErrorPath</key>
  <string>$LOG_FILE</string>
  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
EOF

launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "ngrok login agent installed."
echo "Static URL: $NGROK_URL"
echo "Log: $LOG_FILE"
echo "Status: launchctl print gui/$(id -u)/$LABEL"
