"""
Paper Figure 6: hot-spot analysis, Post-SFA (2008-2019). No in-image
header -- the caption is typed out directly in the Word manuscript
instead. Same underlying data/plotting as hotspot_common.render_hotspot_figure()
(used by the original-paper-numbered figure7.py); this is just a
relabeled, header-free copy for the current paper's own figure order.

To run (from the repo root): .venv/bin/python python/paper_figure6_hotspot_postsfa.py
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

deaths = bc.load_deaths()
subset = deaths[deaths["is_post_sfa"]]
print(f"Post-SFA (2008-2019) deaths in this extract: {len(subset)}")

hc.render_hotspot_figure(
    deaths_subset=subset,
    death_label="Location of Remains 2008-2019",
    title=None,
    out_filename="paper_figure6_hotspot_postsfa.png",
)
