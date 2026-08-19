"""
VESTIGIAL for the current paper's figure set: superseded by
paper_figure8_overlay.py, which folds this same black/dark-gray outline
fix in directly (this script's own color patch was silently a no-op --
fixed here, then carried over -- see paper_figure8_overlay.py's
docstring). Kept for reference/history.

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

# Temporarily swap overlay colors to black/dark gray. danger_index_common's
# _draw_hotspot_outlines() reads hc.HOT_99/hc.HOT_95 (not a dc.OVERLAY_*
# attribute -- there isn't one), so those are the names that actually need
# patching; hc and dc share the same hotspot_common module object, so this
# patch is visible from inside danger_index_common too.
hc.HOT_99 = "#000000"
hc.HOT_95 = "#555555"

dc.render_overlay_figure(out_filename="figure8_black_outline.png")
