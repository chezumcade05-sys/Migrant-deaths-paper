"""
danger_index_common_annotated.py
==================================
WHAT THIS FILE IS:
    A shared library — never run directly. figure2.py and figure8.py import
    this file to compute and draw the danger index. It rebuilds the paper's
    Figure 2 danger index using a 6-factor scoring system.

WHAT IS THE DANGER INDEX?
    The danger index is a single score assigned to every grid cell in southern
    Arizona that captures how hazardous that terrain is for a migrant crossing
    on foot. A high score means the area combines multiple risk factors —
    extreme heat, far from any road or city, steep terrain, etc. The index
    is used in the paper's regression analysis as the key explanatory variable
    (D_i) measuring whether the Secure Fence Act pushed migrants into more
    dangerous terrain.

THE 6 FACTORS (each turned into a Z-score, then summed):
    1. July temperature (°C)       — hotter = more dangerous
    2. Distance to nearest city    — farther from Phoenix/Tucson = more dangerous
    3. Distance to nearest road    — farther from I-10/US-80/etc. = more dangerous
    4. Distance to nearest water   — farther from Humane Borders water stations = more dangerous
    5. Slope (degrees)             — steeper = more dangerous
    6. Vegetation density (NDVI)   — denser vegetation slows travel = more dangerous
                                     (follows Boyce et al. 2019's precedent;
                                     dense desert shrub is NOT treated as protective shade)

HOW Z-SCORING WORKS:
    Each factor is converted to a Z-score: (value - mean) / standard deviation.
    This puts all 6 factors on the same scale regardless of their original units
    (°C vs miles vs degrees of slope), so they contribute equally to the total.
    A Z-score of 0 means average; +2 means two standard deviations above average
    (more dangerous than 97.5% of cells); -1 means one SD below average.
    The composite index is the sum of the 6 Z-scores.

DIFFERENCE FROM THE ORIGINAL PAPER'S DANGER INDEX:
    The paper buckets each factor into 1–5 ordinal categories, then sums.
    This version Z-scores each factor instead — a more statistically principled
    approach that avoids arbitrary category boundaries. The spatial pattern
    of high/low danger is similar; the scale is different.

THE GRID:
    The danger index uses the EXACT SAME grid (0.044° cells, same origin) as
    the hot-spot analysis, so each cell has both a death count AND a danger
    index value. This alignment is what makes the regression analysis possible.
    But unlike the hot-spot grid (which only has cells where deaths occurred),
    the danger index covers EVERY cell in the study area — it's a continuous
    surface, not just where deaths happened.
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.colors import LinearSegmentedColormap

import basemap_common as bc
import hotspot_common as hc


# =============================================================================
# SECTION 1: SETUP
# =============================================================================

# Path to the pre-computed environmental data (slope, July temperature, NDVI).
# This CSV was built by fetch_ndvi_layer.py (NDVI) and separate slope/temperature
# downloads; it covers every grid cell in the study area.
ENV_CSV = bc.DATA_DIR / "Danger Index Environmental Layers.csv"

# Only Phoenix and Tucson count as "major cities" for factor 2 — the small
# border towns (Nogales, Sasabe) used for map labels are too small to serve
# as meaningful supply/rescue references for migrants.
MAJOR_CITIES = {"Phoenix": bc.CITIES["Phoenix"], "Tucson": bc.CITIES["Tucson"]}

# Color ramp for the danger index map: pale yellow (low danger) → dark red (high danger).
# Deliberately not the paper's green-to-red scheme: green implies "safe," which
# is misleading since even the least dangerous cells are still desert crossings.
# YlOrRd is also colorblind-safe (red-green colorblindness is the most common form).
DANGER_CMAP = plt.get_cmap("YlOrRd")


# =============================================================================
# SECTION 2: DISTANCE CALCULATION FUNCTIONS
# For factors 2, 3, and 4 we need to know how far each grid cell is from
# the nearest city, road, or water station. These three functions do that.
# All distances are in degrees (not miles) for speed — they're converted to
# miles only for the summary table at the bottom of the figure.
# =============================================================================

def _min_dist_to_points(lons, lats, ref_lonlat):
    """
    WHAT IT DOES:
        For each grid cell (defined by its lon/lat), finds the straight-line
        distance in degrees to the nearest reference point (e.g. nearest city).
        Returns an array with one distance value per grid cell.

    USED FOR: Factor 2 (city distance) and called similarly for water stations.
    """
    ref = np.array(list(ref_lonlat.values()))
    d = np.full(len(lons), np.inf)
    for rlon, rlat in ref:
        d = np.minimum(d, np.hypot(lons - rlon, lats - rlat))
    return d


def _min_dist_to_roads(lons, lats):
    """
    WHAT IT DOES:
        For each grid cell, finds the perpendicular distance to the nearest
        road segment (not just the nearest road endpoint). Uses a spatial
        index (STRtree) to do this efficiently rather than checking every
        cell against every road segment one by one.

    USED FOR: Factor 3 (road distance).

    WHY MORE COMPLEX THAN CITY DISTANCE:
        Cities are points — distance to a point is simple Pythagorean.
        Roads are lines — distance to a line requires computing the
        perpendicular drop from the cell to the nearest point ON the line,
        not just to its endpoints. Shapely's geometry library handles this.
    """
    import shapefile  # pyshp
    from shapely.geometry import Point, LineString
    from shapely.ops import unary_union
    from shapely.strtree import STRtree

    # Read all major roads in Arizona from the Census shapefile
    sf = shapefile.Reader(str(bc.SHAPE_DIR / "tl_2021_04_prisecroads" / "tl_2021_04_prisecroads.shp"))
    field_names = [f[0] for f in sf.fields[1:]]
    lines = []
    for sr in sf.iterShapeRecords():
        rec = dict(zip(field_names, sr.record))
        if rec["RTTYP"] not in ("I", "U", "S"):  # Interstate, US, State highways only
            continue
        pts = sr.shape.points
        parts = list(sr.shape.parts) + [len(pts)]
        for i in range(len(parts) - 1):
            seg = pts[parts[i]:parts[i + 1]]
            if len(seg) >= 2:
                lines.append(LineString(seg))

    # Build a spatial index for fast nearest-line lookup
    tree = STRtree(lines)
    d = np.empty(len(lons))
    for i, (lon, lat) in enumerate(zip(lons, lats)):
        p = Point(lon, lat)
        nearest_idx = tree.nearest(p)
        d[i] = p.distance(lines[nearest_idx])   # perpendicular distance to nearest road
    return d


def _min_dist_to_water(lons, lats):
    """
    WHAT IT DOES:
        For each grid cell, finds the straight-line distance to the nearest
        Humane Borders water station. Same approach as city distance — simple
        minimum distance to a set of points.

    USED FOR: Factor 4 (water distance).
    """
    water = bc.load_water_stations()
    d = np.full(len(lons), np.inf)
    for wlon, wlat in zip(water["longitude"], water["latitude"]):
        d = np.minimum(d, np.hypot(lons - wlon, lats - wlat))
    return d


# =============================================================================
# SECTION 3: MAIN COMPUTATION — compute_danger_index()
# This is the core function. It assembles all 6 factors, Z-scores each one,
# and returns the composite index for every grid cell.
#
# STEP BY STEP:
#   1. Read the pre-computed slope, temperature, and NDVI from the CSV
#   2. Compute distances to cities, roads, and water stations for each cell
#   3. Z-score all 6 raw factor arrays
#   4. Sum the 6 Z-scores → composite danger index
#   5. Return everything in a dictionary of arrays
# =============================================================================

def compute_danger_index():
    """
    OUTPUT:
        A dictionary containing one array per grid cell for each factor,
        each factor's Z-score, and the composite index. Also includes
        grid shape metadata (n_rows, n_cols) and cell coordinates (lon, lat).
        The figure-drawing functions below use this output directly.
    """
    # Load the pre-computed environmental layers from CSV
    env = pd.read_csv(ENV_CSV)
    lons = env["longitude"].values
    lats = env["latitude"].values

    # Compute the 6 raw factor values for every cell
    dist_city  = _min_dist_to_points(lons, lats, MAJOR_CITIES)
    dist_road  = _min_dist_to_roads(lons, lats)
    dist_water = _min_dist_to_water(lons, lats)
    slope      = env["slope_deg"].values       # from USGS 3DEP elevation data
    tmax       = env["july_tmax_c"].values     # from PRISM climate data
    ndvi       = env["ndvi"].values            # from USGS NAIP imagery (fetch_ndvi_layer.py)

    # Z-score function: subtract the mean, divide by standard deviation
    # Result: 0 = average cell, +1 = one SD above average, -1 = one SD below
    def zscore(x):
        return (x - np.nanmean(x)) / np.nanstd(x)

    z_temp  = zscore(tmax)       # higher temperature → higher Z → more dangerous
    z_city  = zscore(dist_city)  # farther from city  → higher Z → more dangerous
    z_road  = zscore(dist_road)  # farther from road  → higher Z → more dangerous
    z_water = zscore(dist_water) # farther from water → higher Z → more dangerous
    z_slope = zscore(slope)      # steeper slope      → higher Z → more dangerous
    z_ndvi  = zscore(ndvi)       # denser vegetation  → higher Z → more dangerous
                                  # (denser vegetation slows travel and disorients —
                                  #  not treated as protective shade here)

    # Sum all 6 Z-scores → composite danger index
    # A cell where ALL six factors are one SD above average would score +6.
    # A cell where all six are average would score 0.
    composite = z_temp + z_city + z_road + z_water + z_slope + z_ndvi

    return {
        "row": env["row"].values, "col": env["col"].values,
        "lon": lons, "lat": lats,
        "dist_city_deg": dist_city, "dist_road_deg": dist_road, "dist_water_deg": dist_water,
        "slope_deg": slope, "july_tmax_c": tmax, "ndvi": ndvi,
        "z_temp": z_temp, "z_city": z_city, "z_road": z_road,
        "z_water": z_water, "z_slope": z_slope, "z_ndvi": z_ndvi,
        "composite": composite,
        "n_rows": int(env["row"].max()) + 1,
        "n_cols": int(env["col"].max()) + 1,
    }


# =============================================================================
# SECTION 4: SUMMARY TABLE HELPER
# Adds a min/mean/max table for each raw factor below the map, so readers
# can see the actual range of values (e.g. temperatures from 34°C to 42°C)
# before Z-scoring. Distances in degrees are converted to approximate miles
# for readability.
# =============================================================================

def _draw_factor_summary(fig, result, in_az, lat_mid, summary_h, fig_h):
    """
    WHAT IT DOES:
        Renders a plain-text min/mean/max summary table for all 6 raw factors
        in the reserved space below the map. Distances are shown in miles
        (approximate — converted from degree-space using a mid-latitude average).
    """
    miles_per_deg_lat = 69.17
    miles_per_deg_lon = 69.17 * abs(math.cos(math.radians(lat_mid)))
    miles_per_deg = (miles_per_deg_lat + miles_per_deg_lon) / 2

    keep = in_az & ~np.isnan(result["composite"])
    rows = [
        ("Ambient summer (July) temperature", result["july_tmax_c"][keep], "C", 1),
        ("Distance to major city",            result["dist_city_deg"][keep] * miles_per_deg, "mi", 1),
        ("Distance to major road",            result["dist_road_deg"][keep] * miles_per_deg, "mi", 1),
        ("Distance to water source",          result["dist_water_deg"][keep] * miles_per_deg, "mi", 1),
        ("Slope",                             result["slope_deg"][keep], "deg", 1),
        ("Vegetation density (NDVI)",         result["ndvi"][keep], "", 3),
    ]

    lines = [f"Danger index factors (n={keep.sum()} grid cells within Arizona, min / mean / max):"]
    for name, values, unit, dp in rows:
        lines.append(f"  {name:<38s} {np.min(values):6.{dp}f}  /  {np.mean(values):6.{dp}f}  /  {np.max(values):6.{dp}f}  {unit}")

    y = (summary_h - 0.15) / fig_h
    fig.text(0.01, y, "\n".join(lines), ha="left", va="top", fontsize=7.5, family="monospace")


# =============================================================================
# SECTION 5: FIGURE 2 — RENDER THE DANGER INDEX MAP
# Draws the full danger index map: every grid cell in Arizona colored by its
# composite score (pale yellow = relatively less dangerous, dark red = most
# dangerous), with the standard basemap layers underneath.
#
# PIPELINE:
#   1. Compute the danger index for all cells
#   2. Determine which cells are actually inside Arizona (mask out Mexico/NM/CA)
#   3. Draw basemap layers (state boundary, roads, desert, reservation, fence)
#   4. Draw the colored danger-index raster (one rectangle per cell)
#   5. Add water stations, city labels, scale bar, north arrow, legend
#   6. Add the factor summary table below the map
#   7. Save PNG to figures/
# =============================================================================

def render_danger_index(out_filename="figure2_reproduction.png",
                         title="Figure 2: Danger Index"):
    result = compute_danger_index()
    print(f"  grid cells: {len(result['composite'])} ({result['n_rows']} rows x {result['n_cols']} cols)")
    n_nan = np.isnan(result["composite"]).sum()
    print(f"  composite index range: {np.nanmin(result['composite']):.2f} to {np.nanmax(result['composite']):.2f}"
          f" ({n_nan} cells with missing slope and/or NDVI data, excluded)")

    # --- ARIZONA MASK ---
    # The danger index grid covers a rectangular bounding box that spills into
    # Mexico, New Mexico, and California. We only color cells that fall inside
    # Arizona's actual state boundary. The shapely library's "contains" method
    # checks whether a point is inside a polygon.
    import shapefile
    from shapely.geometry import Point
    from shapely.prepared import prep
    sf = shapefile.Reader(str(bc.SHAPE_DIR / "tl_2021_us_state" / "tl_2021_us_state.shp"))
    field_names = [f[0] for f in sf.fields[1:]]
    az_shape = None
    for sr in sf.iterShapeRecords():
        if dict(zip(field_names, sr.record))["STATEFP"] == "04":
            from shapely.geometry import shape as shapely_shape
            az_shape = shapely_shape(sr.shape.__geo_interface__)
            break
    az_prepared = prep(az_shape)   # "prepared" = pre-processed for faster repeated lookups
    in_az = np.array([az_prepared.contains(Point(lo, la))
                       for lo, la in zip(result["lon"], result["lat"])])

    fence_before, fence_after, have_fence = bc.load_fence_layers()

    # Figure size with correct geographic aspect ratio
    lat_mid = (bc.BBOX["min_lat"] + bc.BBOX["max_lat"]) / 2
    geo_aspect = 1 / math.cos(math.radians(lat_mid))
    lon_span = bc.BBOX["max_lon"] - bc.BBOX["min_lon"]
    lat_span = bc.BBOX["max_lat"] - bc.BBOX["min_lat"]
    fig_w = 12
    map_h = fig_w * (lat_span * geo_aspect) / lon_span
    summary_h = 1.9    # extra height in inches for the factor-summary table below the map
    fig_h = map_h + summary_h
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.subplots_adjust(left=0.02, right=0.98, top=1 - 0.35 / fig_h, bottom=summary_h / fig_h)

    # Draw basemap layers
    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "tl_2021_us_state" / "tl_2021_us_state.shp",
        record_filter=lambda r: r["STATEFP"] == "04",
        closed=True, color="0.3", linewidth=0.8, zorder=6,
    )
    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "tl_2021_04_prisecroads" / "tl_2021_04_prisecroads.shp",
        record_filter=lambda r: r["RTTYP"] in ("I", "U", "S"),
        color="0.15", linewidth=0.5, zorder=6,
    )
    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "deserts_sw" / "deserts_sw.shp",
        record_filter=lambda r: r["NAME"] in ("Colorado Sonoran Desert", "Arizona Sonoran Desert"),
        closed=True, transform=bc.utm11n_to_lonlat,
        color=bc.DESERT_BROWN, linestyle=(0, (6, 2)), linewidth=1.6, zorder=6,
    )
    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "tl_2021_us_aiannh" / "tl_2021_us_aiannh.shp",
        record_filter=lambda r: r["NAMELSAD"] == "Tohono O'odham Nation Reservation",
        closed=True, color=bc.RESERVATION_PURPLE, linestyle=(0, (6, 2)), linewidth=1.3, zorder=6,
    )

    # --- DANGER INDEX RASTER ---
    # For each cell inside Arizona: look up its composite score, map it to
    # a color on the YlOrRd scale, draw a colored square at its position.
    # vabs = the maximum absolute score, used to center the color scale at 0.
    vabs = np.nanmax(np.abs(result["composite"][in_az]))
    half = hc.CELL_SIZE / 2
    for lon, lat, val, keep in zip(result["lon"], result["lat"], result["composite"], in_az):
        if not keep:
            continue
        color = DANGER_CMAP((val + vabs) / (2 * vabs))   # maps [-vabs, +vabs] → [0, 1] for colormap
        ax.add_patch(Rectangle((lon - half, lat - half), hc.CELL_SIZE, hc.CELL_SIZE,
                                facecolor=color, edgecolor="none", zorder=2))

    water = bc.load_water_stations()
    ax.scatter(water["longitude"], water["latitude"], s=30, marker="^",
               color=bc.WATER_STATION_COLOR, edgecolor="black", linewidth=0.4, zorder=5)

    for name, (lon, lat) in bc.CITIES.items():
        ax.annotate(name, (lon, lat), textcoords="offset points", xytext=(4, 4), fontsize=8, zorder=7)

    bc.draw_scale_bar(ax, lon0=-115.05, lat0=31.05, at_latitude=32.0)
    bc.draw_north_arrow(ax, lon=-114.9, lat=31.3)
    bc.draw_cell_size_note(ax, hc.CELL_SIZE, lon=-115.05, lat=30.95, reference_lat=lat_mid)

    # Legend: 5 color swatches spanning the observed score range
    n_swatches = 5
    edges = np.linspace(-vabs, vabs, n_swatches + 1)
    legend_handles = []
    for i in range(n_swatches):
        mid = (edges[i] + edges[i + 1]) / 2
        color = DANGER_CMAP((mid + vabs) / (2 * vabs))
        label = "Most dangerous" if i == n_swatches - 1 else ("Relatively least dangerous" if i == 0 else " ")
        legend_handles.append(Rectangle((0, 0), 1, 1, facecolor=color, edgecolor="none",
                                          label=f"{edges[i]:+.1f} to {edges[i+1]:+.1f}  {label}".strip()))
    legend_handles.append(Line2D([], [], marker="^", linestyle="", markerfacecolor=bc.WATER_STATION_COLOR,
                                   markeredgecolor="black", markeredgewidth=0.4, markersize=8,
                                   label=f"Water stations (n={len(water)})"))
    legend_handles.append(Line2D([], [], color=bc.DESERT_BROWN, linestyle=(0, (6, 2)), linewidth=1.6,
                                   label="Arizona Sonoran Desert"))
    legend_handles.append(Line2D([], [], color=bc.RESERVATION_PURPLE, linestyle=(0, (6, 2)), linewidth=1.3,
                                   label="Tohono O'odham Nation Reservation"))
    legend = ax.legend(handles=legend_handles, loc="upper right", fontsize=7.5,
                        title="Danger Index (sum of 6 Z-scores)", title_fontsize=9.5, frameon=True,
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

    _draw_factor_summary(fig, result, in_az, lat_mid, summary_h, fig_h)

    import datetime
    stamp = f"generated {datetime.datetime.now():%Y-%m-%d %H:%M:%S}"

    out_path = bc.FIGURES_DIR / out_filename
    fig.savefig(out_path, dpi=200)
    print(f"Saved plot to {out_path}")
    print(stamp)
    plt.show()
    return result


# =============================================================================
# SECTION 6: HELPER FUNCTIONS FOR FIGURE 8 (DANGER INDEX + HOT SPOTS OVERLAY)
# Figure 8 overlays the Gi* hot-spot results ON TOP of the danger index raster.
# These two helper functions are called by render_overlay_figure() below.
# =============================================================================

def _draw_danger_raster(ax, result, in_az, vabs):
    """
    WHAT IT DOES:
        Draws only the danger index colored rectangles (no basemap, no legend).
        Factored out separately so render_overlay_figure() can call it once
        per panel without duplicating code.
    """
    half = hc.CELL_SIZE / 2
    for lon, lat, val, keep in zip(result["lon"], result["lat"], result["composite"], in_az):
        if not keep:
            continue
        color = DANGER_CMAP((val + vabs) / (2 * vabs))
        ax.add_patch(Rectangle((lon - half, lat - half), hc.CELL_SIZE, hc.CELL_SIZE,
                                facecolor=color, edgecolor="none", zorder=2))


def _draw_hotspot_outlines(ax, gi_result):
    """
    WHAT IT DOES:
        Draws hot-spot cells as UNFILLED outlined squares on top of the danger
        index raster, so the danger-index color underneath remains visible
        through the middle of each hot-spot cell. Only 95% and 99% cells are
        outlined here (unlike figures 6/7 which also shade the pale-pink tier).

    WHY OUTLINES INSTEAD OF FILLED SQUARES:
        If hot-spot cells were filled (as in figures 6/7), they would completely
        cover the danger-index color underneath, defeating the purpose of this
        overlay figure which is to show WHERE the two align.
    """
    half = hc.CELL_SIZE / 2
    for lon, lat, gb in zip(gi_result["lon"], gi_result["lat"], gi_result["gi_bin"]):
        if gb == 3:
            edgecolor, lw = hc.HOT_99, 2.2
        elif gb == 2:
            edgecolor, lw = hc.HOT_95, 1.6
        else:
            continue   # skip cells below 95% confidence
        ax.add_patch(Rectangle((lon - half, lat - half), hc.CELL_SIZE, hc.CELL_SIZE,
                                facecolor="none", edgecolor=edgecolor, linewidth=lw, zorder=5))


# =============================================================================
# SECTION 7: FIGURE 8 — OVERLAY MAP (DANGER INDEX + HOT SPOTS, BOTH PERIODS)
# Produces a two-panel figure: pre-SFA on top, post-SFA below. Each panel
# shows the danger index raster with hot-spot cell outlines overlaid.
# The two panels share one legend (shown only on the top panel).
# =============================================================================

def render_overlay_figure(out_filename="figure8_reproduction.png",
                           title_pre="Figure 8a: Danger Index and Hot Spots, Pre-SFA (2000-2007)",
                           title_post="Figure 8b: Danger Index and Hot Spots, Post-SFA (2008-2019)"):
    """
    PIPELINE:
        1. Compute the danger index (shared by both panels)
        2. Determine which cells are inside Arizona
        3. Run Gi* hot-spot analysis on pre-SFA deaths → pre_gi
        4. Run Gi* hot-spot analysis on post-SFA deaths → post_gi
        5. Set up a 3-row figure layout: top panel, bottom panel, summary table
        6. Draw each panel: danger raster + hot-spot outlines + basemap layers
        7. Add one shared legend on the top panel
        8. Add the factor summary table in the bottom row
        9. Save PNG to figures/
    """
    result = compute_danger_index()

    # Arizona mask (same approach as render_danger_index above)
    import shapefile
    from shapely.geometry import Point, shape as shapely_shape
    from shapely.prepared import prep
    sf = shapefile.Reader(str(bc.SHAPE_DIR / "tl_2021_us_state" / "tl_2021_us_state.shp"))
    field_names = [f[0] for f in sf.fields[1:]]
    az_shape = None
    for sr in sf.iterShapeRecords():
        if dict(zip(field_names, sr.record))["STATEFP"] == "04":
            az_shape = shapely_shape(sr.shape.__geo_interface__)
            break
    az_prepared = prep(az_shape)
    in_az = np.array([az_prepared.contains(Point(lo, la)) for lo, la in zip(result["lon"], result["lat"])])
    vabs = np.nanmax(np.abs(result["composite"][in_az]))

    # Run Gi* for both periods
    deaths = bc.load_deaths()
    pre_gi = hc.compute_gi_star(
        hc.build_grid_counts(deaths.loc[deaths["is_pre_sfa"], "Longitude"],
                              deaths.loc[deaths["is_pre_sfa"], "Latitude"],
                              hc.CELL_SIZE, bc.BBOX["min_lon"], bc.BBOX["min_lat"]),
        hc.CELL_SIZE, bc.BBOX["min_lon"], bc.BBOX["min_lat"],
    )
    post_gi = hc.compute_gi_star(
        hc.build_grid_counts(deaths.loc[deaths["is_post_sfa"], "Longitude"],
                              deaths.loc[deaths["is_post_sfa"], "Latitude"],
                              hc.CELL_SIZE, bc.BBOX["min_lon"], bc.BBOX["min_lat"]),
        hc.CELL_SIZE, bc.BBOX["min_lon"], bc.BBOX["min_lat"],
    )
    from collections import Counter
    print(f"  pre-SFA:  {pre_gi['n_cells']} grid cells, "
          f"Gi_Bin counts: {dict(sorted(Counter(pre_gi['gi_bin']).items()))}")
    print(f"  post-SFA: {post_gi['n_cells']} grid cells, "
          f"Gi_Bin counts: {dict(sorted(Counter(post_gi['gi_bin']).items()))}")

    fence_before, fence_after, have_fence = bc.load_fence_layers()
    water = bc.load_water_stations()

    # Figure layout: two map panels stacked vertically, plus a summary table row
    lat_mid = (bc.BBOX["min_lat"] + bc.BBOX["max_lat"]) / 2
    geo_aspect = 1 / math.cos(math.radians(lat_mid))
    lon_span = bc.BBOX["max_lon"] - bc.BBOX["min_lon"]
    lat_span = bc.BBOX["max_lat"] - bc.BBOX["min_lat"]
    fig_w = 12
    panel_h = fig_w * (lat_span * geo_aspect) / lon_span
    summary_h = 1.9
    fig_h = panel_h * 2 + summary_h
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = fig.add_gridspec(3, 1, height_ratios=[panel_h, panel_h, summary_h], hspace=0.12,
                           top=1 - 0.3 / fig_h, bottom=0.02, left=0.02, right=0.98)
    ax_pre     = fig.add_subplot(gs[0])   # top panel: pre-SFA
    ax_post    = fig.add_subplot(gs[1])   # bottom panel: post-SFA
    ax_summary = fig.add_subplot(gs[2])   # summary table row
    ax_summary.axis("off")

    def draw_panel(ax, gi_result, title, show_legend):
        """Draws one complete panel (basemap + danger raster + hot-spot outlines)."""
        bc.plot_shapefile(ax, bc.SHAPE_DIR / "tl_2021_us_state" / "tl_2021_us_state.shp",
                           record_filter=lambda r: r["STATEFP"] == "04",
                           closed=True, color="0.3", linewidth=0.8, zorder=6)
        bc.plot_shapefile(ax, bc.SHAPE_DIR / "tl_2021_04_prisecroads" / "tl_2021_04_prisecroads.shp",
                           record_filter=lambda r: r["RTTYP"] in ("I", "U", "S"),
                           color="0.15", linewidth=0.5, zorder=6)
        bc.plot_shapefile(ax, bc.SHAPE_DIR / "deserts_sw" / "deserts_sw.shp",
                           record_filter=lambda r: r["NAME"] in ("Colorado Sonoran Desert", "Arizona Sonoran Desert"),
                           closed=True, transform=bc.utm11n_to_lonlat,
                           color=bc.DESERT_BROWN, linestyle=(0, (6, 2)), linewidth=1.6, zorder=6)
        bc.plot_shapefile(ax, bc.SHAPE_DIR / "tl_2021_us_aiannh" / "tl_2021_us_aiannh.shp",
                           record_filter=lambda r: r["NAMELSAD"] == "Tohono O'odham Nation Reservation",
                           closed=True, color=bc.RESERVATION_PURPLE, linestyle=(0, (6, 2)), linewidth=1.3, zorder=6)
        if have_fence:
            for gdf in fence_after:
                gdf.plot(ax=ax, color=bc.FENCE_YELLOW, linewidth=2.0, zorder=4)
            for gdf in fence_before:
                gdf.plot(ax=ax, color=bc.FENCE_BLUE, linewidth=2.0, zorder=4)

        # Core overlay: danger index raster first, then hot-spot outlines on top
        _draw_danger_raster(ax, result, in_az, vabs)
        _draw_hotspot_outlines(ax, gi_result)

        ax.scatter(water["longitude"], water["latitude"], s=30, marker="^",
                   color=bc.WATER_STATION_COLOR, edgecolor="black", linewidth=0.4, zorder=7)
        for name, (lon, lat) in bc.CITIES.items():
            ax.annotate(name, (lon, lat), textcoords="offset points", xytext=(4, 4), fontsize=8, zorder=8)
        bc.draw_scale_bar(ax, lon0=-115.05, lat0=31.05, at_latitude=32.0)
        bc.draw_north_arrow(ax, lon=-114.9, lat=31.3)
        bc.draw_cell_size_note(ax, hc.CELL_SIZE, lon=-115.05, lat=30.95, reference_lat=lat_mid)

        ax.set_xlim(bc.BBOX["min_lon"], bc.BBOX["max_lon"])
        ax.set_ylim(bc.BBOX["min_lat"], bc.BBOX["max_lat"])
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color("black")
            spine.set_linewidth(1.0)
        ax.set_title(title, fontsize=11)
        ax.set_aspect(geo_aspect)

        # Legend appears only on the top panel to avoid redundancy
        if show_legend:
            n_swatches = 5
            edges = np.linspace(-vabs, vabs, n_swatches + 1)
            legend_handles = []
            for i in range(n_swatches):
                mid = (edges[i] + edges[i + 1]) / 2
                color = DANGER_CMAP((mid + vabs) / (2 * vabs))
                label = "Most dangerous" if i == n_swatches - 1 else ("Relatively least dangerous" if i == 0 else " ")
                legend_handles.append(Rectangle((0, 0), 1, 1, facecolor=color, edgecolor="none",
                                                  label=f"{edges[i]:+.1f} to {edges[i+1]:+.1f}  {label}".strip()))
            legend_handles.append(Rectangle((0, 0), 1, 1, facecolor="none", edgecolor=hc.HOT_99, linewidth=2.2,
                                              label="Hot Spot - 99% Confidence"))
            legend_handles.append(Rectangle((0, 0), 1, 1, facecolor="none", edgecolor=hc.HOT_95, linewidth=1.6,
                                              label="Hot Spot - 95% Confidence"))
            legend_handles.append(Line2D([], [], marker="^", linestyle="", markerfacecolor=bc.WATER_STATION_COLOR,
                                           markeredgecolor="black", markeredgewidth=0.4, markersize=8,
                                           label=f"Water stations (n={len(water)})"))
            if have_fence:
                legend_handles.append(Line2D([], [], color=bc.FENCE_YELLOW, linewidth=2.0, label="Border built 2008 or later"))
                legend_handles.append(Line2D([], [], color=bc.FENCE_BLUE, linewidth=2.0, label="Border built 2007 or before"))
            legend_handles.append(Line2D([], [], color=bc.DESERT_BROWN, linestyle=(0, (6, 2)), linewidth=1.6, label="Arizona Sonoran Desert"))
            legend_handles.append(Line2D([], [], color=bc.RESERVATION_PURPLE, linestyle=(0, (6, 2)), linewidth=1.3, label="Tohono O'odham Nation Reservation"))
            legend = ax.legend(handles=legend_handles, loc="upper right", fontsize=7,
                                title="Danger Index (sum of 6 Z-scores) + Hot Spots", title_fontsize=8.5,
                                frameon=True, edgecolor="black", facecolor="white")
            legend.get_title().set_fontweight("bold")
            legend._legend_box.align = "left"

    draw_panel(ax_pre,  pre_gi,  title_pre,  show_legend=True)
    draw_panel(ax_post, post_gi, title_post, show_legend=False)

    _draw_factor_summary_axes(ax_summary, result, in_az, lat_mid)

    import datetime
    stamp = f"generated {datetime.datetime.now():%Y-%m-%d %H:%M:%S}"

    out_path = bc.FIGURES_DIR / out_filename
    fig.savefig(out_path, dpi=200)
    print(f"Saved plot to {out_path}")
    print(stamp)
    plt.show()
    return {"pre": pre_gi, "post": post_gi, "danger_index": result}


def _draw_factor_summary_axes(ax, result, in_az, lat_mid):
    """
    WHAT IT DOES:
        Same min/mean/max summary table as _draw_factor_summary(), but
        rendered into a proper Axes object (the third row of the GridSpec
        in render_overlay_figure) rather than using raw figure coordinates.
        The two-panel figure layout made using an Axes more natural here.
    """
    miles_per_deg_lat = 69.17
    miles_per_deg_lon = 69.17 * abs(math.cos(math.radians(lat_mid)))
    miles_per_deg = (miles_per_deg_lat + miles_per_deg_lon) / 2

    keep = in_az & ~np.isnan(result["composite"])
    lines = [f"Danger index factors (n={keep.sum()} grid cells within Arizona, min / mean / max) -- shared by both panels above:"]
    rows = [
        ("Ambient summer (July) temperature", result["july_tmax_c"][keep], "C", 1),
        ("Distance to major city",            result["dist_city_deg"][keep] * miles_per_deg, "mi", 1),
        ("Distance to major road",            result["dist_road_deg"][keep] * miles_per_deg, "mi", 1),
        ("Distance to water source",          result["dist_water_deg"][keep] * miles_per_deg, "mi", 1),
        ("Slope",                             result["slope_deg"][keep], "deg", 1),
        ("Vegetation density (NDVI)",         result["ndvi"][keep], "", 3),
    ]
    for name, values, unit, dp in rows:
        lines.append(f"  {name:<38s} {np.min(values):6.{dp}f}  /  {np.mean(values):6.{dp}f}  /  {np.max(values):6.{dp}f}  {unit}")
    ax.text(0.01, 0.95, "\n".join(lines), ha="left", va="top", fontsize=7.5, family="monospace",
            transform=ax.transAxes)
