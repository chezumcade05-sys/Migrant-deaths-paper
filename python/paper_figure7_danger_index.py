"""
Paper Figure 7: the rebuilt danger index. No in-image header -- the
caption is typed out directly in the Word manuscript instead. Same
underlying data/plotting as danger_index_common.render_danger_index()
(used by the original-paper-numbered figure2.py); this is just a
relabeled, header-free copy for the current paper's own figure order.

To run (from the repo root): .venv/bin/python python/paper_figure7_danger_index.py
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
    out_filename="paper_figure7_danger_index.png",
    title=None,
)
