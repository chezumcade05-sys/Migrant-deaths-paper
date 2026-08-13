"""
Shared basemap/plotting logic for reproducing Figures 3, 4, and 5 from
Bansak, Blanco, Coon & Dieringer (2025), "Border Walls and Death on the
US-Mexico Border." All three figures share the same base layer (state
boundary, roads, desert boundary, reservation boundary, border fencing,
scale bar, north arrow, legend style) and differ only in which subset of
migrant-death points is plotted. figure3.py / figure4.py / figure5.py each
import this module and call render_figure() with their own subset.

Data used (expected next to this module, in the same folder):
    - Original death data.csv          Arizona OpenGIS Initiative for Deceased
                                        Migrants (PCMOE / Humane Borders)
    - Original Fence data/01-ORIGINAL.gdb
                                        CBP tactical-infrastructure geodatabase
                                        (marked FOUO in its metadata)
    - Shape Files/                     Basemap geography (Census TIGER/Line
                                        2021 counties/tribal areas/roads/
                                        states, USGS 2006 desert survey)
    - Water Stations 2000-2019.csv     Humane Borders water station locations,
                                        extracted from their own published
                                        poster (not surveyed) -- see
                                        WATER_STATIONS_METHODOLOGY.md

This module assumes the re-exec-into-.venv trick (see the top of figure4.py)
has already run in the entry-point script, so it's safe to import pandas/
geopandas/matplotlib here without checking the interpreter itself.
"""

import datetime
import math
import re
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import shapefile  # pyshp
import utm  # pure-Python UTM <-> lat/lon conversion (no PROJ/GDAL needed)

# Colors sampled directly from the original figures' legend swatches (the
# embedded JPEGs inside the .docx), so the reproduction's palette matches.
DEATH_GREEN = "#27e32c"
FENCE_BLUE = "#205aae"    # "Border built 2007 or before"
FENCE_YELLOW = "#ffe600"  # "Border built 2008 or later"
DESERT_BROWN = "#82604f"
RESERVATION_PURPLE = "#3d1a5b"
# Not sourced from the paper -- a distinct teal, chosen to read clearly
# against both the green death markers and the navy fence lines.
WATER_STATION_COLOR = "#00b7c3"

# Repo layout: this file lives in python/, siblings to r/, data/, figures/,
# and docs/ at the repo root -- REPO_ROOT is python/'s parent.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
FIGURES_DIR = REPO_ROOT / "figures"
DEATH_CSV = DATA_DIR / "Original death data.csv"
FENCE_GDB = DATA_DIR / "Original Fence data" / "01-ORIGINAL.gdb"
SHAPE_DIR = DATA_DIR / "Shape Files"
# Extracted from Humane Borders' own public poster -- see
# WATER_STATIONS_METHODOLOGY.md for how, and for the ~5 mile positional
# uncertainty this carries. Used for all figures regardless of period: an
# earlier 2000-2007-poster extraction was tried and dropped -- it needed a
# manual correction for points landing south of the border and disagreed
# with this dataset by ~29 miles on average, so this (2000-2019) extraction
# is the one now used everywhere as the more reliable of the two.
WATER_STATIONS_CSV = DATA_DIR / "Water Stations 2000-2019.csv"

# Study-area bounding box (roughly southern Arizona), used to crop the
# nationwide TIGER/Line layers down to the relevant area.
BBOX = {"min_lon": -115.2, "max_lon": -109.0, "min_lat": 30.8, "max_lat": 34.3}

FENCE_LAYERS = [
    "obp_baseline_ti_ped_fence_LIMIT_GOV_USE",
    "obp_baseline_ti_veh_barrier_LIMIT_GOV_USE",
]

CITIES = {
    "Phoenix": (-112.0740, 33.4484),
    "Tucson": (-110.9265, 32.2217),
    "Nogales": (-110.9370, 31.3379),
    "Sasabe": (-111.5410, 31.4890),
    "Sonoyta": (-112.8380, 31.8620),
}


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def plot_shapefile(ax, shp_path, record_filter=None, closed=False, transform=None,
                    **line_kwargs):
    """Draw every part of every shape in a (possibly filtered) shapefile.
    pyshp doesn't reproject -- TIGER/Line layers are already in geographic
    coordinates close enough to WGS84 for this map scale, but the USGS
    desert layer is in projected UTM meters and needs `transform`.

    transform, if given, is applied to each (x, y) point and must return
    (lon, lat)."""
    sf = shapefile.Reader(str(shp_path))
    field_names = [f[0] for f in sf.fields[1:]]
    drawn = False
    for sr in sf.iterShapeRecords():
        rec = dict(zip(field_names, sr.record))
        if record_filter is not None and not record_filter(rec):
            continue
        shape = sr.shape
        points = shape.points
        if transform is not None:
            points = [transform(x, y) for x, y in points]
        parts = list(shape.parts) + [len(points)]
        for i in range(len(parts) - 1):
            part_pts = points[parts[i]:parts[i + 1]]
            if closed and part_pts[0] != part_pts[-1]:
                part_pts = part_pts + [part_pts[0]]
            xs = [p[0] for p in part_pts]
            ys = [p[1] for p in part_pts]
            label = line_kwargs.pop("label", None) if not drawn else None
            ax.plot(xs, ys, label=label, **line_kwargs)
            drawn = True
    return drawn


def utm11n_to_lonlat(x, y):
    """NAD27 UTM Zone 11N (meters) -> approx (lon, lat). Uses the WGS84
    ellipsoid rather than Clarke 1866/NAD27, a ~100-200m datum shift that's
    negligible at this map's scale (study area spans ~500 km)."""
    lat, lon = utm.to_latlon(x, y, 11, "N", strict=False)
    return lon, lat


def draw_scale_bar(ax, lon0, lat0, at_latitude, miles=(0, 15, 30, 60)):
    """A simple alternating-segment scale bar, degrees-longitude-per-mile
    computed at `at_latitude` (longitude degrees shrink with latitude)."""
    miles_per_degree = 69.17 * abs(math.cos(math.radians(at_latitude)))
    deg_per_mile = 1 / miles_per_degree
    tick_h = 0.045
    for i in range(len(miles) - 1):
        x0 = lon0 + miles[i] * deg_per_mile
        x1 = lon0 + miles[i + 1] * deg_per_mile
        face = "black" if i % 2 == 0 else "white"
        ax.add_patch(plt.Rectangle((x0, lat0), x1 - x0, tick_h / 3,
                                     facecolor=face, edgecolor="black", linewidth=0.6, zorder=10))
    for m in miles:
        x = lon0 + m * deg_per_mile
        ax.plot([x, x], [lat0, lat0 + tick_h], color="black", linewidth=0.6, zorder=10)
        ax.annotate(str(m), (x, lat0 - 0.02), ha="center", va="top", fontsize=6.5, zorder=10)
    end_x = lon0 + miles[-1] * deg_per_mile
    ax.annotate("Miles", (end_x + 0.05, lat0), ha="left", va="center", fontsize=6.5, zorder=10)


def draw_north_arrow(ax, lon, lat, size=0.12):
    ax.annotate("", xy=(lon, lat + size), xytext=(lon, lat),
                arrowprops=dict(arrowstyle="-|>", color="black", linewidth=1.2),
                zorder=10)
    ax.annotate("N", (lon, lat + size + 0.03), ha="center", va="bottom",
                fontsize=9, fontweight="bold", zorder=10)


def draw_cell_size_note(ax, cell_size_deg, lon, lat, reference_lat, fontsize=6.5):
    """A text note (not a true-to-scale box -- a single 0.044 deg cell
    would be an imperceptible speck at this map's zoom level) stating the
    raster grid's cell size, in degrees and in approximate real-world
    miles at the study area's latitude. For figures that render data as a
    fixed-size grid of cells (hot-spot analysis, danger index) rather than
    individual points. Placed near the scale bar so a reader can connect
    the two distance references."""
    miles_per_deg_lat = 69.17
    miles_per_deg_lon = 69.17 * abs(math.cos(math.radians(reference_lat)))
    h_mi = cell_size_deg * miles_per_deg_lat
    w_mi = cell_size_deg * miles_per_deg_lon
    label = f"Grid cell size: {cell_size_deg:g}° (≈{w_mi:.1f} × {h_mi:.1f} mi)"
    ax.annotate(label, (lon, lat), ha="left", va="top", fontsize=fontsize, zorder=10,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.75))


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load_deaths():
    """Load migrant death data and reproduce the paper's pre/post-SFA split
    (Section 4.2). Adds boolean columns 'is_pre_sfa' / 'is_post_sfa'; their
    union reproduces Figure 3's combined 2000-2019 dataset. Verified to
    match the paper's reported totals: 1,215 pre-SFA / 1,826 post-SFA /
    3,041 combined (Table 4)."""
    deaths = pd.read_csv(DEATH_CSV)
    deaths["Reporting Date"] = pd.to_datetime(deaths["Reporting Date"], errors="coerce")
    deaths["year"] = deaths["Reporting Date"].dt.year
    pmi = deaths["Post Mortem Interval"].str.strip()

    # A 2008 discovery whose postmortem interval was "> 6-8 months" is moved
    # into the pre-SFA bucket, since the death itself likely occurred in
    # 2007 even though the remains were found in 2008 (paper, Sec. 4.2).
    reclassified_2008 = (deaths["year"] == 2008) & (pmi == "> 6-8 months")

    deaths["is_pre_sfa"] = deaths["year"].between(2000, 2007) | reclassified_2008
    deaths["is_post_sfa"] = (deaths["year"].between(2008, 2019) & pmi.notna()
                              & ~reclassified_2008)
    return deaths


def _date_in_year(value):
    """Pull the leading 4-digit year out of the messy DATE_IN field, e.g.
    '20070615' -> 2007, '2004* or before' -> 2004, '1998 EST' -> 1998."""
    if value is None:
        return None
    m = re.match(r"(\d{4})", str(value))
    return int(m.group(1)) if m else None


def load_water_stations():
    """Coordinates were extracted from a Humane Borders published poster,
    not surveyed directly -- see WATER_STATIONS_METHODOLOGY.md for the
    method and its uncertainty."""
    return pd.read_csv(WATER_STATIONS_CSV)


def load_fence_layers():
    """Load AZ border fencing, split into pre-2008 / 2008-or-later. Returns
    (fence_before, fence_after, have_fence) -- the first two are lists of
    GeoDataFrames (empty if have_fence is False)."""
    fence_before, fence_after = [], []
    have_fence = False
    try:
        import geopandas as gpd

        for layer in FENCE_LAYERS:
            gdf = gpd.read_file(FENCE_GDB, layer=layer)  # already EPSG:4326
            gdf = gdf[gdf["STATE_ABBR"] == "AZ"].copy()
            gdf["year_in"] = gdf["DATE_IN"].apply(_date_in_year)
            fence_before.append(gdf[gdf["year_in"] <= 2007])
            fence_after.append(gdf[gdf["year_in"] >= 2008])
        have_fence = True
    except Exception as e:
        print(f"Could not load fence geodatabase layers ({e}).")
        print("To include fence lines, install a working GIS stack:")
        print("    pip install geopandas pyogrio")
    return fence_before, fence_after, have_fence


# ---------------------------------------------------------------------------
# Figure rendering
# ---------------------------------------------------------------------------
def render_figure(deaths_subset, death_label, title, out_filename):
    """Build and save one figure. deaths_subset: DataFrame with Longitude/
    Latitude columns (already filtered to the desired date range).
    death_label: legend text before the "(n=...)" suffix, e.g.
    "Location of Remains 2000-2007". title: axes title. out_filename: PNG
    filename, saved next to this module."""
    fence_before, fence_after, have_fence = load_fence_layers()
    water = load_water_stations()

    # Longitude degrees are physically shorter than latitude degrees away
    # from the equator; correct for that (rather than a naive 'equal'
    # aspect) and size the figure to match, so there's no wasted whitespace.
    lat_mid = (BBOX["min_lat"] + BBOX["max_lat"]) / 2
    geo_aspect = 1 / math.cos(math.radians(lat_mid))
    lon_span = BBOX["max_lon"] - BBOX["min_lon"]
    lat_span = BBOX["max_lat"] - BBOX["min_lat"]
    fig_w = 12
    fig_h = fig_w * (lat_span * geo_aspect) / lon_span
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # Arizona state boundary -- faint gray, just for the CA/NM edges (the
    # south edge along Mexico is instead carried by the fence lines
    # themselves, with their real gaps, same as the original).
    plot_shapefile(
        ax, SHAPE_DIR / "tl_2021_us_state" / "tl_2021_us_state.shp",
        record_filter=lambda r: r["STATEFP"] == "04",
        closed=True, color="0.7", linewidth=0.7, zorder=1,
    )

    # Major roads/highways -- thin, unlabeled, no legend entry (context
    # only, same supporting role they play in the original).
    plot_shapefile(
        ax, SHAPE_DIR / "tl_2021_04_prisecroads" / "tl_2021_04_prisecroads.shp",
        record_filter=lambda r: r["RTTYP"] in ("I", "U", "S"),
        color="0.6", linewidth=0.5, zorder=1,
    )

    # Sonoran Desert boundary -- brown dashed. The USGS survey splits it
    # into two named polygons (Colorado + Arizona portions); both are
    # needed to cover the Nogales-Sasabe-Sonoyta corridor.
    plot_shapefile(
        ax, SHAPE_DIR / "deserts_sw" / "deserts_sw.shp",
        record_filter=lambda r: r["NAME"] in ("Colorado Sonoran Desert", "Arizona Sonoran Desert"),
        closed=True, transform=utm11n_to_lonlat,
        color=DESERT_BROWN, linestyle=(0, (6, 2)), linewidth=1.6, zorder=3,
    )

    # Tohono O'odham Nation Reservation -- purple dashed
    plot_shapefile(
        ax, SHAPE_DIR / "tl_2021_us_aiannh" / "tl_2021_us_aiannh.shp",
        record_filter=lambda r: r["NAMELSAD"] == "Tohono O'odham Nation Reservation",
        closed=True, color=RESERVATION_PURPLE, linestyle=(0, (6, 2)), linewidth=1.3, zorder=3,
    )

    # Border fencing, both periods, if geopandas is available
    if have_fence:
        for gdf in fence_after:
            gdf.plot(ax=ax, color=FENCE_YELLOW, linewidth=2.4, zorder=4)
        for gdf in fence_before:
            gdf.plot(ax=ax, color=FENCE_BLUE, linewidth=2.4, zorder=4)

    # Migrant deaths
    ax.scatter(deaths_subset["Longitude"], deaths_subset["Latitude"], s=16,
               color=DEATH_GREEN, edgecolor="black", linewidth=0.3, zorder=5)

    # Water stations -- not part of the original figures; see
    # WATER_STATIONS_METHODOLOGY.md for source and positional uncertainty.
    ax.scatter(water["longitude"], water["latitude"], s=45, marker="^",
               color=WATER_STATION_COLOR, edgecolor="black", linewidth=0.4, zorder=5)

    # City labels (text only, no markers -- matches the original's style)
    for name, (lon, lat) in CITIES.items():
        ax.annotate(name, (lon, lat), textcoords="offset points", xytext=(4, 4), fontsize=8, zorder=6)

    # Scale bar and north arrow (bottom-left, as in the original)
    draw_scale_bar(ax, lon0=-115.05, lat0=31.05, at_latitude=32.0)
    draw_north_arrow(ax, lon=-114.9, lat=31.3)

    # Legend: boxed, ordered to match the original exactly. Fence entries
    # are only added if the layers actually loaded and drew something --
    # otherwise the legend would falsely claim fence lines are on the map
    # when they aren't.
    legend_handles = [
        Line2D([], [], marker="o", linestyle="", markerfacecolor=DEATH_GREEN,
               markeredgecolor="black", markeredgewidth=0.3, markersize=7,
               label=f"{death_label} (n={len(deaths_subset)})"),
        Line2D([], [], marker="^", linestyle="", markerfacecolor=WATER_STATION_COLOR,
               markeredgecolor="black", markeredgewidth=0.4, markersize=8,
               label=f"Water stations (~2019, n={len(water)}, ±~5mi)"),
    ]
    if have_fence:
        legend_handles.append(Line2D([], [], color=FENCE_YELLOW, linewidth=2.4, label="Border built 2008 or later"))
        legend_handles.append(Line2D([], [], color=FENCE_BLUE, linewidth=2.4, label="Border built 2007 or before"))
    legend_handles.append(Line2D([], [], color=DESERT_BROWN, linestyle=(0, (6, 2)), linewidth=1.6, label="Arizona Sonoran Desert"))
    legend_handles.append(Line2D([], [], color=RESERVATION_PURPLE, linestyle=(0, (6, 2)), linewidth=1.3, label="Tohono O'odham Nation Reservation"))
    legend = ax.legend(handles=legend_handles, loc="upper right", fontsize=8,
                        title="Legend", title_fontsize=11, frameon=True,
                        edgecolor="black", facecolor="white")
    legend.get_title().set_fontweight("bold")
    legend._legend_box.align = "left"

    # Clean cartographic frame: no ticks, no axis labels, no grid
    ax.set_xlim(BBOX["min_lon"], BBOX["max_lon"])
    ax.set_ylim(BBOX["min_lat"], BBOX["max_lat"])
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("black")
        spine.set_linewidth(1.0)
    ax.set_title(title)
    ax.set_aspect(geo_aspect)

    fence_status = "fence: ON" if have_fence else "fence: OFF (geopandas unavailable)"
    stamp = f"generated {datetime.datetime.now():%Y-%m-%d %H:%M:%S} -- {fence_status}"

    fig.tight_layout()
    out_path = FIGURES_DIR / out_filename
    fig.savefig(out_path, dpi=200)
    print(f"Saved plot to {out_path}")
    print(stamp)
    plt.show()
