from __future__ import annotations

import asyncio
import os
import socket
import sys

# Windows' Proactor loop can print noisy ConnectionResetError callbacks when a browser
# refreshes/closes a Streamlit WebSocket. Streamlit itself can continue running, but the
# Selector policy avoids that specific Proactor transport path on Python 3.12.
if sys.platform.startswith("win") and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
os.environ["REEF_ENABLE_EDITING"] = "1"


def dashboard_port() -> int:
    """Select a free local port when 8501 is already occupied."""
    for port in range(8501, 8511):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            occupied = probe.connect_ex(("127.0.0.1", port)) == 0
        if not occupied:
            return port
    raise RuntimeError("Ports 8501-8510 are occupied")


port = dashboard_port()

from streamlit.web import cli as stcli

sys.argv = [
    "streamlit",
    "run",
    "Executive_Forecast.py",
    "--server.address=127.0.0.1",
    f"--server.port={port}",
    "--browser.gatherUsageStats=false",
]
raise SystemExit(stcli.main())
