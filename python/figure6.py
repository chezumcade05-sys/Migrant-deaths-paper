"""
VESTIGIAL for the current paper's figure set: this is now Figure 5, not
Figure 6 -- see paper_figure5_hotspot_presfa.py (same underlying
hotspot_common.render_hotspot_figure(), just a different output
number/no in-image header). Still valid as a reproduction of the
*original* Bansak et al. (2025) paper's own Figure 6, if that's ever
needed again.

Reproduce Figure 6 from Bansak, Blanco, Coon & Dieringer (2025),
"Border Walls and Death on the US-Mexico Border":
    Figure 6. Hot-Spot Analysis, 2000-2007 (pre-Secure Fence Act)

Applies a from-scratch Getis-Ord Gi* hot-spot analysis (see
hotspot_common.py) to the same pre-SFA death points used in figure4.py,
plotted on the same base layer as figure3/4/5.py.

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
subset = deaths[deaths["is_pre_sfa"]]
print(f"Pre-SFA (2000-2007) deaths in this extract: {len(subset)}")

hc.render_hotspot_figure(
    deaths_subset=subset,
    death_label="Location of Remains 2000-2007",
    title="Figure 6: Hot-Spot Analysis, Pre-SFA (2000-2007)",
    out_filename="figure6_reproduction.png",
)
