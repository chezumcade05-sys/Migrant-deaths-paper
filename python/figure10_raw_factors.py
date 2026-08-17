"""
Raw slope + vegetation-density (NDVI) rasters, as pulled into the
environmental-layers CSV -- descriptive, not analytical (no Z-scoring,
no summing into the danger index). Not a reproduction of anything in the
original paper -- a new reference figure showing how two of the danger
index's six inputs are actually distributed.

To run (from the repo root): .venv/bin/python python/figure_raw_factors.py
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
import raw_factor_common as rc

rc.render_raw_factor_rasters(out_filename="figure10_raw_factors.png")
