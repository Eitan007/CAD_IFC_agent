#!/usr/bin/env bash

# Starts the regular local stack and opens a separate Windows PowerShell window
# for an ngrok tunnel to the FastAPI server. Intended for WSL development.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v powershell.exe >/dev/null 2>&1; then
    echo "Error: start_main.sh must be run from WSL with Windows PowerShell available."
    exit 1
fi

if ! powershell.exe -NoProfile -Command "if (-not (Get-Command ngrok -ErrorAction SilentlyContinue)) { exit 1 }"; then
    echo "Error: ngrok is not available in Windows PowerShell. Install it, authenticate it, then retry."
    exit 1
fi

echo "Opening a Windows PowerShell window for ngrok on port 8000..."
powershell.exe -NoProfile -Command "Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoExit', '-NoProfile', '-Command', 'ngrok http 8000')"

exec "$REPO_ROOT/start_dev.sh"
