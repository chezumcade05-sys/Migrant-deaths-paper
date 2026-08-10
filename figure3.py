"""
Reproduce Figure 3 from Bansak, Blanco, Coon & Dieringer (2025),
"Border Walls and Death on the US-Mexico Border":
    Figure 3. Migrant Deaths, 2000-2019 (complete data set)

Shares its base layer (basemap, fence, styling) with figure4.py and
figure5.py via basemap_common.py -- see that file for data requirements
and layer details. This file only picks which death points to plot.

To run in VS Code: see the instructions at the top of figure4.py -- same
.venv/ setup and re-exec trick apply here.
"""

import os
import sys
from pathlib import Path

_VENV_DIR = Path(__file__).resolve().parent / ".venv"
_VENV_PYTHON = _VENV_DIR / "bin" / "python"
if _VENV_PYTHON.exists() and Path(sys.prefix).resolve() != _VENV_DIR.resolve():
    os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

import basemap_common as bc

deaths = bc.load_deaths()
subset = deaths[deaths["is_pre_sfa"] | deaths["is_post_sfa"]]
print(f"All deaths, 2000-2019, in this extract: {len(subset)}")
if len(subset) != 3041:
    print("NOTE: this does not match the paper's reported 3,041 -- the CSV "
          "may have been updated with additional records since the paper's "
          "data pull. Check the count above against Table 4.")

bc.render_figure(
    deaths_subset=subset,
    death_label="Location of Remains 2000-2019",
    title="Figure 3: Migrant Deaths, 2000-2019",
    out_filename="figure3_reproduction.png",
)
