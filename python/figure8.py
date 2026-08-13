"""
Reproduce Figure 8 from Bansak, Blanco, Coon & Dieringer (2025),
"Border Walls and Death on the US-Mexico Border": the danger index
overlaid with the hot-spot analysis results -- extended here to show both
the pre-SFA and post-SFA hot spots (the original combines both periods
into one map; this version keeps them as two panels so each period's
significant cells can be read against the danger index without visual
overlap). See danger_index_common.render_overlay_figure()'s docstring for
the full design rationale, and DANGER_INDEX_METHODOLOGY.md for the danger
index itself.

To run (from the repo root): .venv/bin/python python/figure8.py
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

dc.render_overlay_figure(out_filename="figure8_reproduction.png")
