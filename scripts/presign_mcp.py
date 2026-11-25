"""Start the TraceIntel pre-sign MCP server over stdio.

    uv run python scripts/presign_mcp.py

Reads RPC URLs (and, for explain=true, OPENROUTER_API_KEY) from .env or the environment.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)  # settings read .env from the project root

from app.presign.mcp_server import main  # noqa: E402

if __name__ == "__main__":
    main()
