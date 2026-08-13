"""
Reproduce Figure 4 from Bansak, Blanco, Coon & Dieringer (2025),
"Border Walls and Death on the US-Mexico Border":
    Figure 4. Migrant Deaths, 2000-2007 (pre-Secure Fence Act)

Shares its base layer (basemap, fence, styling) with figure3.py and
figure5.py via basemap_common.py -- see that file for data requirements
and layer details. This file only picks which death points to plot.

To run in VS Code:
    1. Open the repo root folder in VS Code and install the Microsoft
       "Python" extension if you don't already have it.
    2. A virtual environment with every dependency (including geopandas/
       pyogrio for the fence-line overlay) is set up at .venv/ in the repo
       root (a level up from this file, in python/). This script re-execs
       into it automatically below, so it works regardless of which
       interpreter VS Code has selected -- but you can also select it
       manually via Cmd+Shift+P -> "Python: Select Interpreter" -> the
       entry under ./.venv/bin/python.
    3. Open this file and click "Run Python File", or from the repo root
       in the integrated terminal: .venv/bin/python python/figure4.py

    If you ever need to rebuild the environment from scratch (e.g. on a
    different machine), note it was created with Python 3.9 specifically
    -- geopandas/pyproj don't yet have prebuilt wheels for very new Python
    versions (3.13+), so a much newer interpreter may fail to install them:
        python3.9 -m venv .venv
        .venv/bin/pip install pandas matplotlib pyshp utm geopandas pyogrio
"""

import os
import sys
from pathlib import Path

# VS Code's "Run Python File" button uses whatever interpreter is currently
# selected for the workspace, which can silently drift from the .venv/ we
# set up here. That interpreter may lack geopandas, so the fence overlay
# would fail even though .venv/ has it installed correctly. To make this
# robust regardless of what's selected in the UI, re-exec under the .venv/
# interpreter directly if we're not already running under it -- this must
# happen before importing anything that isn't in the standard library.
_VENV_DIR = Path(__file__).resolve().parent.parent / ".venv"
_VENV_PYTHON = _VENV_DIR / "bin" / "python"
# Compare sys.prefix (the active environment root), not sys.executable --
# this venv's python is itself a symlink through to the same base system
# Python binary, so resolving symlinks on sys.executable collapses both
# paths to that shared binary and makes them look identical even when the
# venv (with its own site-packages) isn't actually active.
if _VENV_PYTHON.exists() and Path(sys.prefix).resolve() != _VENV_DIR.resolve():
    os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

import basemap_common as bc

deaths = bc.load_deaths()
subset = deaths[deaths["is_pre_sfa"]]
print(f"Pre-SFA (2000-2007) deaths in this extract: {len(subset)}")
if len(subset) != 1215:
    print("NOTE: this does not match the paper's reported 1,215 -- the CSV "
          "may have been updated with additional records since the paper's "
          "data pull. Check the count above against Table 4.")

bc.render_figure(
    deaths_subset=subset,
    death_label="Location of Remains 2000-2007",
    title="Figure 4: Migrant Deaths, 2000-2007",
    out_filename="figure4_reproduction.png",
)
