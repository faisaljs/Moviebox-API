"""Command line launcher for the local MovieBox web app."""

from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent


def _data_dir() -> Path:
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return data_home / "moviebox"


def _port_is_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _open_browser_when_ready(server, url: str) -> None:
    while not server.started and not server.should_exit:
        time.sleep(0.1)
    if server.started and not server.should_exit:
        print(f"MovieBox is ready at {url}", flush=True)
        try:
            webbrowser.open(url)
        except Exception as exc:
            print(f"Could not open a browser automatically: {exc}", file=sys.stderr)
            print(f"Open {url} in your browser.", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="moviebox",
        description="Start MovieBox locally and open its web app.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MOVIEBOX_BIND_HOST", "127.0.0.1"),
        help="Address to bind (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
        help="Port to listen on (default: 8000).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the server without opening a browser.",
    )
    args = parser.parse_args()

    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    if args.host in ("0.0.0.0", "::"):
        browser_host = "127.0.0.1"
    elif args.host in ("127.0.0.1", "localhost"):
        browser_host = "127.0.0.1"
    else:
        browser_host = args.host

    if not args.no_browser and browser_host in ("127.0.0.1", "localhost"):
        if not _port_is_available(args.port):
            print(
                f"Port {args.port} is already in use. Try `moviebox --port {args.port + 1}`.",
                file=sys.stderr,
            )
            return 1

    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("CATALOG_DB", str(data_dir / "catalog.db"))
    sys.path.insert(0, str(APP_DIR))

    try:
        import uvicorn
        import main as app_module
    except ImportError as exc:
        print(f"MovieBox dependencies are missing: {exc}", file=sys.stderr)
        print("Re-run the installer to repair this installation.", file=sys.stderr)
        return 1

    config = uvicorn.Config(
        app_module.app,
        host=args.host,
        port=args.port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    url = f"http://{browser_host}:{args.port}/app"

    if not args.no_browser:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(server, url),
            daemon=True,
        ).start()

    print("Starting MovieBox. Press Ctrl+C to stop.", flush=True)
    try:
        server.run()
    except KeyboardInterrupt:
        print("MovieBox stopped.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
