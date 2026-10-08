#!/usr/bin/env bash
# Run as the SSH login user on the Debian VM, not with sudo.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
if [[ $(id -u) == 0 ]]; then echo 'Run this script without sudo.'; exit 1; fi
cd "$ROOT/backend"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
LLM_PROVIDER=mock .venv/bin/python -m unittest discover -s tests -v
cd "$ROOT/frontend"
npm ci --no-fund
npm test
./node_modules/.bin/tsc --noEmit --incremental false
BACKEND_URL=http://127.0.0.1:8000 NEXT_TELEMETRY_DISABLED=1 npm run build
printf '\nPREPARE COMPLETE. Next: configure backend/.env, then install services.\n'
