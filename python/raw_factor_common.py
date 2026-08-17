"""
Raw-data raster figure: the slope, temperature, and vegetation-density
(NDVI, i.e. "foliage cover") grids exactly as pulled into
"Danger Index Environmental Layers.csv", rendered as true rasters
(imshow, not per-cell Rectangle patches) rather than run through the
danger index's Z-scoring/summing. This is meant to be *descriptive* --
showing how these three inputs are actually distributed across the study
area -- not analytical like Figure 2's composite danger index.

Same grid (basemap_common.BBOX, hotspot_common.CELL_SIZE), same reference
layers (Arizona boundary, roads, Sonoran Desert outline, Tohono O'odham
Nation Reservation, scale bar, north arrow, cell-size note) as the rest of
this reproduction, stacked as three panels the same way Figure 8 stacks
its pre-/post-SFA panels.
"""
import math

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import basemap_common as bc
import hotspot_common as hc

ENV_CSV = bc.DATA_DIR / "Danger Index Environmental Layers.csv"


def _az_mask(lons, lats):
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


def _pivot_grid(df, value_col, in_az):
    n_rows = int(df["row"].max()) + 1
    n_cols = int(df["col"].max()) + 1
    grid = np.full((n_rows, n_cols), np.nan)
    vals = df[value_col].values.copy()
    vals[~in_az] = np.nan
    grid[df["row"].values, df["col"].values] = vals
    return grid


def render_raw_factor_rasters(out_filename="figure_raw_factors.png"):
    df = pd.read_csv(ENV_CSV)
    in_az = _az_mask(df["longitude"].values, df["latitude"].values)

    slope_grid = _pivot_grid(df, "slope_deg", in_az)
    temp_grid = _pivot_grid(df, "july_tmax_c", in_az)
    ndvi_grid = _pivot_grid(df, "ndvi", in_az)

    bbox = bc.BBOX
    lat_mid = (bbox["min_lat"] + bbox["max_lat"]) / 2
    geo_aspect = 1 / math.cos(math.radians(lat_mid))
    lon_span = bbox["max_lon"] - bbox["min_lon"]
    lat_span = bbox["max_lat"] - bbox["min_lat"]
    fig_w = 12
    panel_h = fig_w * (lat_span * geo_aspect) / lon_span
    fig_h = panel_h * 3
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = fig.add_gridspec(3, 1, height_ratios=[panel_h, panel_h, panel_h], hspace=0.12,
                           top=0.98, bottom=0.02, left=0.02, right=0.98)
    ax_slope = fig.add_subplot(gs[0])
    ax_temp = fig.add_subplot(gs[1])
    ax_ndvi = fig.add_subplot(gs[2])

    def draw_panel(ax, grid, cmap, vmin, vmax, title, cbar_label):
        im = ax.imshow(grid, extent=(bbox["min_lon"], bbox["max_lon"], bbox["min_lat"], bbox["max_lat"]),
                        origin="lower", cmap=cmap, vmin=vmin, vmax=vmax, zorder=1, interpolation="nearest")

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
        for name, (lon, lat) in bc.CITIES.items():
            ax.annotate(name, (lon, lat), textcoords="offset points", xytext=(4, 4), fontsize=8, zorder=8)

        bc.draw_scale_bar(ax, lon0=-115.05, lat0=31.05, at_latitude=32.0)
        bc.draw_north_arrow(ax, lon=-114.9, lat=31.3)
        bc.draw_cell_size_note(ax, hc.CELL_SIZE, lon=-115.05, lat=30.95, reference_lat=lat_mid)

        ax.set_xlim(bbox["min_lon"], bbox["max_lon"])
        ax.set_ylim(bbox["min_lat"], bbox["max_lat"])
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color("black")
            spine.set_linewidth(1.0)
        ax.set_title(title, fontsize=11)
        ax.set_aspect(geo_aspect)

        cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
        cbar.set_label(cbar_label, fontsize=8)
        cbar.ax.tick_params(labelsize=7)

    draw_panel(ax_slope, slope_grid, "YlOrBr", np.nanmin(slope_grid), np.nanmax(slope_grid),
               "Figure 10a: Slope (raw grid, not Z-scored)", "Slope (degrees)")
    draw_panel(ax_temp, temp_grid, "YlOrRd", np.nanmin(temp_grid), np.nanmax(temp_grid),
               "Figure 10b: Temperature, July Max (raw grid, not Z-scored)", "°C")
    draw_panel(ax_ndvi, ndvi_grid, "Greens", np.nanmin(ndvi_grid), np.nanmax(ndvi_grid),
               "Figure 10c: Vegetation Density / Foliage Cover (raw grid, not Z-scored)", "NDVI")

    out_path = bc.FIGURES_DIR / out_filename
    fig.savefig(out_path, dpi=200)
    print(f"Saved plot to {out_path}")
    plt.show()
