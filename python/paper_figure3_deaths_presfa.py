"""
Paper Figure 3: migrant deaths, Pre-SFA (2000-2007). No in-image header --
the caption is typed out directly in the Word manuscript instead. Same
underlying data/plotting as basemap_common.render_figure() (used by the
original-paper-numbered figure4.py); this is just a relabeled,
header-free copy for the current paper's own figure order.

To run (from the repo root): .venv/bin/python python/paper_figure3_deaths_presfa.py
"""

import os
import sys
from pathlib import Path

_VENV_DIR = Path(__file__).resolve().parent.parent / ".venv"
_VENV_PYTHON = _VENV_DIR / "bin" / "python"
if _VENV_PYTHON.exists() and Path(sys.prefix).resolve() != _VENV_DIR.resolve():
    os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

import basemap_common as bc

deaths = bc.load_deaths()
subset = deaths[deaths["is_pre_sfa"]]
print(f"Pre-SFA (2000-2007) deaths in this extract: {len(subset)}")

bc.render_figure(
    deaths_subset=subset,
    death_label="Location of Remains 2000-2007",
    title=None,
    out_filename="paper_figure3_deaths_presfa.png",
)
