"""Futures Cheat Code — Streamlit entrypoint."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# desk_ui is the full Streamlit UI — importing runs it
import modules.desk_ui  # noqa: F401
