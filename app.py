"""Futures Cheat Code entry"""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).parent / "modules" / "desk_ui.py"), run_name="__main__")
