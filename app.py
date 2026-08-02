"""Futures Cheat Code — Streamlit entrypoint."""
import sys
from pathlib import Path

# Ensure repo root is on path so `from modules.X` works when Streamlit runs app.py
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load the desk as a package module (not runpy on a file inside modules/,
# which puts modules/ on sys.path and breaks `from modules.crypto_rank`).
import runpy

runpy.run_module("modules.desk_ui", run_name="__main__")
