"""
hotspot_common_annotated.py
============================
WHAT THIS FILE IS:
    A shared library — never run directly. Figures 6, 7, and 8 import this
    file to run the Gi* hot-spot analysis and draw hot-spot maps. It
    reimplements from scratch the same statistical method that ArcGIS's
    "Optimized Hot Spot Analysis" tool uses, so the results can be reproduced
    without ArcGIS.

THE BIG PICTURE — WHAT IS A HOT SPOT ANALYSIS?
    We have a cloud of death locations scattered across southern Arizona.
    A "hot spot" is a geographic area where deaths cluster more tightly than
    you'd expect if they were randomly spread around. The Gi* statistic
    measures, for each grid cell: given the number of deaths in THIS cell and
    its immediate neighbors, how unusual is that count compared to the overall
    average? If it's unusually high (statistically significant), that cell is
    a "hot spot."

THE THREE STEPS (in order):
    Step 1 — Build a raster: divide the study area into a grid of small cells
             and count how many deaths fall in each cell.
    Step 2 — Run Gi*: for each populated cell, compute a Z-score measuring
             how much the local death count exceeds the global average, then
             apply a multiple-testing correction.
    Step 3 — Draw: shade each hot-spot cell on the map in red/orange by
             confidence level (99% = dark red, 95% = orange).

HOW IT CONNECTS TO THE FIGURES:
    figure6.py (pre-SFA hot spots) does:
        import hotspot_common as hc
        hc.render_hotspot_figure(pre_sfa_deaths, ...)
    That single call runs all three steps and saves the PNG.
"""

import math
from collections import Counter

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

import basemap_common as bc


# =============================================================================
# SECTION 1: CONSTANTS
# =============================================================================

# Colors for the hot-spot confidence tiers, sampled from the original figures
HOT_99 = "#d62f29"       # 99% confidence — dark red
HOT_95 = "#ed7553"       # 95% confidence — orange/salmon
NOT_SIGNIFICANT = "#f9ddd2"  # cells with deaths but no significant cluster — pale pink
                              # (the original paper leaves these blank; this
                              # reproduction shows them so no deaths are hidden)

# The grid cell size used throughout all analyses.
# 0.044 degrees ≈ 2.7 miles per side at Arizona's latitude.
# This matches the cell size in the paper's own ArcGIS output files.
CELL_SIZE = 0.044

# Esri's documented default: when auto-calibrating the neighborhood radius,
# find the smallest distance such that each cell has at least 8 neighbors
# on average.
TARGET_AVG_NEIGHBORS = 8.0

# The three significance thresholds used for classification.
# After FDR correction, cells exceeding each threshold get Gi_Bin ±1, ±2, ±3.
FDR_LEVELS = (0.10, 0.05, 0.01)


# =============================================================================
# SECTION 2: STEP 1 — BUILD THE RASTER GRID
# Turn a list of death lat/lon points into a dictionary of grid cell counts.
#
# HOW IT WORKS:
#   The study area is divided into a grid of 0.044° squares. Each death record
#   is assigned to whichever cell its coordinates fall in. The result is a
#   dictionary like {(row, col): count} — only cells with at least one death
#   appear (empty cells are discarded, matching the paper's ArcGIS approach).
#
# EXAMPLE:
#   A death at longitude -110.95, latitude 31.34 would fall in the cell
#   whose column = floor((-110.95 - (-115.2)) / 0.044) = 96
#   and whose row  = floor((31.34 - 30.8) / 0.044) = 12
#   So counts[(12, 96)] gets incremented by 1.
# =============================================================================

def build_grid_counts(lons, lats, cell_size, origin_lon, origin_lat):
    """
    PARAMETERS:
        lons, lats   — arrays of longitude/latitude for each death
        cell_size    — grid cell size in degrees (0.044)
        origin_lon   — western edge of the study area (BBOX["min_lon"])
        origin_lat   — southern edge of the study area (BBOX["min_lat"])

    OUTPUT:
        A Counter (dictionary) mapping (row, col) -> death count
    """
    counts = Counter()
    for lon, lat in zip(lons, lats):
        col = math.floor((lon - origin_lon) / cell_size)
        row = math.floor((lat - origin_lat) / cell_size)
        counts[(row, col)] += 1
    return counts


# =============================================================================
# SECTION 3: STEP 2 — THE Gi* STATISTICAL ANALYSIS
# This is the core of the hot-spot method. Three sub-functions do the work:
#   _pairwise_distance_matrix  — compute distances between all pairs of cells
#   _calibrate_distance_band   — choose the neighborhood radius automatically
#   compute_gi_star            — run the full Gi* calculation
# =============================================================================

def _pairwise_distance_matrix(xs, ys):
    """
    WHAT IT DOES:
        Builds an N×N matrix of straight-line distances between all N
        populated cells. Entry [i, j] is the distance (in degrees) between
        cell i and cell j. This is used to determine which cells count as
        "neighbors" of each other.
    """
    dx = xs[:, None] - xs[None, :]
    dy = ys[:, None] - ys[None, :]
    return np.sqrt(dx**2 + dy**2)


def _calibrate_distance_band(D, target_avg_neighbors=TARGET_AVG_NEIGHBORS):
    """
    WHAT IT DOES:
        Finds the smallest neighborhood radius (in degrees) such that, on
        average, each cell has at least TARGET_AVG_NEIGHBORS (8) neighbors
        within that radius. Uses binary search — repeatedly tries the midpoint
        between a too-small and too-large radius until it converges.

    WHY THIS MATTERS:
        The neighborhood radius determines how "local" the hot-spot detection
        is. Too small → each cell has almost no neighbors, so the test has
        almost no power. Too large → you're averaging over so much area that
        local clusters disappear. 8 neighbors is Esri's documented default.

    OUTPUT:
        The calibrated radius in degrees (typically ~0.1°, about 7 miles)
    """
    n = D.shape[0]
    def avg_neighbors_at(radius):
        return (D <= radius).sum(axis=1).mean() - 1  # exclude self
    lo, hi = 1e-4, float(D.max())
    for _ in range(50):   # 50 iterations is more than enough to converge
        mid = (lo + hi) / 2
        if avg_neighbors_at(mid) < target_avg_neighbors:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _norm_sf_two_tailed(z):
    """
    WHAT IT DOES:
        Converts a Gi* Z-score to a two-tailed p-value using the standard
        normal distribution. A Z-score of 1.96 corresponds to p ≈ 0.05
        (5% significance), Z = 2.58 to p ≈ 0.01 (1% significance).
        Uses math.erf (a built-in Python math function) to avoid needing scipy.
    """
    cdf = 0.5 * (1 + math.erf(abs(z) / math.sqrt(2)))
    return 2 * (1 - cdf)


def _bh_fdr_threshold(pvalues, q):
    """
    WHAT IT DOES:
        Applies the Benjamini-Hochberg False Discovery Rate (FDR) correction.

    WHY THIS IS NEEDED:
        When you test hundreds of cells simultaneously, some will appear
        "significant" by chance alone (e.g., if you flip 600 fair coins,
        you'd expect ~30 to come up heads 5+ times in a row even though
        nothing is special about them). The BH correction adjusts the
        significance threshold to account for this, limiting the expected
        fraction of false positives to q.

    HOW IT WORKS:
        Sort all p-values from smallest to largest. The largest p-value that
        satisfies p[k] ≤ (k/m) × q becomes the corrected threshold.
        Any cell with p ≤ threshold is declared significant.

    OUTPUT:
        The adjusted p-value threshold below which a cell is declared
        significant at the q level (e.g., q=0.05 for 95% confidence)
    """
    m = len(pvalues)
    sp = np.sort(pvalues)
    ks = np.arange(1, m + 1)
    ok = sp <= (ks / m) * q
    return sp[ok].max() if ok.any() else 0.0


def compute_gi_star(cell_counts, cell_size, origin_lon, origin_lat):
    """
    THE MAIN ANALYSIS FUNCTION — runs the full Gi* hot-spot calculation.

    WHAT IT DOES, STEP BY STEP:
        1. Convert cell (row, col) keys into actual (longitude, latitude)
           coordinates for each populated cell
        2. Build the pairwise distance matrix
        3. Calibrate the neighborhood radius (binary search for ~8 neighbors)
        4. Build binary spatial weight matrix W: W[i,j] = 1 if cells i and j
           are within the radius of each other, 0 otherwise
        5. Compute the Gi* Z-score for every cell:
               Z[i] = (sum of deaths in i's neighborhood - expected sum)
                      / (standard deviation of expected sum)
           A large positive Z means this neighborhood has far more deaths than
           expected if deaths were spread randomly.
        6. Convert Z-scores to p-values
        7. Apply Benjamini-Hochberg FDR correction at 90%, 95%, 99% levels
        8. Classify each cell:
               +3 = hot spot at 99% confidence
               +2 = hot spot at 95% confidence
               +1 = hot spot at 90% confidence
                0 = not significant
               -1/-2/-3 = cold spot (fewer deaths than expected — rare here)

    OUTPUT:
        A dictionary of arrays with everything needed to draw the map:
        cell coordinates, Z-scores, p-values, Gi_Bin classifications, and
        diagnostic information (distance band, neighbor counts, etc.)
    """
    cells = list(cell_counts.keys())
    n = len(cells)
    # Convert (row, col) grid indices to lon/lat degrees at each cell's center
    xs = np.array([origin_lon + (c + 0.5) * cell_size for (r, c) in cells])
    ys = np.array([origin_lat + (r + 0.5) * cell_size for (r, c) in cells])
    vals = np.array([cell_counts[c] for c in cells], dtype=float)

    D = _pairwise_distance_matrix(xs, ys)
    radius = _calibrate_distance_band(D)

    # W is the spatial weights matrix: 1 if within radius, 0 if not
    # (Gi* includes each cell as its own neighbor, hence "self-inclusive")
    W = (D <= radius).astype(float)
    Wsum = W.sum(axis=1)   # number of neighbors each cell has (including itself)

    # Global mean and standard deviation of deaths per cell
    xbar = vals.mean()
    s = math.sqrt((vals**2).mean() - xbar**2)

    # The Gi* formula:
    #   numerator   = actual weighted sum of neighbors' deaths minus expected
    #   denominator = theoretical standard deviation under the null hypothesis
    sum_wx = W @ vals    # for each cell: sum of death counts in its neighborhood
    denom = s * np.sqrt(Wsum * (n - Wsum) / (n - 1))
    denom[denom == 0] = np.nan
    Z = (sum_wx - xbar * Wsum) / denom
    Z = np.nan_to_num(Z, nan=0.0)

    # Convert Z-scores to p-values and apply BH correction
    P = np.array([_norm_sf_two_tailed(z) for z in Z])
    thresholds = {q: _bh_fdr_threshold(P, q) for q in FDR_LEVELS}

    def classify(z, p):
        if z > 0:
            if p <= thresholds[0.01]:
                return 3    # hot spot, 99% confidence
            if p <= thresholds[0.05]:
                return 2    # hot spot, 95% confidence
            if p <= thresholds[0.10]:
                return 1    # hot spot, 90% confidence
        elif z < 0:
            if p <= thresholds[0.01]:
                return -3   # cold spot, 99% confidence
            if p <= thresholds[0.05]:
                return -2
            if p <= thresholds[0.10]:
                return -1
        return 0             # not significant

    gi_bin = np.array([classify(z, p) for z, p in zip(Z, P)])

    return {
        "cells": cells, "lon": xs, "lat": ys, "count": vals,
        "z": Z, "p": P, "gi_bin": gi_bin,
        "distance_band_deg": radius,
        "avg_neighbors": Wsum.mean() - 1,
        "n_cells": n,
        "fdr_thresholds": thresholds,
    }


# =============================================================================
# SECTION 4: STEP 3 — DRAW THE HOT-SPOT MAP
# Takes the Gi* results and renders a complete publication-ready figure,
# reusing the same basemap layers (state boundary, roads, desert, fence)
# as the death-location figures.
#
# WHAT GETS DRAWN (in order, bottom to top):
#   - Arizona boundary and roads (gray)
#   - Sonoran Desert and Tohono O'odham Reservation outlines (dashed)
#   - Border fence lines (blue/yellow)
#   - Hot-spot grid cells (colored rectangles: dark red, orange, pale pink)
#   - Water station triangles
#   - City labels, scale bar, north arrow, legend
# =============================================================================

def render_hotspot_figure(deaths_subset, death_label, title, out_filename):
    """
    PARAMETERS:
        deaths_subset — pre-SFA or post-SFA death records (already filtered)
        death_label   — used in printed output, e.g. "Pre-SFA (2000-2007)"
        title         — map title
        out_filename  — PNG filename saved to figures/
    """
    water = bc.load_water_stations()

    # Run the full analysis pipeline (Steps 1 and 2)
    result = compute_gi_star(
        build_grid_counts(deaths_subset["Longitude"], deaths_subset["Latitude"],
                           CELL_SIZE, bc.BBOX["min_lon"], bc.BBOX["min_lat"]),
        CELL_SIZE, bc.BBOX["min_lon"], bc.BBOX["min_lat"],
    )

    # Print diagnostics to the console for validation
    print(f"  grid cells: {result['n_cells']}, distance band: "
          f"{result['distance_band_deg']:.4f} deg (avg neighbors: {result['avg_neighbors']:.1f})")
    print(f"  Gi_Bin counts: {dict(sorted(Counter(result['gi_bin']).items()))}")

    # Set up figure with correct geographic aspect ratio
    lat_mid = (bc.BBOX["min_lat"] + bc.BBOX["max_lat"]) / 2
    geo_aspect = 1 / math.cos(math.radians(lat_mid))
    lon_span = bc.BBOX["max_lon"] - bc.BBOX["min_lon"]
    lat_span = bc.BBOX["max_lat"] - bc.BBOX["min_lat"]
    fig_w = 12
    fig_h = fig_w * (lat_span * geo_aspect) / lon_span
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # Draw basemap layers (reuses basemap_common functions)
    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "tl_2021_us_state" / "tl_2021_us_state.shp",
        record_filter=lambda r: r["STATEFP"] == "04",
        closed=True, color="0.7", linewidth=0.7, zorder=1,
    )
    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "tl_2021_04_prisecroads" / "tl_2021_04_prisecroads.shp",
        record_filter=lambda r: r["RTTYP"] in ("I", "U", "S"),
        color="0.6", linewidth=0.5, zorder=1,
    )
    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "deserts_sw" / "deserts_sw.shp",
        record_filter=lambda r: r["NAME"] in ("Colorado Sonoran Desert", "Arizona Sonoran Desert"),
        closed=True, transform=bc.utm11n_to_lonlat,
        color=bc.DESERT_BROWN, linestyle=(0, (6, 2)), linewidth=1.6, zorder=3,
    )
    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "tl_2021_us_aiannh" / "tl_2021_us_aiannh.shp",
        record_filter=lambda r: r["NAMELSAD"] == "Tohono O'odham Nation Reservation",
        closed=True, color=bc.RESERVATION_PURPLE, linestyle=(0, (6, 2)), linewidth=1.3, zorder=3,
    )

    fence_before, fence_after, have_fence = bc.load_fence_layers()
    if have_fence:
        for gdf in fence_after:
            gdf.plot(ax=ax, color=bc.FENCE_YELLOW, linewidth=2.4, zorder=4)
        for gdf in fence_before:
            gdf.plot(ax=ax, color=bc.FENCE_BLUE, linewidth=2.4, zorder=4)

    # --- DRAW THE HOT-SPOT GRID CELLS ---
    # Each populated cell is drawn as a colored square at its geographic position.
    # half = half the cell width, used to center the square on the cell's midpoint.
    half = CELL_SIZE / 2
    for lon, lat, gb in zip(result["lon"], result["lat"], result["gi_bin"]):
        if gb == 3:
            color = HOT_99          # dark red: 99% confidence hot spot
        elif gb == 2:
            color = HOT_95          # orange: 95% confidence hot spot
        else:
            color = NOT_SIGNIFICANT # pale pink: death recorded, not significant
        ax.add_patch(Rectangle((lon - half, lat - half), CELL_SIZE, CELL_SIZE,
                                facecolor=color, edgecolor="none", zorder=2, alpha=0.9))

    ax.scatter(water["longitude"], water["latitude"], s=45, marker="^",
               color=bc.WATER_STATION_COLOR, edgecolor="black", linewidth=0.4, zorder=5)

    for name, (lon, lat) in bc.CITIES.items():
        ax.annotate(name, (lon, lat), textcoords="offset points", xytext=(4, 4), fontsize=8, zorder=6)

    bc.draw_scale_bar(ax, lon0=-115.05, lat0=31.05, at_latitude=32.0)
    bc.draw_north_arrow(ax, lon=-114.9, lat=31.3)
    bc.draw_cell_size_note(ax, CELL_SIZE, lon=-115.05, lat=30.95, reference_lat=lat_mid)

    legend_handles = [
        Rectangle((0, 0), 1, 1, facecolor=HOT_99, edgecolor="none", label="Hot Spot - 99% Confidence"),
        Rectangle((0, 0), 1, 1, facecolor=HOT_95, edgecolor="none", label="Hot Spot - 95% Confidence"),
        Rectangle((0, 0), 1, 1, facecolor=NOT_SIGNIFICANT, edgecolor="none", label="Death Recorded - Not Significant"),
        Line2D([], [], marker="^", linestyle="", markerfacecolor=bc.WATER_STATION_COLOR,
               markeredgecolor="black", markeredgewidth=0.4, markersize=8,
               label=f"Water stations (~2019, n={len(water)}, ±~5mi)"),
    ]
    if have_fence:
        legend_handles.append(Line2D([], [], color=bc.FENCE_YELLOW, linewidth=2.4, label="Border built 2008 or later"))
        legend_handles.append(Line2D([], [], color=bc.FENCE_BLUE, linewidth=2.4, label="Border built 2007 or before"))
    legend_handles.append(Line2D([], [], color=bc.DESERT_BROWN, linestyle=(0, (6, 2)), linewidth=1.6, label="Arizona Sonoran Desert"))
    legend_handles.append(Line2D([], [], color=bc.RESERVATION_PURPLE, linestyle=(0, (6, 2)), linewidth=1.3, label="Tohono O'odham Nation Reservation"))
    legend = ax.legend(handles=legend_handles, loc="upper right", fontsize=8,
                        title="Legend", title_fontsize=11, frameon=True,
                        edgecolor="black", facecolor="white")
    legend.get_title().set_fontweight("bold")
    legend._legend_box.align = "left"

    ax.set_xlim(bc.BBOX["min_lon"], bc.BBOX["max_lon"])
    ax.set_ylim(bc.BBOX["min_lat"], bc.BBOX["max_lat"])
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("black")
        spine.set_linewidth(1.0)
    ax.set_title(title)
    ax.set_aspect(geo_aspect)

    fig.tight_layout()
    out_path = bc.FIGURES_DIR / out_filename
    fig.savefig(out_path, dpi=200)
    print(f"Saved plot to {out_path}")
    plt.show()
    return result
