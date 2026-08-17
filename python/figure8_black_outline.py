"""
Figure 8 variant: black/dark-gray outlines for hot spot cells instead of purple.
Saves as figure8_black_outline.png so it doesn't overwrite the main figure8_reproduction.png.
"""

import os
import sys
from pathlib import Path

_VENV_DIR = Path(__file__).resolve().parent.parent / ".venv"
_VENV_PYTHON = _VENV_DIR / "bin" / "python"
if _VENV_PYTHON.exists() and Path(sys.prefix).resolve() != _VENV_DIR.resolve():
    os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

import basemap_common as bc
import hotspot_common as hc
import danger_index_common as dc

# Temporarily swap overlay colors to black/dark gray
dc.OVERLAY_99 = "#000000"
dc.OVERLAY_95 = "#555555"

dc.render_overlay_figure(out_filename="figure8_black_outline.png")
