from __future__ import annotations
import os
import sys
from pathlib import Path

# Ensure "src" is on sys.path for tests
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
