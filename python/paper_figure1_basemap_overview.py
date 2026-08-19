"""
Paper Figure 1: basemap + vegetation density + temperature + slope,
2x2 panel. No in-image header -- the caption is typed out directly in
the Word manuscript instead. See grand_overview_common.py.

To run (from the repo root): .venv/bin/python python/paper_figure1_basemap_overview.py
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
import grand_overview_common as gc

gc.render_grand_overview(out_filename="paper_figure1_basemap_overview.png")
