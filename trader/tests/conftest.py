import sys
from pathlib import Path

# make `kenui_trader` importable when pytest runs from the repo root or from trader/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
