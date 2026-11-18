"""Make the delivered modules importable without copying or forking their code."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for directory in (ROOT / "a/backend", ROOT / "b", ROOT / "c/src"):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

