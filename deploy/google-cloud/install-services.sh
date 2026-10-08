#!/usr/bin/env bash
# Initial install only; refuses to replace existing I-Care services.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
ICARE_USER=$(id -un)
ICARE_DATA="$HOME/icare-data"
if [[ $(id -u) == 0 ]]; then echo 'Run without sudo; the script requests sudo where needed.'; exit 1; fi
if [[ ! "$ROOT" =~ ^/[a-zA-Z0-9_./-]+$ || ! "$ICARE_DATA" =~ ^/[a-zA-Z0-9_./-]+$ || ! "$ICARE_USER" =~ ^[a-zA-Z0-9_-]+$ ]]; then echo 'Use a path without spaces or special characters.'; exit 1; fi
for service in backend frontend; do
  if sudo test -e "/etc/systemd/system/icare-$service.service"; then echo "Existing icare-$service service: stop and review update procedure."; exit 1; fi
done
[[ -f "$ROOT/frontend/.next/BUILD_ID" ]] || { echo 'Run prepare.sh first.'; exit 1; }
[[ -f "$ROOT/backend/.env" ]] || { echo 'Configure backend/.env first.'; exit 1; }
chmod 600 "$ROOT/backend/.env"
# Validate configuration and KB alignment without showing credentials or calling a model.
cd "$ROOT/backend"
.venv/bin/python - <<'PY'
import sqlite3
from pathlib import Path
from app.config import get_settings
s = get_settings()
if s.llm_provider != 'openai' or not s.openai_api_key.strip():
    raise SystemExit('Set the real provider and API key in backend/.env before enabling the service.')
p = Path(s.kb_db_path).resolve()
if not p.is_file(): raise SystemExit('Configured knowledge base does not exist.')
c = sqlite3.connect(p.as_uri() + '?mode=ro', uri=True)
row = c.execute("SELECT value FROM meta WHERE key='embed_model'").fetchone()
if not row or row[0] != s.openai_embed_model:
    raise SystemExit('Knowledge-base embedding model does not match OPENAI_EMBED_MODEL.')
if c.execute('SELECT count(*) FROM chunks').fetchone()[0] == 0:
    raise SystemExit('Knowledge base is empty.')
c.close()
print('Provider configuration and knowledge-base model match. No API call made.')
PY
if [[ -n "$(ss -H -ltn '( sport = :3000 or sport = :8000 )')" ]]; then
  echo 'Port 3000 or 8000 is already in use; stop and inspect.'; exit 1
fi
mkdir -p "$ICARE_DATA"
chmod 700 "$ICARE_DATA"
ICARE_TMP=$(mktemp -d)
trap 'rm -rf "$ICARE_TMP"' EXIT
for service in backend frontend; do
  sed -e "s|@ROOT@|$ROOT|g" -e "s|@USER@|$ICARE_USER|g" -e "s|@DATA@|$ICARE_DATA|g" \
    "$ROOT/deploy/google-cloud/icare-$service.service.in" > "$ICARE_TMP/icare-$service.service"
  sudo install -m 644 "$ICARE_TMP/icare-$service.service" "/etc/systemd/system/icare-$service.service"
done
sudo systemctl daemon-reload
sudo systemctl enable --now icare-backend icare-frontend
curl --fail --silent --show-error --retry 15 --retry-connrefused --retry-delay 1 http://127.0.0.1:8000/health
curl --fail --silent --show-error --retry 15 --retry-connrefused --retry-delay 1 -o /dev/null http://127.0.0.1:3000/
printf '\nLocal services ready. Next: HTTPS reverse proxy.\n'
