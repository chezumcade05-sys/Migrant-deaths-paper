"""
VESTIGIAL for the current paper's figure set: not one of the current 8
figures. Kept for reference -- still a valid supplementary analysis if
ever needed again.

Hot-spot analysis of the complete 2000-2019 migrant death dataset (the same
points used in figure3.py). There is no directly corresponding numbered
figure in Bansak, Blanco, Coon & Dieringer (2025) -- the paper only runs
this analysis split by pre-/post-SFA period (Figures 6 and 7, reproduced in
figure6.py / figure7.py) -- but the same Getis-Ord Gi* method (see
hotspot_common.py) is applied here to the full dataset for comparison.

See HOTSPOT_METHODOLOGY.md for the full statistical write-up.

To run in VS Code: see the instructions at the top of figure4.py -- same
.venv/ setup and re-exec trick apply here.
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
subset = deaths[deaths["is_pre_sfa"] | deaths["is_post_sfa"]]
print(f"All deaths, 2000-2019, in this extract: {len(subset)}")

hc.render_hotspot_figure(
    deaths_subset=subset,
    death_label="Location of Remains 2000-2019",
    title="Figure 9: Hot-Spot Analysis, All Years Combined (2000-2019, no paper equivalent)",
    out_filename="figure9_hotspot_allyears.png",
)
