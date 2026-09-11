"""Spiritus 1-Click Autonomous Demo & Cloudflare Quick Tunnel Daemon.

Launches local FastAPI backend on port 8000 and connects an ephemeral
Cloudflare Quick Tunnel (https://*.trycloudflare.com), outputting the public URL
for live hackathon evaluation.
"""
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
import urllib.request
import urllib.error

ROOT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = ROOT_DIR / "backend"
URL_LOG_FILES = [ROOT_DIR / "demo_url.txt", BACKEND_DIR / "demo_url.txt"]


def is_backend_alive(port=8000) -> bool:
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/config")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def main():
    print("=" * 64)
    print("🚀 SPIRITUS AUTONOMOUS HARNESS — LIVE DEMO RUNNER")
    print("=" * 64)

    # 1. Verify / Start Backend
    uvicorn_proc = None
    if is_backend_alive(8000):
        print("✓ Backend is already running on http://127.0.0.1:8000")
    else:
        print("▶ Starting FastAPI backend on http://127.0.0.1:8000...")
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "app:app",
            "--app-dir",
            str(BACKEND_DIR),
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ]
        uvicorn_proc = subprocess.Popen(
            cmd,
            cwd=str(BACKEND_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        ready = False
        for _ in range(20):
            time.sleep(0.5)
            if is_backend_alive(8000):
                ready = True
                break
        if not ready:
            print("❌ Backend failed to start within 10s.")
            if uvicorn_proc:
                uvicorn_proc.kill()
            sys.exit(1)
        print("✓ FastAPI backend successfully started.")

    # 2. Locate cloudflared binary
    cloudflared_bin = "cloudflared"
    system_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "bin" / "cloudflared.exe",
        Path("C:/Users/lupixele/bin/cloudflared"),
        Path("C:/Program Files (x86)/cloudflared/cloudflared.exe"),
        Path("C:/Program Files/cloudflared/cloudflared.exe"),
    ]
    for p in system_paths:
        if p.exists():
            cloudflared_bin = str(p)
            break

    print(f"▶ Launching Cloudflare Quick Tunnel using: {cloudflared_bin}")
    tunnel_cmd = [
        cloudflared_bin,
        "tunnel",
        "--url",
        "http://127.0.0.1:8000",
        "--no-autoupdate",
    ]

    try:
        tunnel_proc = subprocess.Popen(
            tunnel_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
        )
    except Exception as e:
        print(f"❌ Failed to launch cloudflared: {e}")
        if uvicorn_proc:
            uvicorn_proc.terminate()
        sys.exit(1)

    # 3. Stream output and scrape public URL
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    public_url = None

    print("▶ Generating secure HTTPS public tunnel...")
    start_time = time.time()

    while time.time() - start_time < 30:
        line = tunnel_proc.stdout.readline()
        if not line and tunnel_proc.poll() is not None:
            break
        if line:
            match = url_pattern.search(line)
            if match:
                public_url = match.group(0)
                break

    if not public_url:
        print("❌ Could not extract TryCloudflare tunnel URL within 30s.")
        tunnel_proc.terminate()
        if uvicorn_proc:
            uvicorn_proc.terminate()
        sys.exit(1)

    for out_file in URL_LOG_FILES:
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(public_url + "\n")
        except Exception:
            pass

    print("\n" + "=" * 64)
    print("✨ SPIRITUS DEMO IS LIVE & ACCESSIBLE PUBLICLY")
    print(f"  Local Address:  http://127.0.0.1:8000")
    print(f"  Public Tunnel:  {public_url}")
    print("=" * 64)
    print("Press Ctrl+C to terminate the demo.\n")

    def cleanup(signum=None, frame=None):
        print("\n▶ Shutting down demo processes...")
        tunnel_proc.terminate()
        try:
            tunnel_proc.wait(timeout=3)
        except Exception:
            tunnel_proc.kill()

        if uvicorn_proc:
            uvicorn_proc.terminate()
            try:
                uvicorn_proc.wait(timeout=3)
            except Exception:
                uvicorn_proc.kill()
        print("✓ Shutdown complete.")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        while True:
            time.sleep(1)
            if tunnel_proc.poll() is not None:
                print("⚠️ Cloudflare tunnel terminated.")
                break
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
