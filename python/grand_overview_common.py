"""
Figure 1: 2x2 grand overview panel -- basemap, vegetation density (NDVI),
temperature, and slope -- the plain reference layer plus three of the
danger index's six raw (not Z-scored) inputs, side by side for a single
at-a-glance view. Reuses the exact same grid/masking helpers as
raw_factor_common.py (same underlying data, same AZ mask).

Sized and set in Times New Roman (12pt for the legend/reference text that
a reader actually reads at length; titles and axis chrome scaled up/down
from that base for a normal print hierarchy) at final print dimensions --
6.5in wide, matching a standard Word page's content width at 1in margins
-- so inserting the saved PNG at 6.5in in Word reproduces these exact
point sizes, not a scaled-down approximation. The legend, scale bar,
north arrow, and cell-size note all live inside the basemap panel itself
(upper-right and lower-left corners, same convention as the original
paper's own Figure 1), not in a separate strip.
"""
import math

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import basemap_common as bc
import hotspot_common as hc
from raw_factor_common import ENV_CSV, _az_mask, _pivot_grid

BODY_PT = 12
FONT = "Times New Roman"


def _draw_reference_layers(ax, linewidth_scale=1.0):
    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "tl_2021_us_state" / "tl_2021_us_state.shp",
        record_filter=lambda r: r["STATEFP"] == "04",
        closed=True, color="0.3", linewidth=0.8 * linewidth_scale, zorder=6,
    )
    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "tl_2021_04_prisecroads" / "tl_2021_04_prisecroads.shp",
        record_filter=lambda r: r["RTTYP"] in ("I", "U", "S"),
        color="0.35", linewidth=0.4 * linewidth_scale, zorder=6,
    )
    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "deserts_sw" / "deserts_sw.shp",
        record_filter=lambda r: r["NAME"] in ("Colorado Sonoran Desert", "Arizona Sonoran Desert"),
        closed=True, transform=bc.utm11n_to_lonlat,
        color=bc.DESERT_BROWN, linestyle=(0, (6, 2)), linewidth=1.2 * linewidth_scale, zorder=6,
    )
    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "tl_2021_us_aiannh" / "tl_2021_us_aiannh.shp",
        record_filter=lambda r: r["NAMELSAD"] == "Tohono O'odham Nation Reservation",
        closed=True, color=bc.RESERVATION_PURPLE, linestyle=(0, (6, 2)), linewidth=1.0 * linewidth_scale, zorder=6,
    )


def render_grand_overview(out_filename="figure1_grand_overview.png"):
    plt.rcParams["font.family"] = FONT
    plt.rcParams["font.size"] = BODY_PT

    df = pd.read_csv(ENV_CSV)
    in_az = _az_mask(df["longitude"].values, df["latitude"].values)
    ndvi_grid = _pivot_grid(df, "ndvi", in_az)
    temp_grid = _pivot_grid(df, "july_tmax_c", in_az)
    slope_grid = _pivot_grid(df, "slope_deg", in_az)
    water = bc.load_water_stations()

    bbox = bc.BBOX
    lat_mid = (bbox["min_lat"] + bbox["max_lat"]) / 2
    geo_aspect = 1 / math.cos(math.radians(lat_mid))
    lon_span = bbox["max_lon"] - bbox["min_lon"]
    lat_span = bbox["max_lat"] - bbox["min_lat"]

    # Final print size: 6.5in wide total -- a standard Word page's content
    # width at 1in margins -- so a 12pt font here really is 12pt once
    # inserted at that width, not shrunk from a larger working canvas.
    fig_w = 6.5
    col_gap = 0.15
    panel_w = (fig_w - col_gap) / 2
    panel_h = panel_w * (lat_span * geo_aspect) / lon_span
    title_h = 0.32
    fig_h = panel_h * 2 + title_h
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=300)
    gs = fig.add_gridspec(2, 4, hspace=0.1, wspace=0.06,
                           width_ratios=[1, 0.07, 1, 0.07],
                           top=1 - title_h / fig_h, bottom=0.02, left=0.03, right=0.97)

    ax_white = fig.add_subplot(gs[0, 0])
    ax_ndvi = fig.add_subplot(gs[0, 2])
    cax_ndvi = fig.add_subplot(gs[0, 3])
    ax_temp = fig.add_subplot(gs[1, 0])
    cax_temp = fig.add_subplot(gs[1, 1])
    ax_slope = fig.add_subplot(gs[1, 2])
    cax_slope = fig.add_subplot(gs[1, 3])
    fig.delaxes(fig.add_subplot(gs[0, 1]))  # unused column next to basemap

    def base_panel_setup(ax, title):
        _draw_reference_layers(ax)
        for name, (lon, lat) in bc.CITIES.items():
            ax.annotate(name, (lon, lat), textcoords="offset points", xytext=(2, 2),
                        fontsize=6.5, fontfamily=FONT, zorder=8)
        ax.set_xlim(bbox["min_lon"], bbox["max_lon"])
        ax.set_ylim(bbox["min_lat"], bbox["max_lat"])
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color("black")
            spine.set_linewidth(0.7)
        ax.set_title(title, fontsize=10, fontweight="bold", fontfamily=FONT, pad=3)
        ax.set_aspect(geo_aspect, adjustable="box")

    base_panel_setup(ax_white, "Basemap")
    ax_white.scatter(water["longitude"], water["latitude"], s=12, marker="^",
                      color=bc.WATER_STATION_COLOR, edgecolor="black", linewidth=0.3, zorder=7)
    bc.draw_scale_bar(ax_white, lon0=-115.05, lat0=31.15, at_latitude=32.0)
    bc.draw_north_arrow(ax_white, lon=-114.85, lat=31.42, size=0.14)

    legend_handles = [
        Line2D([], [], color="0.3", linewidth=0.8, label="State boundary"),
        Line2D([], [], color="0.35", linewidth=0.4, label="Major roads"),
        Line2D([], [], color=bc.DESERT_BROWN, linestyle=(0, (6, 2)), linewidth=1.2, label="Sonoran Desert"),
        Line2D([], [], color=bc.RESERVATION_PURPLE, linestyle=(0, (6, 2)), linewidth=1.0, label="TON Reservation"),
        Line2D([], [], marker="^", linestyle="", markerfacecolor=bc.WATER_STATION_COLOR,
               markeredgecolor="black", markeredgewidth=0.3, markersize=5,
               label="Water stations"),
    ]
    legend = ax_white.legend(handles=legend_handles, loc="upper right", fontsize=5.2,
                              frameon=True, edgecolor="black", facecolor="white", framealpha=0.97,
                              handlelength=1.0, labelspacing=0.25, borderpad=0.35, handletextpad=0.5,
                              title="Legend", title_fontsize=6)
    legend.get_title().set_fontfamily(FONT)
    legend.get_title().set_fontweight("bold")
    for text in legend.get_texts():
        text.set_fontfamily(FONT)
    legend.set_zorder(10)

    def data_panel(ax, cax, grid, cmap, title, cbar_label, cbar_side="right"):
        im = ax.imshow(grid, extent=(bbox["min_lon"], bbox["max_lon"], bbox["min_lat"], bbox["max_lat"]),
                        origin="lower", cmap=cmap, vmin=np.nanmin(grid), vmax=np.nanmax(grid),
                        zorder=1, interpolation="nearest")
        base_panel_setup(ax, title)
        cbar = fig.colorbar(im, cax=cax, format="%.2g")
        # figure-interior colorbars (temperature, sandwiched between two
        # map panels) need their ticks on the *inner* side -- toward their
        # own map, not toward the neighboring panel -- or the tick labels
        # get clipped by that neighbor's axis right next door.
        if cbar_side == "left":
            cbar.ax.yaxis.set_ticks_position("left")
            cbar.ax.yaxis.set_label_position("left")
        cbar.set_label(cbar_label, fontsize=7, fontfamily=FONT, labelpad=2)
        cbar.ax.tick_params(labelsize=6, pad=1)
        for t in cbar.ax.get_yticklabels():
            t.set_fontfamily(FONT)
        # Cell-size note only on the three raster panels -- they're the
        # ones actually gridded at this cell size, unlike the basemap.
        bc.draw_cell_size_note(ax, hc.CELL_SIZE, lon=-115.05, lat=31.0, reference_lat=lat_mid, fontsize=5.5)

    data_panel(ax_ndvi, cax_ndvi, ndvi_grid, "Greens", "Vegetation Density (NDVI)", "NDVI")
    data_panel(ax_temp, cax_temp, temp_grid, "YlOrRd", "Temperature (July Max, °C)", "°C", cbar_side="left")
    data_panel(ax_slope, cax_slope, slope_grid, "YlOrBr", "Slope", "Degrees")

    fig.suptitle("Figure 1: Basemap, Vegetation Density, Temperature, and Slope",
                 fontsize=15, fontweight="bold", fontfamily=FONT, y=0.998)

    out_path = bc.FIGURES_DIR / out_filename
    fig.savefig(out_path, dpi=300)
    print(f"Saved plot to {out_path}")
