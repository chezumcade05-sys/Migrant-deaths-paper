# Where This Picks Up

A session-to-session handoff note — what's actually done, what was
explicitly deferred, and what's still an open question. For technical
detail on any of this, see the other docs (linked below); this file is
just the map of where things stand.

## What's built and working (both Python and R)

All eight figure scripts run cleanly end to end, in both languages:

| Figure | Script | Status |
|---|---|---|
| 2 (rebuilt danger index) | `figure2.py` / `figure2.R` | Done — new 6-factor, Z-score version |
| 3 (all deaths, 2000–2019) | `figure3.py` / `figure3.R` | Done |
| 4 (pre-SFA deaths, 2000–2007) | `figure4.py` / `figure4.R` | Done |
| 5 (post-SFA deaths, 2008–2019) | `figure5.py` / `figure5.R` | Done |
| 6 (hot-spot, pre-SFA) | `figure6.py` / `figure6.R` | Done |
| 7 (hot-spot, post-SFA) | `figure7.py` / `figure7.R` | Done |
| 8 (danger index + hot spots overlay) | `figure8.py` / `figure8.R` | Done — two stacked panels (pre-/post-SFA) rather than the original's single combined map |
| — (hot-spot, all years, no paper equivalent) | `figure9_hotspot.py` / `figure9_hotspot.R` | Done |

Every figure shares the same basemap (`basemap_common.py`/`.R`) and the
same water station layer (`Water Stations 2000-2019.csv`). Start with
**`README.md`** for the full pipeline; it's the map of everything else.

## Explicitly deferred, not forgotten

- **Distance-to-water-source as a danger index factor** — you asked to
  hold off on this until the danger index rebuild stage. That stage is
  done now (`figure2.py`/`.R`), and it's in there as factor #4.
- **A vegetation/"shade" factor** — added on a peer reviewer's suggestion
  that this has precedent in past literature. Implemented as NDVI
  (vegetation density), factor #6, following Boyce, Chambers & Launius
  (2019)'s "ruggedness index" — see `DANGER_INDEX_METHODOLOGY.md` §3 for
  the method and an important directional note (denser vegetation is
  scored as *more* dangerous in that paper, not as protective shade).
- **Figure 8** (original paper: hot spots overlaid on the danger index) —
  now built (`figure8.py`/`.R`), made possible by the danger index grid
  and hot-spot grid sharing the *exact same cell size and origin* on
  purpose. Shows both periods as two stacked panels rather than the
  original's single combined map, since cramming both periods'
  significant cells into one panel would need a second color/style
  dimension competing with the confidence-tier colors already in use.
- **Figure 1** (original paper: plain study-area overview map) — never
  attempted. Would mostly be a simpler version of the existing basemap
  layers already in `basemap_common.draw_basemap_layers()`, minus the
  death points.
- **Validating the danger index against actual outcomes** — noted as a
  limitation in `DANGER_INDEX_METHODOLOGY.md` §8: nothing has checked
  whether cells with a higher composite danger score actually had more
  recorded deaths. That's a natural next analytical step once the index
  itself is trusted.

## Open questions — not resolved, still worth a decision

- **The "paywalled data" question from your coauthor** — you mentioned a
  coworker got a "paywalled" error trying to open something you sent, and
  I asked follow-up questions (what exact error, how was it shared, which
  file) that were never answered — the conversation moved to the Humane
  Borders water station work instead. Worth circling back to if it's still
  an active problem.

## Quick orientation if you're picking this up fresh

The repo is organized into `python/`, `r/`, `data/`, `figures/`, and `docs/`
(everything below except README.md itself lives in `docs/`) — see README.md
§0 for the full layout.

1. **`README.md`** — pipeline overview, file table, how to run anything.
2. **`docs/COAUTHOR_CONTEXT.md`** — environment setup (Python `.venv` vs. R
   `install.packages("sf")`), plus the gotchas that cost real time
   (non-portable `.venv`, per-machine IDE interpreter settings, the FOUO
   marking on the fence data).
3. **`docs/Claude Hotspot documentation.md`** / **`docs/WATER_STATIONS_METHODOLOGY.md`**
   / **`docs/DANGER_INDEX_METHODOLOGY.md`** — the statistical/data deep-dives,
   one per analysis. Each is explicit about where the reproduction is
   known to diverge from the original paper's methodology and why.

As of 2026-08-10, figures dropped the on-image "(reproduction)" title tag
and red timestamp watermark that was useful earlier for spotting a stale
cached PNG in an editor tab — the project has moved past that
heavy-iteration stage, so the figures are now clean production output.
Each script still prints a `generated ...` line to the console on every
run.
