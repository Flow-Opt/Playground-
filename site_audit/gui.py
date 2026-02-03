from __future__ import annotations

import subprocess
import sys


def main() -> int:
    """Entry point to launch Streamlit GUI.

    Allows: `site-audit-gui` after pip install -e .
    """
    cmd = [sys.executable, "-m", "streamlit", "run", "app.py"]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
