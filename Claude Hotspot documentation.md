 # Hot-Spot Analysis Methodology

This document explains the statistical method behind `figure6.py`, `figure7.py`,
and `figure3_hotspot.py` (implemented in `hotspot_common.py`), which reproduce
Figures 6 and 7 from Bansak, Blanco, Coon & Dieringer (2025) plus the same
analysis applied to the full 2000–2019 dataset. Read this before trusting the
output — it documents every assumption, where I validated against the paper's
own precomputed results, and where I could not get an exact match and had to
make a defensible substitute choice.

## 1. What the paper says it did

Per the paper's Section 4.1 and your own `Hot Spot Analysis Methodology
Notes.docx`:

- Tool: ArcMap 10.8's **Optimized Hot Spot Analysis**, which computes the
  **Getis-Ord Gi\*** statistic.
- Gi\* is a *local* statistic: for each location, it compares the sum of
  values at that location and its neighbors against the sum you'd expect if
  values were randomly distributed across the whole study area. A large
  positive result means that location and its neighbors have significantly
  more deaths than chance would predict (a hot spot); large negative means
  significantly fewer (a cold spot).
- Significance is reported as a Z-score and p-value, classified at three
  confidence levels: 90%, 95%, 99%.
- The analysis was run separately on the pre-SFA (2000–2007) and post-SFA
  (2008–2019) death locations.

That's the extent of what's stated. The exact grid resolution, the exact
spatial-weights distance, and the multiple-testing correction ArcGIS's
"Optimized" tool chooses internally are **not** published anywhere accessible
to me — they're computed automatically inside the tool from the input data
using an undocumented heuristic. This matters, because it's the crux of what I
could and couldn't reproduce exactly (see Section 4).

## 2. The Getis-Ord Gi\* formula (what I actually implemented)

For a study area divided into $n$ zones, each with a value $x_i$ (here, the
count of deaths in grid cell $i$):

```
Gi*_i = [ Σⱼ wᵢⱼxⱼ − X̄ Σⱼ wᵢⱼ ] / [ S · √( (n·Σⱼwᵢⱼ² − (Σⱼwᵢⱼ)²) / (n−1) ) ]
```

where:
- $X̄$ = mean of $x$ across **all** $n$ cells (not just neighbors)
- $S$ = population standard deviation of $x$ across all $n$ cells
- $w_{ij}$ = 1 if cell $j$ is a "neighbor" of cell $i$ **or $j = i$ itself**
  (this self-inclusion is what makes it Gi\* rather than the older Gi
  statistic), 0 otherwise

This produces a Z-score per cell. I convert it to a two-tailed p-value using
the standard normal CDF (via `math.erf`, not `scipy`, to avoid an extra
dependency):

```
p = 2 × (1 − Φ(|Z|))
```

This formula is the standard, textbook version (Getis & Ord 1992; Mitchell,
*The ESRI Guide to GIS Analysis, Vol. 2*) and is not in dispute — this part of
the reproduction should be exactly correct, independent of any ArcGIS-specific
parameter choices.

## 3. The four things I had to decide myself

Everything above needs four inputs that the paper doesn't specify: how to turn
points into zones, how big those zones are, which zones count as "neighbors,"
and how to control for testing thousands of cells at once.

### 3.1 Aggregating points into a grid

Gi\* needs zones with values, not raw points. I built a square grid over the
study area and counted deaths per cell — **but only kept cells with at least
one death**, discarding all empty cells before running the statistic. This
matches how the original was clearly built: the pre/post `.dbf` files you
already had (`HotBeforejuly2023.dbf`, `HotAfterJuly2023.dbf`) contain only 629
and 780 records respectively — far fewer than a full-coverage grid over that
bounding box would produce (I calculate roughly 12,000 possible cells), so the
original analysis was also run only on populated cells.

### 3.2 Cell size

I derived this from the original `.dbf` files directly. Each record has
`Shape_Leng` (perimeter) and `Shape_Area` fields; both are consistent across
records and imply **square cells with side ≈0.0427°** for the pre-SFA
analysis and **≈0.0451°** for post-SFA (roughly 2.5 miles, at this latitude).

I tried to find a formula (e.g., cell size scaling with point density) that
would predict both values from first principles, so I could apply it
consistently to the "all data" case with no original to check against. **This
did not work** — a standard density formula predicts a *smaller* cell for the
post-SFA period (which has more points), but the original used a *larger*
one. This tells me ArcGIS's internal cell-size heuristic accounts for
something else (likely spatial spread/dispersion, not just point count) that
I don't have access to.

**What I did instead:** I use one fixed cell size, **0.044°** (the average of
the two recovered values), applied identically across all three scripts. This
is simpler, fully transparent, and keeps the three analyses on a consistent
footing — arguably a *more* comparable setup than the original's two
slightly-different per-period grids, though it means neither individual grid
is a perfect match to its corresponding original.

*To change it:* edit `CELL_SIZE` at the top of `hotspot_common.py`.

### 3.3 Spatial weights (which cells are "neighbors")

This is where I could **not** get a good match, and it's worth understanding
why, because it's the single biggest source of difference from the original
figures.

I first tried the standard, Esri-documented default for grid/lattice data:
**Queen contiguity** (a cell's neighbors are the up to 8 cells sharing an edge
or corner). I validated this against the original's `NNeighbors` field, which
records how many neighbors each cell actually had. The results didn't come
close:

| | My queen-contiguity result | Original (ArcGIS) |
|---|---|---|
| Average neighbors per cell | 3.6 | **135.9** |
| Range | 0–8 | 1–254 |

An average of 136 neighbors, in a dataset of only 629 total cells, means the
original's spatial weighting reached roughly a fifth of *all* cells in the
entire study area for every single cell — nowhere near simple adjacency. This
strongly implies ArcGIS's "Optimized" tool chose a **large fixed-distance
band** automatically (tens of miles), not contiguity.

I tried calibrating a fixed-distance band to reproduce that average-136
figure exactly. It technically matches the neighbor count, but the distance
band is then so large that it smooths out virtually all local variation —
after multiple-testing correction, almost nothing remains significant (6
cells, versus the original's 186). That's a worse result than queen
contiguity, not a better one, so I discarded it.

**What I did instead:** I used a **fixed distance band**, but chose its size
with a different, standard, Esri-documented rule of thumb: the smallest
radius such that each cell has **at least 8 neighbors on average**. This is a
commonly cited default in Esri's own spatial-statistics documentation. It's
principled and explainable, but it is a genuinely different choice than
whatever the original run actually used, so:

- The exact Z-scores, p-values, and which specific cells qualify as hot spots
  **will not match** the original figures cell-for-cell.
- The general *pattern* — where clusters form, and that the post-SFA period
  shows more/larger clusters shifted west relative to pre-SFA — should still
  emerge, because that pattern is a property of the underlying death
  locations, not of the exact weighting scheme.

*To change it:* edit `TARGET_AVG_NEIGHBORS` in `hotspot_common.py`, or swap
`_calibrate_distance_band` for a fixed-radius or queen-contiguity scheme if
you want to test alternatives.

### 3.4 Multiple-testing correction

Running Gi\* on ~600–1,000 cells simultaneously means some will look
"significant" purely by chance. ArcGIS's *Optimized* Hot Spot Analysis (as
opposed to the plain, non-optimized version) corrects for this automatically
using the **Benjamini-Hochberg False Discovery Rate (FDR)** procedure, applied
separately at the 90/95/99% levels. I implemented the same procedure:

1. Sort all p-values ascending.
2. For target FDR $q$ (0.10, 0.05, or 0.01), find the largest rank $k$ such
   that $p_{(k)} \le (k/n) \cdot q$.
3. Every cell with $p \le p_{(k)}$ is significant at that level.

One piece of supporting evidence this is the right general approach: the
paper's own text gives a worked example — "a hot spot is determined where the
critical value, Z-score, is 4.996... p-value... 0.000001" (Section 4.1). A
**raw**, uncorrected two-tailed 99%-confidence threshold only requires
Z ≈ 2.576. Needing a Z-score as extreme as 4.996 to hit "99% confidence" is
exactly the signature of FDR correction under many simultaneous tests — the
correction makes the *effective* threshold much stricter than the naive one.
This is consistent with what I implemented, even though my specific
weights/grid choices mean my numeric thresholds won't match theirs exactly.

## 4. Validation summary — what matched, what didn't

| Check | Result |
|---|---|
| Populated cell count (pre-SFA): mine vs. original | 633 vs. 629 — **close match**, validates cell size |
| Average neighbors per cell (pre-SFA): queen contiguity vs. original | 3.6 vs. 135.9 — **no match** |
| Average neighbors (calibrated fixed-distance) vs. original | matched by construction, but over-smooths results |
| FDR-implied threshold severity (Z≈4.996 in paper's example) | qualitatively consistent with FDR being applied |
| Overall spatial pattern (cluster locations) vs. published Figures 6/7 | qualitatively similar (see below), not cell-exact |

**Bottom line:** the Getis-Ord Gi\* math and the FDR correction are standard
and implemented correctly. The grid cell size is empirically well-matched.
The spatial-weights distance band is the one parameter I could not recover —
ArcGIS's automatic choice implies a far larger, denser weighting scheme than
any standard rule of thumb I tried reproduces sensible results with. I used
the "average 8 neighbors" default instead, which is defensible and
Esri-documented but not what actually produced the published figures.

## 5. What the figures show

The original published figures only fill cells classified at **95%** or
**99%** confidence (dark red / salmon) — even though the paper's *text*
describes a third "beige, <95% confidence" tier, I checked pixel colors
across the original images directly and found only two distinct fill colors
are actually used (confirmed against the legend box, which also only lists
two hot-spot entries).

**This reproduction deliberately goes further than the originals**: every
populated cell is shown, not just the significant ones. Cells at 95%/99%
keep the same two colors sampled from the original figures; every other
populated cell (a death was recorded there, but it wasn't part of a
statistically significant cluster — including 90%-only and cold-spot cells)
is filled with a pale tint of the same red family (`NOT_SIGNIFICANT` in
`hotspot_common.py`) rather than left blank. This makes the *full* extent of
recorded deaths visible on the map, with the statistically significant
clusters still clearly standing out by color intensity. It's an intentional
divergence from the original figures' styling, not an attempt to replicate
them exactly on this point.

## 6. Practical implication for interpreting these reproductions

Treat `figure6_reproduction.png` / `figure7_reproduction.png` as **an
independent, from-scratch statistical analysis that asks the same question
with a legitimate, standard method** — not as a pixel-for-pixel replication of
the original ArcGIS run. The counts, exact cell boundaries, and precise
cluster shapes will differ. What should hold up is the qualitative claim the
paper is built on: clustering exists, and it's spatially different
(smaller/more concentrated pre-SFA vs. larger/more dispersed post-SFA) between
the two periods. If you want to sanity-check that claim independent of my
implementation, the `HotBeforejuly2023.dbf` / `HotAfterJuly2023.dbf` files
already contain the paper's own original Gi\* output (just missing the
geometry needed to map them without GIS software) — comparing their `Gi_Bin`
counts to mine is exactly the check summarized in Section 4.
