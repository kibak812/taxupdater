#!/usr/bin/env bash
set -euo pipefail

APP_MODULE="${APP_MODULE:-src.web.app:app}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8001}"
VENV_DIR="${VENV_DIR:-taxupdater_venv}"

if ! command -v lsof >/dev/null 2>&1; then
    echo "Error: lsof is required for the port guard." >&2
    exit 1
fi

listeners="$(lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)"

if [[ -n "${listeners}" ]]; then
    pids="$(printf '%s\n' "${listeners}" | awk 'NR > 1 {print $2}' | sort -u)"
    own_pids=""
    conflict_details=""

    for pid in ${pids}; do
        command_line="$(ps -p "${pid}" -o command= 2>/dev/null || true)"
        if [[ "${command_line}" == *"${APP_MODULE}"* ]]; then
            own_pids="${own_pids} ${pid}"
        else
            conflict_details="${conflict_details}
PID ${pid}: ${command_line}"
        fi
    done

    if [[ -n "${conflict_details}" ]]; then
        echo "Error: port ${PORT} is already used by another process:${conflict_details}" >&2
        echo >&2
        echo "Current listeners:" >&2
        printf '%s\n' "${listeners}" >&2
        echo >&2
        echo "Stop the conflicting process or start TaxUpdater with another port, e.g. PORT=8011 ./run.sh" >&2
        exit 1
    fi

    if [[ -n "${own_pids}" ]]; then
        echo "TaxUpdater is already running on ${HOST}:${PORT} (PID(s):${own_pids})."
        echo "Dashboard: http://${HOST}:${PORT}/dashboard"
        exit 0
    fi
fi

source "${VENV_DIR}/bin/activate"
exec python -m uvicorn "${APP_MODULE}" --host "${HOST}" --port "${PORT}" --reload
