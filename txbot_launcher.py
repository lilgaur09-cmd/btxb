from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def resolve_app_path() -> Path:
    """Return the TXBOT app source file for local runs and PyInstaller bundles."""
    if hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).resolve().parent

    candidate_paths = [
        base_dir / "txbot_app.py",
        base_dir / "src" / "txbot_app.py",
        Path(__file__).resolve().parent / "txbot_app.py",
    ]

    for candidate in candidate_paths:
        if candidate.exists():
            return candidate

    raise FileNotFoundError("Could not find txbot_app.py for TXBOT launch.")


def main() -> int:
    app_path = resolve_app_path()
    host = "127.0.0.1"
    port = "8503"

    if getattr(sys, "frozen", False):
        from streamlit.web import bootstrap

        sys.path.insert(0, str(app_path.parent))
        bootstrap.run(
            str(app_path),
            False,
            [],
            {
                "server.headless": True,
                "server.address": host,
                "server.port": int(port),
            },
        )
        return 0

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.headless",
        "true",
        "--server.address",
        host,
        "--server.port",
        port,
    ]
    process = subprocess.Popen(
        cmd,
        cwd=str(app_path.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())