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
- All of the above styled to match the originals' actual colors/legend
  (sampled directly from the embedded images in the paper's `.docx`), not
  guessed.

**Not done / not attempted yet:**
- Figure 1 (study-area overview map) and Figure 2 (danger index map) —
  no scripts exist for these yet.
- Figure 8 (danger index overlaid with hot spots) — same; this also depends
  on Figure 2's danger-index calculation, which hasn't been built.
- Exact replication of the paper's original ArcGIS hot-spot parameters. This
  was investigated in real depth (see `Claude Hotspot documentation.md` §3–4)
  and deliberately **not** forced to a fake match — the grid cell size
  matches well, but the spatial-weights distance band does not, and that's
  documented rather than hidden. Worth reading before either of you cites
  specific hot-spot cell counts anywhere.

If either of you starts on Figure 1/2/8 or anything else, update this
section so the other person isn't duplicating work.

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

## 5. No version control yet — read this before editing concurrently

This folder is **not currently a git repository.** That matters a lot for
"working on it at the same time": right now, if you both have a copy (email
attachment, shared drive, etc.) and edit the same file independently, there
is no merge — whoever saves/sends last silently overwrites the other
person's changes, with no warning and no way to recover the lost version.

Two ways to handle this, pick one before you both start editing:

1. **Set up git** (recommended if there's any real back-and-forth planned).
   A private GitHub/GitLab repo, or even just a shared git remote, gives you
   real merging, history, and the ability to see exactly what changed and
   who changed it. This is a quick one-time setup — ask if you want help
   with it.
2. **Informal file-ownership split**, if git feels like overkill for the
   remaining work: agree explicitly on who's touching which files before
   starting a session, and don't both have the same script open for editing
   at the same time. Fragile for anything beyond quick, well-separated
   changes, but workable for small edits.

Either way, **do not sync the `.venv` folder or R package library** through
whatever you use to share files (see §3) — exclude it explicitly if you're
using a shared drive that syncs everything by default.
