# I-Care initial deployment: Debian 13 / Google Compute Engine

Target: icarebridge.org / www.icarebridge.org -> 136.116.208.55.
Run commands inside the VM, as SSH login user siqi, unless marked LOCAL.
This is an initial-install kit, not a claim that deployment is complete.

## 1. Upload and extract

Use Google Cloud Console > VM instances > SSH > Upload file. The browser SSH
uploader places files in the login user's home directory. Upload icare-deploy.tar.gz.

```bash
cd ~
# Only on a fresh deployment: do not extract over an existing installation.
test ! -e icare-release && tar -xzf icare-deploy.tar.gz
cd ~/icare-release
sha256sum -c SHA256SUMS
bash deploy/google-cloud/prepare.sh
```

prepare.sh installs dependencies, runs tests, and builds Next.js production output.
It does not start public services, migrate user data, or configure model credentials.
Do not close the SSH tab while this initial build runs. If it fails, retain the error.
No source directory, node_modules, or .next directory from the Mac is reused as a binary.

## 2. Configure provider privately

```bash
cd ~/icare-release
install -m 600 deploy/google-cloud/backend.env.example backend/.env
nano backend/.env
```

Use the provider URL, chat model, embedding model, reasoning setting and API key
from your working local configuration. Do not post the key in chat/screenshots.
The example shows OpenAI settings; it does NOT assert those are the current local
settings. Gemini through its OpenAI-compatible endpoint also uses LLM_PROVIDER=openai.
Choose data/kb.openai.sqlite3 for text-embedding-3-small or data/kb.gemini.sqlite3
for gemini-embedding-001. Do not mix embedding models and knowledge bases.
Save nano with Ctrl+O, Enter, then Ctrl+X.

The bundle intentionally contains no users, conversations, assessment history,
authentication tokens, .env, or private keys. Both KBs are read-only snapshots of
education content; the working local databases are untouched.
New app data will be created under ~/icare-data/app.sqlite3, outside this release.
Decide whether to migrate existing accounts/history BEFORE opening registration.
Migration requires a consistent SQLite backup, not copying a live database file.

## 3. Start private services

```bash
cd ~/icare-release
bash deploy/google-cloud/install-services.sh
```

Creates systemd units with startup on boot and restart on failure, one backend
worker for SQLite, both services listening only on 127.0.0.1. Installation refuses
existing I-Care unit files and occupied ports. The .env is read by the backend only.
The preparation/build process has not verified the real model API; test chat later.

## 4. HTTPS

Allow inbound TCP 80 and 443 to this VM in Google Cloud firewall rules (HTTP/HTTPS
network tags need matching allow rules). Keep ports 3000 and 8000 private.
Install Caddy using https://caddyserver.com/docs/install#debian-ubuntu-raspbian .
Review the existing /etc/caddy/Caddyfile before replacement; for this new VM:

```bash
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.before-icare
sudo caddy validate --config ~/icare-release/deploy/google-cloud/Caddyfile --adapter caddyfile
sudo install -m 644 ~/icare-release/deploy/google-cloud/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Caddy obtains/renews HTTPS certificates and redirects www to the main HTTPS domain.
The /api route is sent directly to FastAPI with streaming flush enabled.
Do not add a restrictive read timeout that cuts off chat responses.

## 5. Acceptance and operation

Check HTTPS on root and www, chat streaming with actual model, register/login,
self-assessments and history, PDFs/library/videos, and mobile browser navigation.
Retest on the previously affected company network. A production build does not
by itself fix the previously reported mobile hydration mismatch; check that too.

```bash
sudo systemctl status icare-backend icare-frontend caddy --no-pager
curl -I https://icarebridge.org
curl -I https://www.icarebridge.org
```

Review logs privately with journalctl -u SERVICE; avoid sharing personal content.
Before opening to participants: finish user-data decision, configure consistent
SQLite backups to storage outside this VM, test a restore, and add uptime alerts.
A disk on this same VM alone is not an off-machine backup.

This first bundle updates Next.js/React in the deployment copy only. The original
Mac manifests/runtime remain unchanged. Subsequent releases must preserve these
patched dependencies. Record exact versions in frontend/package.json/package-lock.json.
Do not run prepare.sh on a live release: build a fresh release and switch services
after checks, retaining the previous release for rollback.

## Preparation verification (2026-10-05)

The isolated Mac deployment copy passed 37 backend tests (Python 3.12), 11 frontend
tests, TypeScript checks and Next.js 15.5.27 production build. React/React DOM are
pinned to 19.0.8; overrides postcss 8.5.29 and nanoid 3.3.20 resolve the remaining
reported transitive advisories. npm install reported zero known vulnerabilities
at preparation time (not a guarantee against future advisories).
A temporary production server returned the homepage, 25-guide/12-video library,
three-instrument catalogue and PSS PDF through the existing backend proxy.
The VM's Python 3.13 installation, systemd units, Caddy and real-model access still
need on-server verification. No files have been uploaded to the VM by this tool.
