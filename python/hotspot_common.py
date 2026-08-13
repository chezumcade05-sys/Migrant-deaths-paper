"""
Getis-Ord Gi* hot-spot analysis, implemented from scratch (no ArcGIS, no
proprietary spatial stats library), for reproducing Figures 6 and 7 from
Bansak, Blanco, Coon & Dieringer (2025), plus the same analysis applied to
the complete 2000-2019 dataset (no direct paper equivalent).

See HOTSPOT_METHODOLOGY.md for the full statistical write-up: what's
computed, why these specific parameter choices, and where this
reproduction is known to diverge from the paper's original ArcGIS
"Optimized Hot Spot Analysis" output.

This module assumes the re-exec-into-.venv trick (see the top of
figure4.py) has already run in the entry-point script.
"""

import math
from collections import Counter

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

import basemap_common as bc

# Colors sampled directly from the original Figures 6/7 legend swatches.
HOT_99 = "#d62f29"
HOT_95 = "#ed7553"
# Not part of the original figures (which only show the two tiers above) --
# a paler continuation of the same red family, for cells with a recorded
# death that didn't reach 95%/99% significance.
NOT_SIGNIFICANT = "#f9ddd2"

# Shared grid cell size (degrees) used for all three analyses -- see the
# methodology write-up for how this was derived and why it's fixed rather
# than auto-computed per dataset.
CELL_SIZE = 0.044

# Esri's own documented rule of thumb for choosing a default fixed distance
# band: pick the smallest distance such that, on average, each feature has
# at least this many neighbors.
TARGET_AVG_NEIGHBORS = 8.0

FDR_LEVELS = (0.10, 0.05, 0.01)  # -> Gi_Bin +-1, +-2, +-3


# ---------------------------------------------------------------------------
# Step 1: aggregate points into a grid, keeping only populated cells (this
# matches the original ArcGIS output, whose feature count -- 629 pre-SFA,
# 780 post-SFA -- is far smaller than a full-coverage fishnet would produce,
# meaning empty cells were excluded before running Gi*).
# ---------------------------------------------------------------------------
def build_grid_counts(lons, lats, cell_size, origin_lon, origin_lat):
    counts = Counter()
    for lon, lat in zip(lons, lats):
        col = math.floor((lon - origin_lon) / cell_size)
        row = math.floor((lat - origin_lat) / cell_size)
        counts[(row, col)] += 1
    return counts


# ---------------------------------------------------------------------------
# Step 2: choose a fixed distance band (in degrees) via Esri's "average N
# neighbors" heuristic, then compute Getis-Ord Gi* for every populated cell.
# ---------------------------------------------------------------------------
def _pairwise_distance_matrix(xs, ys):
    dx = xs[:, None] - xs[None, :]
    dy = ys[:, None] - ys[None, :]
    return np.sqrt(dx**2 + dy**2)


def _calibrate_distance_band(D, target_avg_neighbors=TARGET_AVG_NEIGHBORS):
    n = D.shape[0]
    def avg_neighbors_at(radius):
        return (D <= radius).sum(axis=1).mean() - 1  # exclude self
    lo, hi = 1e-4, float(D.max())
    for _ in range(50):
        mid = (lo + hi) / 2
        if avg_neighbors_at(mid) < target_avg_neighbors:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _norm_sf_two_tailed(z):
    """Two-tailed p-value from a standard-normal z-score, via math.erf
    (avoids adding a scipy dependency for one function)."""
    cdf = 0.5 * (1 + math.erf(abs(z) / math.sqrt(2)))
    return 2 * (1 - cdf)


def _bh_fdr_threshold(pvalues, q):
    """Benjamini-Hochberg critical p-value for false discovery rate q."""
    m = len(pvalues)
    sp = np.sort(pvalues)
    ks = np.arange(1, m + 1)
    ok = sp <= (ks / m) * q
    return sp[ok].max() if ok.any() else 0.0


def compute_gi_star(cell_counts, cell_size, origin_lon, origin_lat):
    """cell_counts: {(row, col): count}. Returns a DataFrame-like dict of
    arrays (cells, lon, lat, count, z, p, gi_bin) plus the calibrated
    distance band, for inspection/debugging."""
    cells = list(cell_counts.keys())
    n = len(cells)
    xs = np.array([origin_lon + (c + 0.5) * cell_size for (r, c) in cells])
    ys = np.array([origin_lat + (r + 0.5) * cell_size for (r, c) in cells])
    vals = np.array([cell_counts[c] for c in cells], dtype=float)

    D = _pairwise_distance_matrix(xs, ys)
    radius = _calibrate_distance_band(D)
    W = (D <= radius).astype(float)  # binary weights, self-inclusive (Gi*)
    Wsum = W.sum(axis=1)

    xbar = vals.mean()
    s = math.sqrt((vals**2).mean() - xbar**2)
    sum_wx = W @ vals
    denom = s * np.sqrt(Wsum * (n - Wsum) / (n - 1))
    denom[denom == 0] = np.nan
    Z = (sum_wx - xbar * Wsum) / denom
    Z = np.nan_to_num(Z, nan=0.0)
    P = np.array([_norm_sf_two_tailed(z) for z in Z])

    thresholds = {q: _bh_fdr_threshold(P, q) for q in FDR_LEVELS}

    def classify(z, p):
        if z > 0:
            if p <= thresholds[0.01]:
                return 3
            if p <= thresholds[0.05]:
                return 2
            if p <= thresholds[0.10]:
                return 1
        elif z < 0:
            if p <= thresholds[0.01]:
                return -3
            if p <= thresholds[0.05]:
                return -2
            if p <= thresholds[0.10]:
                return -1
        return 0

    gi_bin = np.array([classify(z, p) for z, p in zip(Z, P)])

    return {
        "cells": cells, "lon": xs, "lat": ys, "count": vals,
        "z": Z, "p": P, "gi_bin": gi_bin,
        "distance_band_deg": radius, "avg_neighbors": Wsum.mean() - 1,
        "n_cells": n, "fdr_thresholds": thresholds,
    }


# ---------------------------------------------------------------------------
# Step 3: render, reusing the exact same basemap layers as figure3/4/5.py.
# ---------------------------------------------------------------------------
def render_hotspot_figure(deaths_subset, death_label, title, out_filename):
    water = bc.load_water_stations()
    result = compute_gi_star(
        build_grid_counts(deaths_subset["Longitude"], deaths_subset["Latitude"],
                           CELL_SIZE, bc.BBOX["min_lon"], bc.BBOX["min_lat"]),
        CELL_SIZE, bc.BBOX["min_lon"], bc.BBOX["min_lat"],
    )
    print(f"  grid cells: {result['n_cells']}, distance band: "
          f"{result['distance_band_deg']:.4f} deg (avg neighbors: {result['avg_neighbors']:.1f})")
    print(f"  Gi_Bin counts: {dict(sorted(Counter(result['gi_bin']).items()))}")

    lat_mid = (bc.BBOX["min_lat"] + bc.BBOX["max_lat"]) / 2
    geo_aspect = 1 / math.cos(math.radians(lat_mid))
    lon_span = bc.BBOX["max_lon"] - bc.BBOX["min_lon"]
    lat_span = bc.BBOX["max_lat"] - bc.BBOX["min_lat"]
    fig_w = 12
    fig_h = fig_w * (lat_span * geo_aspect) / lon_span
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

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

    # Hot-spot grid cells. The original figures only fill the 95%/99% tiers;
    # this reproduction additionally shows every other populated cell (a
    # death was recorded there, just not part of a statistically significant
    # cluster) in a pale tint of the same color family, so no data is hidden.
    half = CELL_SIZE / 2
    for lon, lat, gb in zip(result["lon"], result["lat"], result["gi_bin"]):
        if gb == 3:
            color = HOT_99
        elif gb == 2:
            color = HOT_95
        else:
            color = NOT_SIGNIFICANT
        ax.add_patch(Rectangle((lon - half, lat - half), CELL_SIZE, CELL_SIZE,
                                facecolor=color, edgecolor="none", zorder=2, alpha=0.9))

    # Water stations -- not part of the original figures; see
    # WATER_STATIONS_METHODOLOGY.md for source and positional uncertainty.
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
