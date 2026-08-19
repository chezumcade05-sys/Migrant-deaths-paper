"""
VESTIGIAL: superseded by the raw-factor rasters (raw_factor_common.py)
and then by Figure 1's basemap panel (grand_overview_common.py). Never
committed/used in any delivered figure set. Kept for reference only.

Bare topography basemap -- no death points, fencing, danger-index colors,
hot spots, or labels. Just the terrain underlying every other figure in
this reproduction. Not a reproduction of anything in the original paper --
a new reference figure.

To run (from the repo root): .venv/bin/python python/figure_topography.py
"""

import os
import sys
from pathlib import Path

_VENV_DIR = Path(__file__).resolve().parent.parent / ".venv"
_VENV_PYTHON = _VENV_DIR / "bin" / "python"
if _VENV_PYTHON.exists() and Path(sys.prefix).resolve() != _VENV_DIR.resolve():
    os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

import basemap_common as bc
import topography_common as tc

tc.render_topography_basemap(out_filename="figure_topography_basemap.png", title="Topography")
