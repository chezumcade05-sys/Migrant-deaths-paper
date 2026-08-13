"""
basemap_common_annotated.py
===========================
WHAT THIS FILE IS:
    A shared library — it is never run directly. Every figure script
    (figure3.py, figure4.py, figure5.py, etc.) imports this file and uses
    the tools inside it. Think of it as the toolbox that all the figures draw
    from so they don't each have to repeat the same code.

WHAT IT PROVIDES:
    1. Fixed settings: file paths, colors, the study-area boundary
    2. Data-loading functions: read the death records, fence lines, water stations
    3. Map-drawing functions: draw the Arizona basemap, scale bar, north arrow
    4. The main render_figure() function that assembles a complete figure

HOW IT CONNECTS TO THE FIGURES:
    figure4.py does:
        import basemap_common as bc
        deaths = bc.load_deaths()           # load and classify all death records
        subset = deaths[deaths["is_pre_sfa"]]  # keep only pre-SFA deaths
        bc.render_figure(subset, ...)        # draw and save the map
    That's it — figure4.py itself is only ~20 lines. All the real work is here.
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


# =============================================================================
# SECTION 1: COLORS
# These hex color codes were sampled directly from the legend swatches in the
# paper's original Word document, so the reproduction matches the published
# figures exactly.
# =============================================================================
DEATH_GREEN = "#27e32c"       # color of the death-location dots
FENCE_BLUE = "#205aae"        # fence built 2007 or before
FENCE_YELLOW = "#ffe600"      # fence built 2008 or later (post Secure Fence Act)
DESERT_BROWN = "#82604f"      # Sonoran Desert boundary outline
RESERVATION_PURPLE = "#3d1a5b"  # Tohono O'odham Nation boundary outline
WATER_STATION_COLOR = "#00b7c3"  # water station triangles (not in the original paper)


# =============================================================================
# SECTION 2: FILE PATHS
# Python figures out the location of all data files relative to where THIS
# file lives on disk. REPO_ROOT is the folder that contains python/, data/,
# figures/, etc. All data paths are built from that anchor, so the code works
# regardless of where on your computer the repo was cloned.
# =============================================================================
REPO_ROOT = Path(__file__).resolve().parent.parent   # go up one level from python/
DATA_DIR = REPO_ROOT / "data"
FIGURES_DIR = REPO_ROOT / "figures"
DEATH_CSV = DATA_DIR / "Original death data.csv"
FENCE_GDB = DATA_DIR / "Original Fence data" / "01-ORIGINAL.gdb"
SHAPE_DIR = DATA_DIR / "Shape Files"
WATER_STATIONS_CSV = DATA_DIR / "Water Stations 2000-2019.csv"


# =============================================================================
# SECTION 3: STUDY-AREA BOUNDING BOX AND CITY COORDINATES
# BBOX defines the map extent — the rectangle covering southern Arizona that
# all figures zoom into. City coordinates are used for map labels only.
# =============================================================================
BBOX = {"min_lon": -115.2, "max_lon": -109.0, "min_lat": 30.8, "max_lat": 34.3}

FENCE_LAYERS = [
    "obp_baseline_ti_ped_fence_LIMIT_GOV_USE",    # pedestrian fence layer name in the GDB
    "obp_baseline_ti_veh_barrier_LIMIT_GOV_USE",  # vehicle barrier layer name in the GDB
]

CITIES = {
    "Phoenix": (-112.0740, 33.4484),
    "Tucson": (-110.9265, 32.2217),
    "Nogales": (-110.9370, 31.3379),
    "Sasabe": (-111.5410, 31.4890),
    "Sonoyta": (-112.8380, 31.8620),
}


# =============================================================================
# SECTION 4: GEOMETRY HELPER FUNCTIONS
# These handle the technical task of reading shapefile geometry and converting
# between coordinate systems. A shapefile is a standard GIS file format that
# stores geographic boundaries as lists of (longitude, latitude) points.
# =============================================================================

def plot_shapefile(ax, shp_path, record_filter=None, closed=False, transform=None,
                    **line_kwargs):
    """
    WHAT IT DOES:
        Reads a shapefile and draws each shape (state boundary, road, desert
        outline, etc.) as a line on the map.

    KEY PARAMETERS:
        ax            — the matplotlib map panel to draw on
        shp_path      — path to the .shp file
        record_filter — an optional function that returns True/False for each
                        shape record, so we can draw only Arizona (STATEFP=04)
                        out of a nationwide shapefile, for example
        closed        — if True, connect the last point back to the first
                        (needed for polygon outlines like state boundaries)
        transform     — a coordinate conversion function, needed for the desert
                        shapefile which uses UTM meters instead of degrees
    """
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
    """
    WHAT IT DOES:
        The Sonoran Desert shapefile stores coordinates in UTM Zone 11N —
        a projection that uses meters measured from a reference point, not
        degrees of latitude/longitude. This function converts those meter
        coordinates back to (longitude, latitude) degrees so the desert
        boundary can be plotted on the same map as everything else.
    """
    lat, lon = utm.to_latlon(x, y, 11, "N", strict=False)
    return lon, lat


def draw_scale_bar(ax, lon0, lat0, at_latitude, miles=(0, 15, 30, 60)):
    """
    WHAT IT DOES:
        Draws the alternating black-and-white distance scale bar at the
        bottom-left of each figure. The bar is calibrated for the correct
        ground distance at the map's latitude (longitude degrees are shorter
        at higher latitudes, so a raw degree is not a fixed number of miles).
    """
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
    """
    WHAT IT DOES:
        Draws a simple north arrow (an upward-pointing arrow with an "N" label)
        at the given position on the map.
    """
    ax.annotate("", xy=(lon, lat + size), xytext=(lon, lat),
                arrowprops=dict(arrowstyle="-|>", color="black", linewidth=1.2),
                zorder=10)
    ax.annotate("N", (lon, lat + size + 0.03), ha="center", va="bottom",
                fontsize=9, fontweight="bold", zorder=10)


def draw_cell_size_note(ax, cell_size_deg, lon, lat, reference_lat, fontsize=6.5):
    """
    WHAT IT DOES:
        Adds a small text note near the scale bar stating the grid cell size
        used in the hot-spot and danger-index analyses (0.044°, roughly 2.7
        miles square). This helps readers understand the resolution of the
        raster analysis.
    """
    miles_per_deg_lat = 69.17
    miles_per_deg_lon = 69.17 * abs(math.cos(math.radians(reference_lat)))
    h_mi = cell_size_deg * miles_per_deg_lat
    w_mi = cell_size_deg * miles_per_deg_lon
    label = f"Grid cell size: {cell_size_deg:g}° (≈{w_mi:.1f} × {h_mi:.1f} mi)"
    ax.annotate(label, (lon, lat), ha="left", va="top", fontsize=fontsize, zorder=10,
                bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.75))


# =============================================================================
# SECTION 5: DATA-LOADING FUNCTIONS
# These read the raw CSV and GDB files from disk and return them as Python
# data structures ready to work with.
# =============================================================================

def load_deaths():
    """
    WHAT IT DOES:
        Reads the death records CSV and applies the paper's pre/post-SFA
        classification rule (Section 4.2 of the paper).

    THE CLASSIFICATION RULE:
        Pre-SFA  = remains discovered 2000–2007
                   PLUS any 2008 case where the postmortem interval was
                   "> 6-8 months" — meaning the death occurred in 2007
                   but the remains weren't found until 2008
        Post-SFA = remains discovered 2008–2019, excluding the reclassified
                   2008 cases above

    OUTPUT:
        Returns the full deaths table with two new True/False columns added:
            is_pre_sfa   — True if this death counts as pre-SFA
            is_post_sfa  — True if this death counts as post-SFA
        The figure scripts then filter by these columns to get their subset.

    VALIDATION:
        The paper reports 1,215 pre-SFA and 1,826 post-SFA deaths (Table 4).
        This function reproduces those exact counts.
    """
    deaths = pd.read_csv(DEATH_CSV)
    deaths["Reporting Date"] = pd.to_datetime(deaths["Reporting Date"], errors="coerce")
    deaths["year"] = deaths["Reporting Date"].dt.year
    pmi = deaths["Post Mortem Interval"].str.strip()

    # Reclassify 2008 discoveries with a long postmortem interval as pre-SFA
    reclassified_2008 = (deaths["year"] == 2008) & (pmi == "> 6-8 months")

    deaths["is_pre_sfa"] = deaths["year"].between(2000, 2007) | reclassified_2008
    deaths["is_post_sfa"] = (deaths["year"].between(2008, 2019) & pmi.notna()
                              & ~reclassified_2008)
    return deaths


def _date_in_year(value):
    """
    WHAT IT DOES:
        Extracts a 4-digit year from the messy DATE_IN field in the fence
        geodatabase (e.g. '20070615' -> 2007, '2004* or before' -> 2004).
        The field is inconsistently formatted, so this pulls just the first
        4 digits using a regular expression.
    """
    if value is None:
        return None
    m = re.match(r"(\d{4})", str(value))
    return int(m.group(1)) if m else None


def load_water_stations():
    """
    WHAT IT DOES:
        Reads the Humane Borders water station coordinates from CSV.
        These coordinates were extracted from a publicly available Humane
        Borders poster (not surveyed directly) — see WATER_STATIONS_METHODOLOGY.md
        for details. Positional uncertainty is approximately ±5 miles.
    """
    return pd.read_csv(WATER_STATIONS_CSV)


def load_fence_layers():
    """
    WHAT IT DOES:
        Reads the CBP border fence geodatabase and returns the fence segments
        split into two groups:
            fence_before — segments installed 2007 or earlier (plotted blue)
            fence_after  — segments installed 2008 or later (plotted yellow)

    WHY IT'S WRAPPED IN TRY/EXCEPT:
        Reading a .gdb file requires geopandas and pyogrio. If those aren't
        installed, the fence lines simply won't appear on the map (the script
        still runs and produces a figure, just without fence overlay).

    OUTPUT:
        Returns (fence_before, fence_after, have_fence)
            fence_before / fence_after — lists of GeoDataFrames
            have_fence — True if geopandas loaded successfully, False if not
    """
    fence_before, fence_after = [], []
    have_fence = False
    try:
        import geopandas as gpd

        for layer in FENCE_LAYERS:
            gdf = gpd.read_file(FENCE_GDB, layer=layer)
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


# =============================================================================
# SECTION 6: MAIN FIGURE-RENDERING FUNCTION
# This is the function that actually builds and saves a complete map figure.
# All of figures 3, 4, and 5 call this with different death subsets.
#
# PIPELINE (in order):
#   1. Load fence lines and water stations
#   2. Set up the figure canvas with the correct geographic aspect ratio
#   3. Draw background layers: Arizona boundary, roads, desert, reservation
#   4. Draw fence lines (blue for pre-2008, yellow for post-2008)
#   5. Plot the death location dots
#   6. Plot water station triangles
#   7. Add city name labels
#   8. Add scale bar and north arrow
#   9. Build the legend
#  10. Save the PNG to the figures/ folder
# =============================================================================

def render_figure(deaths_subset, death_label, title, out_filename):
    """
    PARAMETERS:
        deaths_subset — DataFrame of death records already filtered to the
                        desired time period (e.g. only pre-SFA deaths)
        death_label   — text for the legend, e.g. "Location of Remains 2000-2007"
        title         — the figure title shown at the top
        out_filename  — filename for the saved PNG (goes into figures/)
    """
    fence_before, fence_after, have_fence = load_fence_layers()
    water = load_water_stations()

    # --- FIGURE SIZE CALCULATION ---
    # Longitude degrees are physically shorter than latitude degrees at
    # Arizona's latitude (~32°N). This corrects the aspect ratio so the map
    # isn't stretched horizontally.
    lat_mid = (BBOX["min_lat"] + BBOX["max_lat"]) / 2
    geo_aspect = 1 / math.cos(math.radians(lat_mid))
    lon_span = BBOX["max_lon"] - BBOX["min_lon"]
    lat_span = BBOX["max_lat"] - BBOX["min_lat"]
    fig_w = 12
    fig_h = fig_w * (lat_span * geo_aspect) / lon_span
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # --- LAYER 1: ARIZONA STATE BOUNDARY (faint gray outline) ---
    # record_filter selects only Arizona (FIPS state code "04") from the
    # nationwide state shapefile
    plot_shapefile(
        ax, SHAPE_DIR / "tl_2021_us_state" / "tl_2021_us_state.shp",
        record_filter=lambda r: r["STATEFP"] == "04",
        closed=True, color="0.7", linewidth=0.7, zorder=1,
    )

    # --- LAYER 2: MAJOR ROADS (thin gray lines, context only) ---
    # RTTYP codes: I = Interstate, U = US Highway, S = State Highway
    plot_shapefile(
        ax, SHAPE_DIR / "tl_2021_04_prisecroads" / "tl_2021_04_prisecroads.shp",
        record_filter=lambda r: r["RTTYP"] in ("I", "U", "S"),
        color="0.6", linewidth=0.5, zorder=1,
    )

    # --- LAYER 3: SONORAN DESERT BOUNDARY (brown dashed outline) ---
    # This shapefile is in UTM meter coordinates, so utm11n_to_lonlat converts
    # each point to degrees before plotting
    plot_shapefile(
        ax, SHAPE_DIR / "deserts_sw" / "deserts_sw.shp",
        record_filter=lambda r: r["NAME"] in ("Colorado Sonoran Desert", "Arizona Sonoran Desert"),
        closed=True, transform=utm11n_to_lonlat,
        color=DESERT_BROWN, linestyle=(0, (6, 2)), linewidth=1.6, zorder=3,
    )

    # --- LAYER 4: TOHONO O'ODHAM NATION RESERVATION BOUNDARY (purple dashed) ---
    plot_shapefile(
        ax, SHAPE_DIR / "tl_2021_us_aiannh" / "tl_2021_us_aiannh.shp",
        record_filter=lambda r: r["NAMELSAD"] == "Tohono O'odham Nation Reservation",
        closed=True, color=RESERVATION_PURPLE, linestyle=(0, (6, 2)), linewidth=1.3, zorder=3,
    )

    # --- LAYER 5: BORDER FENCE LINES ---
    # Post-2008 fence drawn first so pre-2008 (older) fence appears on top
    # where segments overlap
    if have_fence:
        for gdf in fence_after:
            gdf.plot(ax=ax, color=FENCE_YELLOW, linewidth=2.4, zorder=4)
        for gdf in fence_before:
            gdf.plot(ax=ax, color=FENCE_BLUE, linewidth=2.4, zorder=4)

    # --- LAYER 6: MIGRANT DEATH DOTS ---
    # s=16 is the dot size; edgecolor/linewidth adds a thin black outline
    ax.scatter(deaths_subset["Longitude"], deaths_subset["Latitude"], s=16,
               color=DEATH_GREEN, edgecolor="black", linewidth=0.3, zorder=5)

    # --- LAYER 7: WATER STATION TRIANGLES ---
    ax.scatter(water["longitude"], water["latitude"], s=45, marker="^",
               color=WATER_STATION_COLOR, edgecolor="black", linewidth=0.4, zorder=5)

    # --- LAYER 8: CITY NAME LABELS ---
    for name, (lon, lat) in CITIES.items():
        ax.annotate(name, (lon, lat), textcoords="offset points", xytext=(4, 4), fontsize=8, zorder=6)

    # --- LAYER 9: SCALE BAR AND NORTH ARROW ---
    draw_scale_bar(ax, lon0=-115.05, lat0=31.05, at_latitude=32.0)
    draw_north_arrow(ax, lon=-114.9, lat=31.3)

    # --- LEGEND ---
    # Built manually so it matches the original paper's ordering and style
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

    # --- MAP FRAME AND AXIS LIMITS ---
    ax.set_xlim(BBOX["min_lon"], BBOX["max_lon"])
    ax.set_ylim(BBOX["min_lat"], BBOX["max_lat"])
    ax.set_xticks([])     # no tick marks on the map edges
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("black")
        spine.set_linewidth(1.0)
    ax.set_title(title)
    ax.set_aspect(geo_aspect)

    fence_status = "fence: ON" if have_fence else "fence: OFF (geopandas unavailable)"
    stamp = f"generated {datetime.datetime.now():%Y-%m-%d %H:%M:%S} -- {fence_status}"

    # --- SAVE ---
    fig.tight_layout()
    out_path = FIGURES_DIR / out_filename
    fig.savefig(out_path, dpi=200)
    print(f"Saved plot to {out_path}")
    print(stamp)
    plt.show()
