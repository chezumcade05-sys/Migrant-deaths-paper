"""
Paper Figure 8: danger index with hot spots overlaid, both periods, black
outlines (99% confidence)/dark gray (95% confidence) for visibility. No
"Figure 8" header -- the caption is typed out directly in the Word
manuscript instead. The two panels keep their own "Pre-SFA"/"Post-SFA"
labels, since without them there's no way to tell the two stacked panels
apart. Same underlying data/plotting as danger_index_common.render_overlay_figure()
(used by the original-paper-numbered figure8.py / the black-outline
variant figure8_black_outline.py); this is just a relabeled, header-free
copy for the current paper's own figure order.

To run (from the repo root): .venv/bin/python python/paper_figure8_overlay.py
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

# Black/dark-gray hot-spot outlines instead of the default red/orange --
# substantially more visible against the danger index's red-heavy palette.
hc.HOT_99 = "#000000"
hc.HOT_95 = "#555555"

dc.render_overlay_figure(
    out_filename="paper_figure8_overlay.png",
    title_pre="Pre-SFA (2000-2007)",
    title_post="Post-SFA (2008-2019)",
)
