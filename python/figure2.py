"""
Reproduce Figure 2 from Bansak, Blanco, Coon & Dieringer (2025),
"Border Walls and Death on the US-Mexico Border": the danger index map --
but with a rebuilt index using different factors and a different scoring
method than the paper's original. See DANGER_INDEX_METHODOLOGY.md for the
full write-up of what changed and why.

Requires the "sf"-equivalent Python GIS stack (geopandas/pyogrio/shapely)
already used by the other figures, same .venv.
To run (from the repo root): .venv/bin/python python/figure2.py
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

dc.render_danger_index(
    out_filename="figure2_reproduction.png",
    title="Figure 2: Danger Index",
)
