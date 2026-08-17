"""
Reproduce Figure 1 from Bansak, Blanco, Coon & Dieringer (2025),
"Border Walls and Death on the US-Mexico Border": the geographic-features
reference map (state boundary, roads, cities, Sonoran Desert outline,
Tohono O'odham Nation Reservation, border fencing by period) -- the one
figure in the original paper this reproduction hadn't rebuilt yet.

To run (from the repo root): .venv/bin/python python/figure1.py
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
import basemap_white_common as bwc

bwc.render_figure1()
