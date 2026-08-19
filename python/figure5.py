"""
VESTIGIAL for the current paper's figure set: this is now Figure 4, not
Figure 5 -- see paper_figure4_deaths_postsfa.py (same underlying
basemap_common.render_figure(), just a different output number/no
in-image header). Still valid as a reproduction of the *original*
Bansak et al. (2025) paper's own Figure 5, if that's ever needed again.

Reproduce Figure 5 from Bansak, Blanco, Coon & Dieringer (2025),
"Border Walls and Death on the US-Mexico Border":
    Figure 5. Migrant Deaths, 2008-2019 (post-Secure Fence Act)

Shares its base layer (basemap, fence, styling) with figure3.py and
figure4.py via basemap_common.py -- see that file for data requirements
and layer details. This file only picks which death points to plot.

Note: the original figure's legend reads "Location of Remains 2008-2020",
but the paper's own Table 4 defines the post-SFA window as 2008-2019 (12
years, excluding blank-postmortem records) -- this script matches Table 4
for consistency with figure3.py/figure4.py, so all three carry the same
date-range convention.

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

deaths = bc.load_deaths()
subset = deaths[deaths["is_post_sfa"]]
print(f"Post-SFA (2008-2019) deaths in this extract: {len(subset)}")
if len(subset) != 1826:
    print("NOTE: this does not match the paper's reported 1,826 -- the CSV "
          "may have been updated with additional records since the paper's "
          "data pull. Check the count above against Table 4.")

bc.render_figure(
    deaths_subset=subset,
    death_label="Location of Remains 2008-2019",
    title="Figure 5: Migrant Deaths, Post-SFA (2008-2019)",
    out_filename="figure5_reproduction.png",
)
