#!/usr/bin/env python3
"""macOS service management for this checkout. No shell secrets or .env changes.

build -> install -> status. Use stop before deliberate maintenance; use update
after frontend edits. launchd handles exits; a local-only watchdog handles hangs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import time
from urllib.request import urlopen
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".runtime"
LOGS = STATE / "logs"
AGENTS = Path.home() / "Library/LaunchAgents"
PREFIX = "org.icare.local."
DOMAIN = f"gui/{os.getuid()}"
SERVICES = ("backend", "frontend", "ngrok", "watchdog")
PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def initialize():
    STATE.mkdir(mode=0o700, exist_ok=True)
    LOGS.mkdir(mode=0o700, exist_ok=True)


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n")
    temp.chmod(0o600)
    temp.replace(path)


def target(name):
    return f"{DOMAIN}/{PREFIX}{name}"


def ctl(*args, check=True):
    return subprocess.run(["/bin/launchctl", *args], capture_output=True, text=True, check=check)


def loaded(name):
    return ctl("print", target(name), check=False).returncode == 0


def healthy(url):
    try:
        with urlopen(url, timeout=6) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


def wait_ready(url, seconds=40):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if healthy(url):
            return True
        time.sleep(1)
    return False


def event(message):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}", flush=True)


def rotate_logs():
    # Truncate the same inode so existing launchd stdout descriptors keep working.
    for path in LOGS.glob("*.log"):
        if path.name.endswith(".previous.log"):
            continue
        if path.stat().st_size > 10 * 1024 * 1024:
            shutil.copyfile(path, path.with_suffix(".previous.log"))
            with path.open("w"):
                pass


def build():
    """Build in an isolated release; never touch the development .next directory."""
    initialize()
    frontend = ROOT / "frontend"
    config = read_json(STATE / "config.json", {})
    node = config.get("node") or shutil.which("node")
    npm = shutil.which("npm")
    if not node or not npm:
        raise RuntimeError("node and npm must be installed")
    digest = hashlib.sha256((frontend / "package-lock.json").read_bytes()).hexdigest()[:16]
    dependencies = STATE / "dependencies" / digest / "node_modules"
    if not dependencies.exists():
        dependencies.parent.mkdir(parents=True, exist_ok=True)
        staging = dependencies.with_name("node_modules.building")
        if staging.exists():
            shutil.rmtree(staging)
        event("Snapshotting installed frontend dependencies")
        shutil.copytree(frontend / "node_modules", staging, symlinks=True)
        staging.rename(dependencies)
    release = STATE / "releases" / f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    release.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(frontend, release, ignore=shutil.ignore_patterns(
        "node_modules", ".next", ".git", "tsconfig.tsbuildinfo", "out", "output"))
    (release / "node_modules").symlink_to(dependencies, target_is_directory=True)
    env = {**os.environ, "PATH": PATH, "NEXT_TELEMETRY_DISABLED": "1", "BACKEND_URL": "http://127.0.0.1:8000"}
    event(f"Building release {release.name}; existing service stays online")
    subprocess.run([npm, "run", "build"], cwd=release, env=env, check=True)
    # Start on an OS-selected port. No existing local port is interrupted.
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with (LOGS / "build-smoke.log").open("ab") as log:
        process = subprocess.Popen([node, str(release / "node_modules/next/dist/bin/next"),
            "start", "--hostname", "127.0.0.1", "--port", str(port)], cwd=release,
            env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        try:
            if not wait_ready(f"http://127.0.0.1:{port}/"):
                raise RuntimeError("Release smoke check failed; active release is unchanged")
            if not healthy(f"http://127.0.0.1:{port}/api/library"):
                raise RuntimeError("Backend proxy smoke check failed; active release is unchanged")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    write_json(STATE / "candidate.json", {"path": str(release)})
    if not (STATE / "current.json").exists():
        write_json(STATE / "current.json", {"path": str(release)})
    event("Build and HTTP/proxy smoke checks passed")


def prepare(url):
    initialize()
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.path not in ("", "/") or parsed.query or parsed.username:
        raise ValueError("Provide the existing HTTPS ngrok hostname only")
    node, ngrok = shutil.which("node"), shutil.which("ngrok")
    if not node or not ngrok:
        raise RuntimeError("node and ngrok must be installed")
    if not (STATE / "current.json").exists():
        raise RuntimeError("Run build first")
    ngrok_config = Path.home() / "Library/Application Support/ngrok/ngrok.yml"
    if not ngrok_config.exists():
        raise RuntimeError("Existing ngrok config not found; no credentials were changed")
    write_json(STATE / "config.json", {"node": node, "ngrok": ngrok,
        "ngrok_config": str(ngrok_config), "url": url.rstrip("/")})
    staging = STATE / "launchagents"
    staging.mkdir(exist_ok=True)
    for name in SERVICES:
        plist = {"Label": PREFIX + name,
            "ProgramArguments": [sys.executable, str(Path(__file__).resolve()), "run", name],
            "WorkingDirectory": str(ROOT), "RunAtLoad": True,
            "EnvironmentVariables": {"PATH": PATH, "PYTHONUNBUFFERED": "1", "NEXT_TELEMETRY_DISABLED": "1"},
            "StandardOutPath": str(LOGS / f"{name}.log"),
            "StandardErrorPath": str(LOGS / f"{name}.log"), "Umask": 0o077}
        if name == "watchdog":
            plist["StartInterval"] = 60
        else:
            plist.update(KeepAlive=True, ThrottleInterval=10, ExitTimeOut=20)
        with (staging / f"{PREFIX}{name}.plist").open("wb") as stream:
            plistlib.dump(plist, stream)
    event("Prepared four launch agents; no tokens or .env values copied into them")


def start():
    for name in SERVICES:
        if not loaded(name):
            path = AGENTS / f"{PREFIX}{name}.plist"
            ctl("enable", target(name))
            ctl("bootstrap", DOMAIN, str(path))
    event("Services loaded; they will also load at user login")


def stop():
    for name in reversed(SERVICES):
        if loaded(name):
            ctl("bootout", target(name))
    event("Services stopped intentionally; use start to resume")


def run(name):
    config = read_json(STATE / "config.json")
    if name == "watchdog":
        return watchdog()
    if name == "frontend":
        release = Path(read_json(STATE / "current.json")["path"])
        os.chdir(release)
        command = [config["node"], str(release / "node_modules/next/dist/bin/next"),
            "start", "--hostname", "127.0.0.1", "--port", "3000"]
    elif name == "backend":
        os.chdir(ROOT / "backend")
        command = [str(ROOT / "backend/.venv/bin/python"), "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", "8000"]
    else:
        command = [config["ngrok"], "http", "http://127.0.0.1:3000", "--url", config["url"],
            "--config", config["ngrok_config"], "--log", "stdout", "--log-format", "json"]
    event(f"Starting {name}")
    os.execv(command[0], command)


def watchdog():
    rotate_logs()
    state = read_json(STATE / "health.json", {})
    for name, url in (("backend", "http://127.0.0.1:8000/health"),
                      ("frontend", "http://127.0.0.1:3000/"),
                      ("ngrok", "http://127.0.0.1:4040/api/tunnels")):
        # Do not resurrect deliberately stopped/uninstalled services.
        if not loaded(name):
            continue
        ok = healthy(url)
        failures = 0 if ok else state.get(name, {}).get("failures", 0) + 1
        restarted = False
        if failures >= 3:
            event(f"{name} failed three local probes; restarting only that service")
            restarted = ctl("kickstart", "-k", target(name), check=False).returncode == 0
            if restarted:
                failures = 0
        state[name] = {"healthy": ok, "failures": failures, "restarted": restarted, "checked_at": time.time()}
    write_json(STATE / "health.json", state)


def update():
    if not loaded("frontend"):
        raise RuntimeError("Start managed services before update")
    build()
    previous = read_json(STATE / "current.json")
    write_json(STATE / "previous.json", previous)
    write_json(STATE / "current.json", read_json(STATE / "candidate.json"))
    ctl("kickstart", "-k", target("frontend"))
    if not wait_ready("http://127.0.0.1:3000/"):
        write_json(STATE / "current.json", previous)
        ctl("kickstart", "-k", target("frontend"))
        raise RuntimeError("New release did not start; previous release restored")
    event("Production frontend updated")


def status():
    for name in SERVICES:
        result = ctl("print", target(name), check=False)
        fields = [line.strip() for line in result.stdout.splitlines()
                  if line.strip().startswith(("state =", "pid =", "last exit code ="))]
        print(f"{name}: {', '.join(fields) if result.returncode == 0 else 'not loaded'}")
    print("Local frontend:", "OK" if healthy("http://127.0.0.1:3000/") else "FAILED")
    print("Local backend:", "OK" if healthy("http://127.0.0.1:8000/health") else "FAILED")
    print("Production release:", read_json(STATE / "current.json", {}).get("path", "none"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["build", "prepare", "install", "start", "stop", "status", "update", "run", "restart", "uninstall"])
    parser.add_argument("service", nargs="?", choices=SERVICES)
    parser.add_argument("--url")
    args = parser.parse_args()
    if args.action == "build": build()
    elif args.action == "prepare":
        if not args.url: parser.error("prepare requires --url")
        prepare(args.url)
    elif args.action == "install":
        import socket
        for port in (3000, 8000, 4040):
            with socket.socket() as sock:
                sock.settimeout(1)
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    raise RuntimeError(f"Port {port} is still in use; verify and stop the old I-Care process before install")
        AGENTS.mkdir(parents=True, exist_ok=True)
        for name in SERVICES:
            source = STATE / "launchagents" / f"{PREFIX}{name}.plist"
            if not source.exists(): raise RuntimeError("Run prepare first")
        for name in SERVICES:
            source = STATE / "launchagents" / f"{PREFIX}{name}.plist"
            destination = AGENTS / source.name
            if destination.exists(): raise RuntimeError(f"Already installed: {destination}; use start/update")
        for name in SERVICES:
            source = STATE / "launchagents" / f"{PREFIX}{name}.plist"
            shutil.copyfile(source, AGENTS / source.name)
            (AGENTS / source.name).chmod(0o644)
        start()
    elif args.action == "uninstall":
        stop()
        for name in SERVICES:
            (AGENTS / f"{PREFIX}{name}.plist").unlink(missing_ok=True)
    elif args.action == "start": start()
    elif args.action == "stop": stop()
    elif args.action == "status": status()
    elif args.action == "update": update()
    elif args.action == "run":
        if not args.service: parser.error("run requires a service")
        run(args.service)
    elif args.action == "restart":
        if not args.service: parser.error("restart requires a service")
        ctl("kickstart", "-k", target(args.service))


if __name__ == "__main__":
    main()
