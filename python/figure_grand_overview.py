"""
2x2 grand overview: white reference basemap, vegetation density,
temperature, and slope, side by side. Not a reproduction of anything in
the original paper -- a single-glance summary combining Figure 1's
reference layers with three of the danger index's raw inputs.

To run (from the repo root): .venv/bin/python python/figure_grand_overview.py
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

gc.render_grand_overview(out_filename="figure1_grand_overview.png")
