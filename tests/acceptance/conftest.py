"""Make the evidence-pack generator importable by the acceptance tests."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_DIR = REPO_ROOT / "tools" / "evidence"
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))
