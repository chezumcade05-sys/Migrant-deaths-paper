# Project Context — Figure Reproduction Codebase

This is a fast-orientation document for picking up this project. It tells you
what exists, what's still open, and the specific things that cost real time
to figure out the first time around, so you don't have to rediscover them.
For the technical detail this file intentionally doesn't repeat, see:

- **`README.md`** — the full pipeline: what each script does, in what order,
  using what data, and how to validate the output.
- **`Claude Hotspot documentation.md`** — the statistical write-up for the
  hot-spot analysis: the Gi\* formula, every parameter choice, and an honest
  account of where this reproduction could and couldn't be validated against
  the paper's own original ArcGIS output.

Read this file first, then go to whichever of those two you actually need.

## 1. What this project is

A from-scratch reproduction of Figures 3–7 from Bansak, Blanco, Coon &
Dieringer, *"Border Walls and Death on the US-Mexico Border,"* built directly
from the paper's own source data (not eyeballed from the published images).
Two complete, independent implementations exist side by side — one in
Python, one in R — kept deliberately in sync so either can be used/checked
against the other.

## 2. Current status

**Done and validated:**
- Figure 3 (all deaths, 2000–2019), Figure 4 (pre-SFA), Figure 5 (post-SFA) —
  point maps. Record counts match the paper's Table 4 exactly (3,041 / 1,215
  / 1,826) in both languages.
- Figure 6 (pre-SFA hot-spot analysis), Figure 7 (post-SFA), plus one extra
  hot-spot analysis on the full 2000–2019 dataset with no direct paper
  figure number. Both language versions produce numerically identical
  results to each other (same grid cell counts, same `Gi_Bin` distributions).
- Figure 2, a rebuilt danger index (6 Z-scored factors — temperature,
  distance to city/road/water, slope, vegetation density/NDVI — replacing
  the original's ordinal-category scoring), and Figure 8, that danger index
  overlaid with the hot spots from both periods. See
  `DANGER_INDEX_METHODOLOGY.md` for the full write-up.
- All of the above styled to match the originals' actual colors/legend
  (sampled directly from the embedded images in the paper's `.docx`), not
  guessed.

**Not done / not attempted yet:**
- Figure 1 (plain study-area overview map, no death/danger data) — never
  attempted; would mostly reuse the basemap layers already built for every
  other figure.
- Exact replication of the paper's original ArcGIS hot-spot parameters. This
  was investigated in real depth (see `Claude Hotspot documentation.md` §3–4)
  and deliberately **not** forced to a fake match — the grid cell size
  matches well, but the spatial-weights distance band does not, and that's
  documented rather than hidden. Worth reading before either of you cites
  specific hot-spot cell counts anywhere.

If either of you starts on Figure 1 or anything else, update this section so
the other person isn't duplicating work.

## 3. Getting set up

Two independent toolchains, pick whichever you're more comfortable with (or
use both — that's the point of having two implementations):

**Python:** needs a local virtual environment — do **not** try to reuse
anyone else's `.venv` folder; it's tied to the exact machine it was built on
and won't work on a different one (this ate real time before it was
understood — see README.md §2 for the full explanation).
```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```
Use Python 3.9–3.12 — `geopandas`/`pyproj` don't yet have prebuilt installers
for 3.13+.

**R:** just one package, no per-project environment needed:
```r
install.packages("sf")
```

Either way: **don't share the actual `.venv` folder** (or any built R
package library) between machines — rebuild it locally from
`requirements.txt` / `install.packages("sf")` instead. See README.md §2/§6
for exact run commands once set up.

## 4. Things that cost real debugging time — know these going in

- **The fence geodatabase (`Original Fence data/01-ORIGINAL.gdb`) is marked
  FOUO** (For Official Use Only) in its own internal metadata — a DHS
  sensitivity marking. Worth keeping in mind before this folder goes
  anywhere beyond the two of you.
- **PyCharm/VS Code interpreter settings are per-machine.** If you open this
  project and it can't find a Python interpreter, that's expected on a new
  machine — point it at your own freshly-built `.venv`, not a path that
  references someone else's folder structure.
- **Every generated PNG has a small red timestamp** in the bottom-right
  corner. Useful for confirming your editor is showing you a freshly
  regenerated image and not a stale cached tab.
- The hot-spot scripts print diagnostic info (grid cell count, distance
  band, `Gi_Bin` distribution) every time they run — that's intentional and
  is the fastest way to sanity-check a run without opening the image.

## 5. Version control — read this before editing concurrently

This is now a git repository, pushed to GitHub:
https://github.com/chezumcade05-sys/Migrant-deaths-paper (public). Clone it
rather than working from an emailed/shared-drive copy — that gives you real
merging, history, and the ability to see exactly what changed and who
changed it, instead of silently overwriting each other's edits.

A few things worth knowing about what's (deliberately) *not* in the repo,
via `.gitignore`:
- **`.venv/`** and any R package library — not portable between machines,
  rebuild locally (see §3).
- **The fence geodatabase's data is included**, despite its FOUO marking —
  a deliberate call already made once; worth being aware of before you fork
  or mirror this repo elsewhere.
- The unpublished paper draft, reviewer-facing notes, the authors' own
  precomputed ArcGIS validation output, and a folder of raw research
  spreadsheets that were never part of this reproduction's own pipeline —
  none of that belongs in a public repo alongside code.

If you add new data files, check whether they should be `.gitignore`d
before committing — same questions as above (portable? sensitive? actually
part of the pipeline?).
