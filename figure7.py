"""
Reproduce Figure 7 from Bansak, Blanco, Coon & Dieringer (2025),
"Border Walls and Death on the US-Mexico Border":
    Figure 7. Hot-Spot Analysis, 2008-2019 (post-Secure Fence Act)

Applies a from-scratch Getis-Ord Gi* hot-spot analysis (see
hotspot_common.py) to the same post-SFA death points used in figure5.py,
plotted on the same base layer as figure3/4/5.py.

See HOTSPOT_METHODOLOGY.md for the full statistical write-up.

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
import hotspot_common as hc

deaths = bc.load_deaths()
subset = deaths[deaths["is_post_sfa"]]
print(f"Post-SFA (2008-2019) deaths in this extract: {len(subset)}")

hc.render_hotspot_figure(
    deaths_subset=subset,
    death_label="Location of Remains 2008-2019",
    title="Figure 7: Hot-Spot Analysis, 2008-2019",
    out_filename="figure7_reproduction.png",
)
