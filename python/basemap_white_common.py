"""
Figure 1: Geographic Features of the Arizona-Mexico Border -- the original
paper's Figure 1, which this reproduction never rebuilt (the series here
started at Figure 2). Same reference layers as every other figure
(Arizona boundary, major roads, Sonoran Desert outline, Tohono O'odham
Nation Reservation, border fencing by period, city labels, scale bar,
north arrow, legend) on a plain white background -- no death points,
danger-index colors, or hot spots, matching the original's own role as a
geographic-orientation figure, not a results figure.
"""
import math

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

import basemap_common as bc
import hotspot_common as hc


def render_figure1(out_filename="figure1_reproduction.png",
                    title="Figure 1: Geographic Features of Arizona-Mexico Border"):
    fence_before, fence_after, have_fence = bc.load_fence_layers()

    bbox = bc.BBOX
    lat_mid = (bbox["min_lat"] + bbox["max_lat"]) / 2
    geo_aspect = 1 / math.cos(math.radians(lat_mid))
    lon_span = bbox["max_lon"] - bbox["min_lon"]
    lat_span = bbox["max_lat"] - bbox["min_lat"]
    fig_w = 12
    fig_h = fig_w * (lat_span * geo_aspect) / lon_span
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "tl_2021_us_state" / "tl_2021_us_state.shp",
        record_filter=lambda r: r["STATEFP"] == "04",
        closed=True, color="0.3", linewidth=0.9, zorder=2,
    )
    bc.plot_shapefile(
        ax, bc.SHAPE_DIR / "tl_2021_04_prisecroads" / "tl_2021_04_prisecroads.shp",
        record_filter=lambda r: r["RTTYP"] in ("I", "U", "S"),
        color="0.35", linewidth=0.5, zorder=2,
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

    if have_fence:
        for gdf in fence_after:
            gdf.plot(ax=ax, color=bc.FENCE_YELLOW, linewidth=2.4, zorder=4)
        for gdf in fence_before:
            gdf.plot(ax=ax, color=bc.FENCE_BLUE, linewidth=2.4, zorder=4)

    for name, (lon, lat) in bc.CITIES.items():
        ax.annotate(name, (lon, lat), textcoords="offset points", xytext=(4, 4), fontsize=8, zorder=6)

    bc.draw_scale_bar(ax, lon0=-115.05, lat0=31.05, at_latitude=32.0)
    bc.draw_north_arrow(ax, lon=-114.9, lat=31.3)

    legend_handles = []
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

    ax.set_xlim(bbox["min_lon"], bbox["max_lon"])
    ax.set_ylim(bbox["min_lat"], bbox["max_lat"])
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
