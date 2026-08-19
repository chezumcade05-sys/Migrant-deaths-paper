"""
A rebuilt version of the paper's danger index (Section 4.1 / Figure 2),
using a different factor set and a different scoring method than the
original -- see DANGER_INDEX_METHODOLOGY.md for the full write-up.

Original paper: 6 factors (distance to road/city/tribal-land, distance to
river/desert, slope), each bucketed into an ordinal 1-5/1-6 category score,
summed.

This version: 6 factors --
    1. Ambient summer (July) temperature
    2. Distance to a major city (Phoenix, Tucson)
    3. Distance to a major road (Interstate/US/State highway)
    4. Distance to a water source (Humane Borders water station)
    5. Slope
    6. Vegetation density (NDVI) -- added on a peer reviewer's suggestion,
       following Boyce, Chambers & Launius (2019)'s "ruggedness index":
       denser vegetation is treated as MORE dangerous (slows travel,
       disorients), not as protective shade. See DANGER_INDEX_METHODOLOGY.md.
-- each standardized to a Z-score across the full study-area grid (not
bucketed into ordinal categories), summed into one composite index. The
grid uses the exact same cell size and origin as the hot-spot analysis
(hotspot_common.CELL_SIZE, basemap_common.BBOX), so the two are spatially
aligned and comparable, but this grid covers every cell in the study area
(a continuous surface), not just cells with a recorded death.

Requires basemap_common.py (for CITIES, SHAPE_DIR, BBOX, load_water_stations,
plot_shapefile, draw_scale_bar, draw_north_arrow) and hotspot_common.py
(for CELL_SIZE) to already be imported by the entry script.
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

ENV_CSV = bc.DATA_DIR / "Danger Index Environmental Layers.csv"

# Real, substantial Arizona cities only -- the small border towns in
# bc.CITIES (Nogales, Sasabe, Sonoyta) are map-orientation labels, not the
# "major city" reference points this factor is meant to represent.
MAJOR_CITIES = {"Phoenix": bc.CITIES["Phoenix"], "Tucson": bc.CITIES["Tucson"]}

# Pale yellow (relatively less dangerous) -> orange -> dark red (most
# dangerous). Deliberately NOT the original paper's green-to-red scheme:
# green reads as "safe," which is the wrong message for a desert crossing
# where even the "least dangerous" areas are still hazardous -- and
# red-green is also the single most common form of color blindness. YlOrRd
# is a sequential, colorblind-safe ColorBrewer palette with no green at all.
DANGER_CMAP = plt.get_cmap("YlOrRd")


def _min_dist_to_points(lons, lats, ref_lonlat):
    """Euclidean (degree-space) distance from each (lon,lat) grid point to
    the nearest of a small set of reference points."""
    ref = np.array(list(ref_lonlat.values()))
    d = np.full(len(lons), np.inf)
    for rlon, rlat in ref:
        d = np.minimum(d, np.hypot(lons - rlon, lats - rlat))
    return d


def _min_dist_to_roads(lons, lats):
    """Euclidean (degree-space) distance from each grid point to the
    nearest Interstate/US/State highway segment in Arizona."""
    import shapefile  # pyshp
    from shapely.geometry import Point, LineString
    from shapely.ops import unary_union
    from shapely.strtree import STRtree

    sf = shapefile.Reader(str(bc.SHAPE_DIR / "tl_2021_04_prisecroads" / "tl_2021_04_prisecroads.shp"))
    field_names = [f[0] for f in sf.fields[1:]]
    lines = []
    for sr in sf.iterShapeRecords():
        rec = dict(zip(field_names, sr.record))
        if rec["RTTYP"] not in ("I", "U", "S"):
            continue
        pts = sr.shape.points
        parts = list(sr.shape.parts) + [len(pts)]
        for i in range(len(parts) - 1):
            seg = pts[parts[i]:parts[i + 1]]
            if len(seg) >= 2:
                lines.append(LineString(seg))

    tree = STRtree(lines)
    d = np.empty(len(lons))
    for i, (lon, lat) in enumerate(zip(lons, lats)):
        p = Point(lon, lat)
        nearest_idx = tree.nearest(p)
        d[i] = p.distance(lines[nearest_idx])
    return d


def _min_dist_to_water(lons, lats):
    water = bc.load_water_stations()
    d = np.full(len(lons), np.inf)
    for wlon, wlat in zip(water["longitude"], water["latitude"]):
        d = np.minimum(d, np.hypot(lons - wlon, lats - wlat))
    return d


def _compute_az_mask(lons, lats):
    """True for grid cells whose center falls within Arizona's state
    boundary. Factored out so compute_danger_index() and every render
    function share one computation instead of each re-reading the
    shapefile and re-running the point-in-polygon test."""
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
    return np.array([az_prepared.contains(Point(lo, la)) for lo, la in zip(lons, lats)])


def compute_danger_index():
    """Returns a dict of per-cell arrays (row, col, lon, lat, the 6 raw
    factor values, their Z-scores, and the summed composite index), plus
    the grid shape, ready to render or inspect.

    Each factor is standardized using the mean/std of *only the in-Arizona
    cells* -- not the full rectangular grid, which extends into slivers of
    Mexico, California, and New Mexico that aren't part of the study area.
    Z-scores are still returned for every cell (on that Arizona-derived
    scale), but nothing outside Arizona contributes to the scale itself.
    See DANGER_INDEX_METHODOLOGY.md."""
    env = pd.read_csv(ENV_CSV)
    lons = env["longitude"].values
    lats = env["latitude"].values
    in_az = _compute_az_mask(lons, lats)

    dist_city = _min_dist_to_points(lons, lats, MAJOR_CITIES)
    dist_road = _min_dist_to_roads(lons, lats)
    dist_water = _min_dist_to_water(lons, lats)
    slope = env["slope_deg"].values
    tmax = env["july_tmax_c"].values
    ndvi = env["ndvi"].values

    def zscore(x):
        az_mean = np.nanmean(x[in_az])
        az_std = np.nanstd(x[in_az])
        return (x - az_mean) / az_std

    z_temp = zscore(tmax)
    z_city = zscore(dist_city)
    z_road = zscore(dist_road)
    z_water = zscore(dist_water)
    z_slope = zscore(slope)
    # Higher NDVI (denser vegetation) is treated as MORE dangerous, not as
    # protective shade -- matching Boyce, Chambers & Launius (2019)'s
    # "ruggedness index", the precedent for including a vegetation/"shade"
    # factor here: dense vegetation slows travel, disorients, and
    # increases exertion. See DANGER_INDEX_METHODOLOGY.md.
    z_ndvi = zscore(ndvi)

    composite = z_temp + z_city + z_road + z_water + z_slope + z_ndvi

    return {
        "row": env["row"].values, "col": env["col"].values,
        "lon": lons, "lat": lats, "in_az": in_az,
        "dist_city_deg": dist_city, "dist_road_deg": dist_road, "dist_water_deg": dist_water,
        "slope_deg": slope, "july_tmax_c": tmax, "ndvi": ndvi,
        "z_temp": z_temp, "z_city": z_city, "z_road": z_road, "z_water": z_water,
        "z_slope": z_slope, "z_ndvi": z_ndvi,
        "composite": composite,
        "n_rows": int(env["row"].max()) + 1, "n_cols": int(env["col"].max()) + 1,
    }


def _draw_factor_summary(fig, result, in_az, lat_mid, summary_h, fig_h):
    """Adds a min/max/mean table for the 5 raw (pre-Z-score) factors in
    the dedicated blank margin reserved below the map (see summary_h in
    render_danger_index). Distance factors are stored in Euclidean
    degree-space; converted here to an approximate miles figure for
    readability using the mid-latitude average of a longitude-degree and a
    latitude-degree's real length -- a rough conversion, consistent with
    how distance is approximated elsewhere in this project (see
    DANGER_INDEX_METHODOLOGY.md), not a precise geodesic distance."""
    miles_per_deg_lat = 69.17
    miles_per_deg_lon = 69.17 * abs(math.cos(math.radians(lat_mid)))
    miles_per_deg = (miles_per_deg_lat + miles_per_deg_lon) / 2

    keep = in_az & ~np.isnan(result["composite"])
    rows = [
        ("Ambient summer (July) temperature", result["july_tmax_c"][keep], "C", 1),
        ("Distance to major city", result["dist_city_deg"][keep] * miles_per_deg, "mi", 1),
        ("Distance to major road", result["dist_road_deg"][keep] * miles_per_deg, "mi", 1),
        ("Distance to water source", result["dist_water_deg"][keep] * miles_per_deg, "mi", 1),
        ("Slope", result["slope_deg"][keep], "deg", 1),
        ("Vegetation density (NDVI)", result["ndvi"][keep], "", 3),
    ]

    lines = [f"Danger index factors (n={keep.sum()} grid cells within Arizona, min / mean / max):"]
    for name, values, unit, dp in rows:
        lines.append(f"  {name:<38s} {np.min(values):6.{dp}f}  /  {np.mean(values):6.{dp}f}  /  {np.max(values):6.{dp}f}  {unit}")

    # Positioned near the top of the reserved bottom margin (in figure-
    # fraction terms).
    y = (summary_h - 0.15) / fig_h
    fig.text(0.01, y, "\n".join(lines), ha="left", va="top", fontsize=7.5, family="monospace")


def render_danger_index(out_filename="figure2_reproduction.png",
                         title="Figure 2: Danger Index"):
    result = compute_danger_index()
    print(f"  grid cells: {len(result['composite'])} ({result['n_rows']} rows x {result['n_cols']} cols)")
    n_nan = np.isnan(result["composite"]).sum()
    print(f"  composite index range: {np.nanmin(result['composite']):.2f} to {np.nanmax(result['composite']):.2f}"
          f" ({n_nan} cells with missing slope and/or NDVI data, excluded)")

    # Mask to cells within Arizona -- a full rectangular bbox would color
    # parts of Mexico/California/New Mexico that aren't meaningful here.
    # (Also the same mask used inside compute_danger_index() to standardize
    # the Z-scores -- computed once there, just reused here for rendering.)
    in_az = result["in_az"]

    fence_before, fence_after, have_fence = bc.load_fence_layers()

    lat_mid = (bc.BBOX["min_lat"] + bc.BBOX["max_lat"]) / 2
    geo_aspect = 1 / math.cos(math.radians(lat_mid))
    lon_span = bc.BBOX["max_lon"] - bc.BBOX["min_lon"]
    lat_span = bc.BBOX["max_lat"] - bc.BBOX["min_lat"]
    fig_w = 12
    map_h = fig_w * (lat_span * geo_aspect) / lon_span
    # Extra vertical space reserved below the map for the factor-summary
    # table added at the end of this function -- tight_layout() doesn't
    # know about fig.text() elements, so without this the summary text
    # would overlap the map/scale bar instead of sitting cleanly below it.
    # 1.9in fits the title line + 6 factor rows at fontsize 7.5.
    summary_h = 1.9
    fig_h = map_h + summary_h
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    fig.subplots_adjust(left=0.02, right=0.98, top=1 - 0.35 / fig_h, bottom=summary_h / fig_h)

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

    # Danger index raster: one colored square per grid cell, colored by
    # composite Z-score, pale yellow (relatively less dangerous) -> dark red
    # (most dangerous).
    vabs = np.nanmax(np.abs(result["composite"][in_az]))
    half = hc.CELL_SIZE / 2
    for lon, lat, val, keep in zip(result["lon"], result["lat"], result["composite"], in_az):
        if not keep:
            continue
        color = DANGER_CMAP((val + vabs) / (2 * vabs))
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

    # Colorbar-style legend swatches (5 bins across the observed range).
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
    if title:
        ax.set_title(title)
    ax.set_aspect(geo_aspect)

    _draw_factor_summary(fig, result, in_az, lat_mid, summary_h, fig_h)

    import datetime
    stamp = f"generated {datetime.datetime.now():%Y-%m-%d %H:%M:%S}"

    # Not fig.tight_layout() here -- it would discard the explicit
    # subplots_adjust() margins set above that reserve room for the
    # factor-summary text below the map.
    out_path = bc.FIGURES_DIR / out_filename
    fig.savefig(out_path, dpi=200)
    print(f"Saved plot to {out_path}")
    print(stamp)
    plt.show()
    return result


def _draw_danger_raster(ax, result, in_az, vabs):
    half = hc.CELL_SIZE / 2
    for lon, lat, val, keep in zip(result["lon"], result["lat"], result["composite"], in_az):
        if not keep:
            continue
        color = DANGER_CMAP((val + vabs) / (2 * vabs))
        ax.add_patch(Rectangle((lon - half, lat - half), hc.CELL_SIZE, hc.CELL_SIZE,
                                facecolor=color, edgecolor="none", zorder=2))


def _draw_hotspot_outlines(ax, gi_result):
    """Significant (95%/99%) hot-spot cells drawn as UNFILLED outlined
    squares -- reusing hotspot_common.HOT_99/HOT_95 exactly as their edge
    color, no new colors -- so the danger-index color underneath stays
    visible through the middle of each cell. Cells below 95% confidence
    are left undrawn here (unlike figure6.py/figure7.py, which tint every
    populated cell); this figure is about where hot spots and danger
    overlap, not the full underlying death distribution."""
    half = hc.CELL_SIZE / 2
    for lon, lat, gb in zip(gi_result["lon"], gi_result["lat"], gi_result["gi_bin"]):
        if gb == 3:
            edgecolor, lw = hc.HOT_99, 2.2
        elif gb == 2:
            edgecolor, lw = hc.HOT_95, 1.6
        else:
            continue
        ax.add_patch(Rectangle((lon - half, lat - half), hc.CELL_SIZE, hc.CELL_SIZE,
                                facecolor="none", edgecolor=edgecolor, linewidth=lw, zorder=5))


def render_overlay_figure(out_filename="figure8_reproduction.png",
                           title_pre="Figure 8a: Danger Index and Hot Spots, Pre-SFA (2000-2007)",
                           title_post="Figure 8b: Danger Index and Hot Spots, Post-SFA (2008-2019)"):
    """Reproduces the original paper's Figure 8 (hot spots overlaid on the
    danger index), extended to show BOTH periods rather than one combined
    map: the pre-SFA and post-SFA Gi* results each drawn as unfilled
    outlined squares (colored by confidence tier, exactly like
    figure6.py/figure7.py) on top of the shared 6-factor danger-index
    raster, as two vertically stacked panels with one shared legend.
    Two panels instead of one combined map: a single panel showing both
    periods' significant cells at once would need a second color/style
    dimension for "which period", competing with the confidence-tier
    colors already carrying meaning and with the fence-line colors already
    on the map -- two panels keep every existing color meaning exactly
    the same as figure2.py/figure6.py/figure7.py, per the point of this
    figure being an overlay of already-established results, not a new
    visual language.

    Relies on the same grid alignment between the danger index and the
    hot-spot analysis (identical CELL_SIZE and origin) documented in
    DANGER_INDEX_METHODOLOGY.md -- that's what makes an exact cell-for-cell
    overlay possible at all.
    """
    result = compute_danger_index()
    in_az = result["in_az"]
    vabs = np.nanmax(np.abs(result["composite"][in_az]))

    deaths = bc.load_deaths()
    pre_gi = hc.compute_gi_star(
        hc.build_grid_counts(deaths.loc[deaths["is_pre_sfa"], "Longitude"], deaths.loc[deaths["is_pre_sfa"], "Latitude"],
                              hc.CELL_SIZE, bc.BBOX["min_lon"], bc.BBOX["min_lat"]),
        hc.CELL_SIZE, bc.BBOX["min_lon"], bc.BBOX["min_lat"],
    )
    post_gi = hc.compute_gi_star(
        hc.build_grid_counts(deaths.loc[deaths["is_post_sfa"], "Longitude"], deaths.loc[deaths["is_post_sfa"], "Latitude"],
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
    ax_pre = fig.add_subplot(gs[0])
    ax_post = fig.add_subplot(gs[1])
    ax_summary = fig.add_subplot(gs[2])
    ax_summary.axis("off")

    def draw_panel(ax, gi_result, title, show_legend):
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
        if have_fence:
            for gdf in fence_after:
                gdf.plot(ax=ax, color=bc.FENCE_YELLOW, linewidth=2.0, zorder=4)
            for gdf in fence_before:
                gdf.plot(ax=ax, color=bc.FENCE_BLUE, linewidth=2.0, zorder=4)

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
        if title:
            ax.set_title(title, fontsize=11)
        ax.set_aspect(geo_aspect)

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
                                title="Danger Index (sum of 6 Z-scores) + Hot Spots", title_fontsize=8.5, frameon=True,
                                edgecolor="black", facecolor="white")
            legend.get_title().set_fontweight("bold")
            legend._legend_box.align = "left"

    draw_panel(ax_pre, pre_gi, title_pre, show_legend=True)
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
    """Same table (and same mile conversion) as _draw_factor_summary(),
    targeting a dedicated Axes (render_overlay_figure's third GridSpec
    row) instead of raw fig.text() figure-fraction coordinates --
    render_danger_index doesn't use a real Axes for its summary row, but a
    3-row GridSpec (two map panels + one summary row) makes an Axes the
    more natural fit here."""
    miles_per_deg_lat = 69.17
    miles_per_deg_lon = 69.17 * abs(math.cos(math.radians(lat_mid)))
    miles_per_deg = (miles_per_deg_lat + miles_per_deg_lon) / 2

    keep = in_az & ~np.isnan(result["composite"])
    lines = [f"Danger index factors (n={keep.sum()} grid cells within Arizona, min / mean / max) -- shared by both panels above:"]
    rows = [
        ("Ambient summer (July) temperature", result["july_tmax_c"][keep], "C", 1),
        ("Distance to major city", result["dist_city_deg"][keep] * miles_per_deg, "mi", 1),
        ("Distance to major road", result["dist_road_deg"][keep] * miles_per_deg, "mi", 1),
        ("Distance to water source", result["dist_water_deg"][keep] * miles_per_deg, "mi", 1),
        ("Slope", result["slope_deg"][keep], "deg", 1),
        ("Vegetation density (NDVI)", result["ndvi"][keep], "", 3),
    ]
    for name, values, unit, dp in rows:
        lines.append(f"  {name:<38s} {np.min(values):6.{dp}f}  /  {np.mean(values):6.{dp}f}  /  {np.max(values):6.{dp}f}  {unit}")
    ax.text(0.01, 0.95, "\n".join(lines), ha="left", va="top", fontsize=7.5, family="monospace",
            transform=ax.transAxes)
