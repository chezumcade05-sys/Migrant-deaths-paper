# Danger Index (Rebuilt Version): Methodology

Figure 2 in the original paper is a "danger index" — a composite score
meant to capture how hazardous a given patch of desert is to cross on
foot. This document describes a **rebuilt version** of that index
(`figure2.py` / `figure2.R`, backed by `danger_index_common.py` / `.R`):
different factors, a different scoring method, and a different spatial
resolution than the original. Read this before citing or interpreting the
result.

## 1. What changed from the original

| | Original paper (Section 4.1) | This version |
|---|---|---|
| Factors | 6: distance to major road, distance to major city, distance to tribal lands, distance to major river, distance to desert, slope | 6: **ambient summer temperature**, distance to major city, distance to major road, **distance to a water source**, slope, **vegetation density (NDVI)** |
| Scoring | Each factor bucketed into an ordinal category (1–5 or 1–6, see the paper's Tables 1–3), scores summed | Each factor standardized to a **Z-score** ((value − mean) / standard deviation) across the full grid, Z-scores summed |
| Spatial resolution | Not specified in the paper at cell-level detail | A grid matching the hot-spot analysis exactly: same cell size (`hotspot_common.CELL_SIZE` = 0.044°) and same origin, so the two are directly comparable |
| Coverage | Full study area | Full study area, masked to within Arizona's state boundary |

Tribal lands, major river, and desert distance were dropped (the new
factor list replaces them with temperature and water-source distance,
which more directly represent the physical stress of the crossing itself
— heat and access to water — rather than proximity to specific landscape
features). "Distance to major city" and "distance to major road" carry
over from the original; slope carries over unchanged. Vegetation density
(NDVI) was added later, on a peer reviewer's suggestion that "shade" has
precedent as a factor in this literature — see §3 for what that turned
out to mean and why.

**Direction convention:** for every one of the 6 factors, a *higher* raw
value means *more* dangerous — hotter, farther from a city/road/water
source, steeper, more densely vegetated. So no factor needs its sign
flipped before summing; all 6 Z-scores contribute in the same direction,
matching the original paper's principle of "the further/steeper/hotter,
the more dangerous."

## 2. Data sources

| Factor | Source | Notes |
|---|---|---|
| Ambient summer temperature | PRISM Climate Group, July maximum temperature, averaged across 2014–2023 | Downloaded as ten separate monthly GeoTIFFs (`prism_tmax_us_25m_YYYY07`) at PRISM's public data service, then averaged. This is a 10-year approximate normal, not an official 30-year PRISM climate normal (that product needed a different access path than the one used here) |
| Distance to major city | Straight-line (Euclidean, degree-space) distance to the nearest of Phoenix or Tucson | Uses only these two from `basemap_common.CITIES` — the other three entries (Nogales, Sasabe, Sonoyta) are small border towns used elsewhere as map labels, not "major cities" |
| Distance to major road | Straight-line distance to the nearest Interstate/US/State-numbered highway | Same road layer (`Shape Files/tl_2021_04_prisecroads`, filtered to `RTTYP` I/U/S) already used for the basemap in every other figure |
| Distance to a water source | Straight-line distance to the nearest Humane Borders water station | Uses `Water Stations 2000-2019.csv` — see `WATER_STATIONS_METHODOLOGY.md` for that dataset's own ~5 mile positional uncertainty, which carries through into this factor |
| Slope | Derived from USGS 3DEP elevation data | See §4 — this required a real fix, not just a data pull |
| Vegetation density (NDVI) | Derived from USGS NAIP 4-band aerial imagery | See §3 for the formula, the literature precedent, and a real data-quality fix |

## 3. Vegetation density (NDVI): the 6th factor

A peer reviewer's report suggested that "shade" has been used as a factor
in past literature on migrant border-crossing risk, without specifying an
exact source or method. The closest matching precedent found is Boyce,
Chambers & Launius (2019), "Bodily Inertia and the Weaponization of the
Sonoran Desert in US Boundary Enforcement" (*Journal of the Association
for Borderlands Studies*), whose "ruggedness index" for the same Sonoran
Desert study region sums four Z-scored factors — temperature,
**vegetation density**, slope, and jaggedness — via the Normalized
Difference Vegetation Index:

```
NDVI = (NIR − Red) / (NIR + Red)
```

**Important directional note:** that paper does *not* treat vegetation as
protective shade. Denser vegetation is scored as *more* dangerous — it
slows travel, disorients people trying to navigate, and increases energy
expenditure — not as a source of cooling relief from heat. This
reproduction follows that same direction (confirmed as the intended
interpretation before implementing it): a cell with denser vegetation
gets a *higher* NDVI Z-score, contributing toward *more* danger, summed
in the same direction as every other factor. A version treating shade as
protective (subtracting rather than adding the vegetation Z-score) would
need a different citation, since it would contradict the cited paper's
own framing.

**Data source:** Boyce et al. used Landsat imagery for NDVI. This
reproduction instead uses **USGS National Map's NAIP aerial imagery**
(4-band: Red, Green, Blue, Near-Infrared) via the `USGSNAIPPlus`
ImageServer — an unauthenticated REST service in the same family already
used for the elevation/slope pull below, at much finer native resolution
than Landsat (NAIP is ~1m; Landsat is 30m). The formula is identical to
the cited paper's; only the imagery source differs, substituted for
practical reasons (no authentication or heavy GIS stack required, fits
the same lightweight `/exportImage`-plus-Pillow pattern already
established in this codebase — no rasterio/GDAL needed). See
`fetch_ndvi_layer.py`.

**A real data-quality bug, found and fixed:** the raw NDVI pull initially
produced a handful of extreme values (exactly −1 or up to +0.97) at grid
cells straddling the true edge of NAIP's coverage — mostly along the
southern edge of the study area, near the border. Two distinct issues
were involved:

1. A thin band of near-zero "fringe" pixels right at the coverage
   boundary (observed: `red=1, nir=0`) computed to a spurious exact NDVI
   of −1 even though they clearly weren't real reflectance data. Fixed by
   treating any pixel with combined `red + nir < 10` (out of a possible
   510) as nodata, not just the exact `(0, 0)` case — real desert
   reflectance sits comfortably above this floor.
2. Grid cells that straddle the actual edge of NAIP's real-world coverage
   footprint average very few valid sub-pixels (as few as 1–16 out of the
   100 used per cell), producing statistically unstable, unrepresentative
   values. Fixed by requiring at least half (50/100) of a cell's
   sub-pixels to be valid NAIP data before trusting that cell's average;
   otherwise the whole cell is marked missing, the same "insufficient
   data → exclude" approach already used for slope (§4).

With both fixes applied, the NDVI distribution is realistic for this
region: mean ≈ 0.04 (sparse Sonoran Desert scrub), ranging roughly from
−0.13 (bare sand/pavement — the lowest values cluster in the Yuma Desert
sand dunes in the far southwest) up to ~0.34 (denser vegetation, e.g. near
irrigated cropland in the lower Colorado River valley and mountain "sky
island" ranges) — well within NDVI's theoretical −1 to +1 range and
consistent with known desert land cover.

## 4. Why slope needed a non-obvious fix

The first attempt asked the USGS 3DEP ImageServer for slope directly, already
resampled to the coarse (141×80) target grid. That produced nonsense: 99% of
cells showed slope over 45°, which would mean Arizona is almost entirely
cliff faces. It isn't — the actual problem is that the server's slope
function computes rise-over-run using the *native, fine* DEM pixel spacing,
but when the output is requested at a much coarser resolution, that fine
spacing no longer matches the real distance between the coarse output
pixels. The result divides real elevation changes by a run distance
hundreds of times too small, producing artificially extreme slopes.

**Fix:** request raw elevation instead, at a resolution 10× finer than the
target grid (1410×800 pixels, one 3DEP call), compute slope manually in
Python/R using the correct real-world pixel spacing (accounting for how
longitude degrees compress with latitude), and then average each 10×10
block of fine-resolution slope values down to one final grid cell. The
resulting distribution (mean 2.7°, max ~18° after averaging) is realistic
for Arizona's basin-and-range terrain.

**Known gap:** 252 of the 11,280 grid cells (~2%) have no slope value —
these are cells where the 3DEP elevation service returned no data (mostly
just outside the Arizona portion of the grid, e.g. over the Mexico side).
Combined with the ~1,122 cells missing NDVI data (§3), a total of 1,374
cells are excluded from the rendered map and from the Z-score calculation
(`np.nanstd`/`na.rm=TRUE` skip them; a NaN composite score for that cell
just doesn't get colored in). Most of the added NDVI gaps fall outside
Arizona (over Mexico), so the in-Arizona cell count used for the figure's
factor-summary table is unaffected: still 7,536 cells.

## 5. Grid alignment with the hot-spot analysis

The danger index grid uses the exact same `CELL_SIZE` (0.044°) and the
same origin (`BBOX["min_lon"], BBOX["min_lat"]`) as `hotspot_common.py`'s
Getis-Ord Gi\* grid. A cell at grid position (row, col) is centered at the
identical longitude/latitude in both analyses. This means the two are
directly overlayable — a natural next step (not built yet) would be
reproducing the original paper's Figure 8 (hot spots overlaid on the
danger index).

Unlike the hot-spot grid, which only includes cells with at least one
recorded death, the danger index grid covers **every** cell in the full
study-area bounding box (masked to within Arizona) — it's a continuous
environmental surface independent of where anyone died, matching how the
original Figure 2 works.

## 6. Combining into one score

For each of the 6 factors, compute a Z-score across all 11,280 grid cells:

```
Z = (value − mean(value across all cells)) / std(value across all cells)
```

then sum the 6 Z-scores per cell into one composite danger score. A cell
at 0 is exactly average risk across the study area; positive means
more dangerous than average, negative means less. This replaces the
original paper's approach of summing 5–6 hand-bucketed ordinal category
scores (each 1–5 or 1–6) — the underlying idea (equally-weighted sum of
standardized risk factors) is the same, but continuous Z-scores avoid the
information loss and somewhat arbitrary bucket boundaries of manual
categorization.

## 7. Rendering

Colored pale yellow (relatively less dangerous) to dark red (most
dangerous) via a sequential Yellow-Orange-Red gradient (ColorBrewer
`YlOrRd`) — **not** the original Figure 2's green-to-red scheme. Two
reasons for the departure: red-green is the most common form of color
blindness, and "green" reads as *safe*, which is the wrong message here —
even the "relatively least dangerous" parts of this study area are still
a hazardous desert crossing. Legend labels say "relatively least
dangerous" rather than "least dangerous" for the same reason.

Reuses the same basemap layers as every other figure in this project
(state boundary, major roads, Sonoran Desert boundary, Tohono O'odham
Reservation boundary, water stations, city labels, scale bar, north
arrow) for visual consistency across the whole project.

A summary table is rendered below the map giving the min/mean/max of each
of the 6 raw (pre-Z-score) factors across all in-Arizona grid cells —
temperature in °C, the three distance factors converted from degree-space
to an approximate miles figure (see §8's Euclidean-distance caveat, which
applies here too), slope in degrees, and NDVI as a unitless index. This is
meant to give a reader a quick sense of the actual physical range each
Z-score is standardizing over, since the map itself only shows the
standardized composite.

## 8. Known limitations

- **Distances are Euclidean in degree-space**, not true geodesic
  distance or road-network travel distance. This is consistent with how
  distances are handled elsewhere in this project (e.g. the scale bar), and
  doesn't affect the Z-score computation itself (which is scale-invariant),
  but it does mean the raw distance values aren't literal miles.
- **Temperature is a 10-year average, not an official 30-year normal.**
  Close enough for relative comparison across the study area, but not a
  precise climatological reference value.
- **Water-source distance inherits the ~5 mile positional uncertainty**
  documented in `WATER_STATIONS_METHODOLOGY.md` — individual station
  positions there are approximate, not surveyed.
- **Equal weighting is a modeling choice, not a derived result** — summing
  6 unweighted Z-scores assumes each factor matters equally to overall
  danger, mirroring the original paper's "equally weighing each factor"
  approach, but this hasn't been validated against actual outcomes (e.g.,
  whether cells with a higher composite score actually had more deaths).
- **NDVI direction is a citation-driven modeling choice, not a
  self-evident one.** Treating denser vegetation as *more* dangerous
  (§3) follows Boyce, Chambers & Launius (2019)'s framing specifically;
  it will read as counterintuitive to anyone expecting "shade" to mean
  protective cooling. If a future revision wants the protective-shade
  interpretation instead, that's a sign flip on `z_ndvi` in
  `compute_danger_index()` (both languages) plus a new citation — it is
  *not* supported by the source this factor was built from.
- **NDVI is a single-mosaic snapshot, not a fixed calendar date.** Unlike
  the temperature factor (an explicit 2014–2023 July average), the NAIP
  imagery mosaic blends aerial flights from different years across the
  study area depending on each state/region's own acquisition cycle.
  Vegetation density is relatively stable in Sonoran Desert scrub year to
  year compared to temperate vegetation, but this is a coarser vintage
  control than the other factors have.
- **Two languages agree almost exactly.** Python and R compute road
  distance with different underlying libraries (Shapely/STRtree vs.
  sf/GEOS). R's `st_distance()` defaults to spherical (s2) great-circle
  distance in meters for unprojected lon/lat geometry, which would have
  silently mixed units with the other three (degree-space) distance
  factors — this was caught and fixed by stripping the CRS before the
  call so GEOS treats the coordinates as plain planar numbers, matching
  Shapely's CRS-agnostic behavior in Python. With that fixed, the
  composite index range matches to two decimal places (-5.32 to 9.61 in
  both) — the tiny remainder is ordinary floating-point/algorithm
  variation across millions of calculations, not a units or logic bug.
