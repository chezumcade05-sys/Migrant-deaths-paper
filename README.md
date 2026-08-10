# Reproducing Figures 3–7

This folder reproduces Figures 3, 4, 5, 6, and 7 from Bansak, Blanco, Coon &
Dieringer (2025), *"Border Walls and Death on the US-Mexico Border,"* plus one
extra hot-spot analysis (all years combined) that has no direct equivalent in
the paper. Everything here is built from the paper's own underlying data —
nothing about *which* deaths are pre-/post-SFA, or where the fence/desert/
reservation boundaries are, was eyeballed from the published images. This
document is the map: what each script does, in what order, using what data,
and how to check that it did it correctly.

## 1. What's in this folder

**The paper's own source data** (as originally provided, unmodified):
| File/folder | What it is |
|---|---|
| `Original death data.csv` | Arizona OpenGIS Initiative for Deceased Migrants (PCMOE / Humane Borders) — the raw point data everything else is built from |
| `Original Fence data/01-ORIGINAL.gdb` | CBP tactical-infrastructure geodatabase (pedestrian fence + vehicle barriers, by install date). Its internal metadata marks it **FOUO** (For Official Use Only) — a DHS sensitivity marking, worth knowing about if this folder is shared further |
| `HotBeforejuly2023.dbf` / `HotAfterJuly2023.dbf` | The paper authors' **own precomputed ArcGIS Gi\* output** (Z-scores, p-values, `Gi_Bin` classification) for the pre-/post-SFA hot-spot analyses — no geometry attached, but this is the ground truth I validated my own hot-spot reimplementation against (see §4) |
| `Hot Spot Analysis Methodology Notes.docx` | The authors' own methodology notes — confirms ArcMap 10.8's *Optimized Hot Spot Analysis* tool was used |
| `Bansak_Blanco_Coon_Dieringer_..._CEP.docx` | The paper draft itself |

**`REFERENCES.md`** lists every external data source used to build these
figures — full URLs, access dates, and citations — in one place.

**Basemap geography** (public data, downloaded fresh — not originally in the
data folder; see `Shape Files/` and the top of `basemap_common.py` for exact
sources: Census TIGER/Line 2021 for counties/roads/state/tribal lands, USGS
2006 for the Sonoran Desert boundary):
| Folder | Contents |
|---|---|
| `Shape Files/tl_2021_us_state` | Arizona state boundary |
| `Shape Files/tl_2021_04_prisecroads` | Arizona interstate/US/state highways |
| `Shape Files/tl_2021_us_aiannh` | Tohono O'odham Nation Reservation boundary |
| `Shape Files/deserts_sw` | Sonoran Desert boundary (Faunt, 2006 — the exact survey the paper cites) |

**The reproduction code** (what this README is mainly about):
| File | Role |
|---|---|
| `basemap_common.py` | Shared library — not run directly. Loads/classifies the death data, loads fence layers, and draws the shared basemap (state boundary, roads, desert, reservation, legend, scale bar, north arrow) that every figure below uses. |
| `hotspot_common.py` | Shared library — not run directly. Implements the Getis-Ord Gi\* hot-spot statistic from scratch and renders hot-spot maps on the same basemap. |
| `figure3.py` | **Run this.** All migrant deaths, 2000–2019 (Figure 3). |
| `figure4.py` | **Run this.** Pre-SFA deaths, 2000–2007 (Figure 4). |
| `figure5.py` | **Run this.** Post-SFA deaths, 2008–2019 (Figure 5). |
| `figure6.py` | **Run this.** Hot-spot analysis, pre-SFA (Figure 6). |
| `figure7.py` | **Run this.** Hot-spot analysis, post-SFA (Figure 7). |
| `figure3_hotspot.py` | **Run this.** Hot-spot analysis, all years combined (no paper figure number — extends the same method to the full dataset). |
| `danger_index_common.py` | Shared library — not run directly. Rebuilds the paper's Figure 2 danger index with a different factor set (temperature, distance to city/road/water, slope, vegetation density) and Z-score-based scoring, on the same grid as the hot-spot analysis. |
| `figure2.py` | **Run this.** The rebuilt danger index (Figure 2). |
| `figure8.py` | **Run this.** Danger index overlaid with hot spots (Figure 8) — both pre- and post-SFA, as two stacked panels sharing one legend. Reuses the exact same colors as `figure2.py`/`figure6.py`/`figure7.py` (danger palette, `HOT_99`/`HOT_95`), just as unfilled outlines so the danger-index color shows through each cell. |
| `requirements.txt` | Exact package list needed to run any of the above |
| `Claude Hotspot documentation.md` | **The full statistical write-up** for the Gi\* method — read this before trusting `figure6.py`/`figure7.py`/`figure3_hotspot.py`'s output. This README gives the pipeline overview; that document gives the formulas, parameter choices, and validation detail. |
| `DANGER_INDEX_METHODOLOGY.md` | **The full write-up** for the rebuilt danger index — what changed from the original, data sources for each factor, a real bug that had to be fixed in the slope calculation, and known limitations. Read before citing `figure2.py`'s output. |
| `Water Stations 2000-2019.csv` | Humane Borders water station locations, shown on every figure as teal triangles. **Not** part of the paper's original data — extracted from Humane Borders' own public poster. See `WATER_STATIONS_METHODOLOGY.md` for the extraction method, a dropped/less-reliable earlier extraction, and this dataset's ~5 mile positional uncertainty before relying on it for anything beyond a visual reference. |
| `WATER_STATIONS_METHODOLOGY.md` | Source, extraction method, and quantified uncertainty for the water station coordinates above. |
| `Danger Index Environmental Layers.csv` | Per-grid-cell slope, July temperature, and NDVI (vegetation density) data backing the danger index, at the same resolution as the hot-spot grid. See `DANGER_INDEX_METHODOLOGY.md` for sources. |
| `fetch_ndvi_layer.py` | One-off/re-runnable data-acquisition script that (re)populates the `ndvi` column of the CSV above from USGS NAIP imagery. Not part of the normal figure-rendering pipeline. |
| `poisson_did_regression.py` | **Run this.** Not a figure — a Poisson difference-in-differences regression testing whether the danger index's relationship with recorded deaths per grid cell shifted after the SFA. Panel of every in-Arizona grid cell x {pre-SFA, post-SFA}, deaths as the outcome, `post`, `danger_index`, and their interaction as predictors, offset for the periods' unequal length (8 vs. 12 years), cluster-robust SEs by cell. Requires `pip install statsmodels` (in `requirements.txt`). Writes `poisson_did_regression_results.txt` and `poisson_did_panel.csv`. |

**R versions**: every script above also has an `.R` equivalent
(`basemap_common.R`, `hotspot_common.R`, `danger_index_common.R`,
`figure2.R`, `figure3.R` ... `figure3_hotspot.R`) that produces closely
matching results using R instead of Python — see §6.

## 2. One-time setup

You need a Python virtual environment (`.venv`) with the packages in
`requirements.txt` installed. This is **machine-specific** — if you're
setting up on a new computer (including sharing this project with a
coauthor), don't try to reuse someone else's `.venv` folder; build your own:

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Use a Python version between 3.9 and 3.12 — `geopandas`/`pyproj` (needed for
the fence-line overlay) don't yet have prebuilt installers for very new
Python versions (3.13+).

Every `figureN.py` script automatically re-launches itself under `.venv` if
it wasn't started with it already, so as long as `.venv` exists in this same
folder, you don't need to manually select an interpreter to get correct
results from the command line. (IDEs like PyCharm/VS Code still need to be
*pointed at* `.venv` for their own UI features — see below — but the scripts
self-correct regardless.)

**To run any figure:** open it in VS Code/PyCharm and hit Run, or from a
terminal in this folder:
```bash
./.venv/bin/python figure4.py
```
Each script prints its record count and saves a PNG named after itself
(e.g., `figure4_reproduction.png`) in this same folder.

## 3. The point-map figures (3, 4, 5): pipeline

All three share one pipeline, in `basemap_common.load_deaths()` and
`render_figure()`:

1. **Load** `Original death data.csv`.
2. **Classify each record** as pre-SFA or post-SFA using the exact rule
   described in the paper's Section 4.2: pre-SFA = discovered 2000–2007, OR
   discovered in 2008 with a postmortem interval of "> 6-8 months" (i.e., the
   death likely occurred in 2007, even though the remains were found in
   2008). Post-SFA = discovered 2008–2019, excluding blank-postmortem
   records and the reclassified 2008 cases above.
3. **Filter** to the subset that figure needs (all / pre / post).
4. **Draw the basemap**: Arizona state boundary, major roads, Sonoran Desert
   boundary, Tohono O'odham Reservation boundary, border fencing (colored by
   pre-2008 vs. 2008-or-later install date, read from the CBP geodatabase).
5. **Plot the death points and water stations** (teal triangles — not part
   of the original figures; see `WATER_STATIONS_METHODOLOGY.md`), add city
   labels, scale bar, north arrow, and a legend styled to match the
   original figures' colors (sampled directly from the embedded images in
   the paper's `.docx`).

**How to validate this part:** each script prints its record count on run.
These are checked against the paper's own Table 4 and will print a warning
if they don't match:
- Figure 3 (all): **n = 3,041**
- Figure 4 (pre-SFA): **n = 1,215**
- Figure 5 (post-SFA): **n = 1,826**

If your copy of `Original death data.csv` has been updated with newer
records since the paper's data pull, these totals will drift upward — that's
expected and the scripts will tell you.

## 4. The hot-spot figures (6, 7, and the all-years extra): pipeline

This is the more involved analysis. Full statistical detail, formulas, and
— importantly — an honest account of where this could and couldn't be
validated against the paper's own ArcGIS output, is in
**`Claude Hotspot documentation.md`**. Here is the pipeline at a glance:

1. **Start from the same classified death points** as §3 (pre-SFA / post-SFA
   / all, depending on the script).
2. **Aggregate into a grid**: lay a grid of ~0.044°-square cells (~2.7 miles
   per side) over the study area and count deaths per cell. Empty cells are
   discarded — only cells with at least one death are analyzed further (this
   matches how the paper's own `.dbf` output is structured: far fewer
   populated cells than a full grid would produce).
3. **Define spatial weights**: for each populated cell, determine which
   other cells count as its "neighbors" for the statistic. This uses a fixed
   distance band, sized so each cell has ~8 neighbors on average (a standard,
   documented default) — chosen because I could **not** reverse-engineer
   ArcGIS's actual internal parameter (see the write-up for the validation
   attempt and why).
4. **Compute the Getis-Ord Gi\* statistic** for every populated cell: a
   Z-score comparing that cell-plus-its-neighbors' death count against what
   you'd expect if deaths were randomly distributed across the whole study
   area, converted to a two-tailed p-value.
5. **Correct for multiple testing**: with 600–1,000+ cells tested
   simultaneously, some will look "significant" by chance alone. A
   Benjamini-Hochberg False Discovery Rate (FDR) correction is applied at the
   90/95/99% confidence levels (matching ArcGIS's *Optimized* Hot Spot
   Analysis tool, which does this by default).
6. **Classify** each cell into a `Gi_Bin`: +3/+2/+1 for hot spots
   (99%/95%/90% confidence), −3/−2/−1 for cold spots, 0 for not significant.
7. **Draw**: the 95% and 99% hot-spot tiers are filled with the same dark
   red / salmon sampled from the original figures. Every *other* populated
   cell (a death was recorded there, just not significant) is filled with a
   pale tint of the same color family, rather than left blank — this
   reproduction intentionally shows the full extent of recorded deaths, not
   only the statistically significant clusters the original figures display.
   Water stations (teal triangles) are drawn on top, same as the point-map
   figures — see `WATER_STATIONS_METHODOLOGY.md`.

**How to validate this part:** each script prints, on run:
- how many grid cells were analyzed,
- the calibrated distance band and resulting average neighbor count,
- the full `Gi_Bin` distribution (how many cells landed in each
  confidence tier).

Compare these printed counts against the paper's own precomputed output —
`HotBeforejuly2023.dbf` / `HotAfterJuly2023.dbf` (readable with any `.dbf`
reader, e.g. Python's `dbfread` package) — which contain the *exact* original
`Gi_Bin`/`GiZScore`/`GiPValue`/`NNeighbors` values ArcGIS produced. **These
will not match exactly** — see `Claude Hotspot documentation.md` §4 for
which parameters matched closely (grid cell size) and which fundamentally
couldn't be recovered (the neighbor/distance-band structure — the original's
average neighbor count is ~100–140 per cell, far larger than any standard
method reproduces without over-smoothing the result to near-nothing). This
reproduction is a legitimate, independent Gi\* analysis of the same data with
the same general method, not a pixel-exact replay of the original ArcGIS
run — the qualitative pattern (clusters shift and grow post-SFA) is what
should hold up, not exact cell-for-cell counts.

## 5. Quick reference: expected outputs

| Script | Output file | What to check |
|---|---|---|
| `figure3.py` | `figure3_reproduction.png` | n = 3,041 |
| `figure4.py` | `figure4_reproduction.png` | n = 1,215 |
| `figure5.py` | `figure5_reproduction.png` | n = 1,826 |
| `figure6.py` | `figure6_reproduction.png` | `Gi_Bin` distribution printed to console; compare pattern (not exact counts) to `HotBeforejuly2023.dbf` |
| `figure7.py` | `figure7_reproduction.png` | `Gi_Bin` distribution printed to console; compare pattern to `HotAfterJuly2023.dbf` |
| `figure3_hotspot.py` | `figure3_hotspot_reproduction.png` | No paper equivalent to compare against; sanity-check only |
| `figure8.py` | `figure8_reproduction.png` | Two panels; `Gi_Bin` distributions printed to console should match `figure6.py`/`figure7.py` exactly (604 / 814 grid cells) |

Every script also prints a `generated YYYY-MM-DD HH:MM:SS` line to the
console on each run — the figures themselves are now clean, production-
style output with no on-image timestamp or "(reproduction)" tag, now that
the pipeline has stabilized past the heavy-iteration stage where that
watermark was useful for telling a fresh render apart from a stale cached
one in an editor tab.

## 6. R versions

Every script above has an R port, kept functionally identical on purpose —
same classification rule, same grid/distance-band calibration, same Gi\*
formula, same FDR correction, same colors:

| Python | R equivalent |
|---|---|
| `basemap_common.py` | `basemap_common.R` |
| `hotspot_common.py` | `hotspot_common.R` |
| `danger_index_common.py` | `danger_index_common.R` |
| `figure3.py` ... `figure3_hotspot.py` | `figure3.R` ... `figure3_hotspot.R` |
| `figure8.py` | `figure8.R` |
| `poisson_did_regression.py` | `poisson_did_regression.R` |

**Setup:** two packages -- `sf` (handles the shapefiles and the fence
geodatabase, and, unlike the Python side, doesn't need a special virtual
environment to get a working GDAL install) for every figure script, plus
`sandwich`/`lmtest` (cluster-robust standard errors) for
`poisson_did_regression.R` only:
```r
install.packages("sf")
install.packages(c("sandwich", "lmtest"))
```

**To run:** `Rscript figure4.R` from a terminal in this folder, or open in
RStudio/PyCharm's R plugin and Source it. Each `.R` script locates its own
folder automatically (same idea as the Python `.venv` re-exec trick, just
via `commandArgs()`/RStudio's active-document path instead), so your
working directory doesn't matter. Output PNGs get an `_R` suffix
(`figure4_reproduction_R.png`) so they don't overwrite the Python versions.

**Validated for exact parity, not just "looks similar":** the point-map
scripts (`figure3.R`/`figure4.R`/`figure5.R`) produce the identical record
counts as their Python counterparts (3,041 / 1,215 / 1,826). The hot-spot
scripts (`figure6.R`/`figure7.R`/`figure3_hotspot.R`) produce the *exact
same* grid cell counts, calibrated distance bands, and full `Gi_Bin`
distributions as `figure6.py`/`figure7.py`/`figure3_hotspot.py` — e.g. both
`figure6.py` and `figure6.R` independently compute 604 grid cells, a
0.0984° distance band, and a `Gi_Bin` split of `{0: 573, 2: 1, 3: 30}`. The
same caveats about matching (or not matching) the original paper's ArcGIS
output in `Claude Hotspot documentation.md` apply equally to both language
versions, since the underlying method is identical.

The danger index (`figure2.py`/`figure2.R`) matches almost exactly between
languages — both currently report a composite index range of -5.32 to
9.61. See `DANGER_INDEX_METHODOLOGY.md` §8 for the tiny remaining
floating-point-level difference and a units bug in R's road-distance
calculation that was caught and fixed along the way.

One implementation difference worth knowing about, even though it doesn't
change the results: the R version reprojects the desert shapefile with
`sf::st_transform()`, which reads the file's actual coordinate system and
converts it properly. The Python version doesn't have easy access to a
projection library in this environment, so it manually re-implements the
one relevant UTM-to-latitude/longitude conversion by hand instead (see the
`utm11n_to_lonlat()` comment in `basemap_common.py`). Both land on the same
coordinates; the R route just uses a general-purpose tool where Python had
to special-case it.
