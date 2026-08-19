"""
VESTIGIAL: only figure_topography.py (itself vestigial) imports this.
Never committed/used in any delivered figure set. Kept for reference only.

Topography basemap, styled to match the rest of this reproduction's
figures (basemap_common.render_figure) -- same reference layers (Arizona
boundary, major roads, Sonoran Desert outline, Tohono O'odham Nation
Reservation, scale bar, north arrow, black frame), same bounding box
(basemap_common.BBOX), just with a light grayscale terrain background in
place of blank white, and no death points / water stations / fencing /
danger-index colors / legend.

Data source: USGS 3DEP Elevation ImageServer, using its own
"Hillshade Gray-Stretch" server-side rendering function (plain grayscale
relief, not the elevation color ramp), via the same unauthenticated
/exportImage REST pattern already used in fetch_ndvi_layer.py -- no
GDAL/rasterio needed, decoded with Pillow.
"""

import io
import json
import math
import urllib.parse
import urllib.request

import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

import basemap_common as bc

TOPO_IMAGESERVER = (
    "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
)


def _fetch_hillshade(bbox, size):
    w, h = size
    params = {
        "bbox": f"{bbox['min_lon']},{bbox['min_lat']},{bbox['max_lon']},{bbox['max_lat']}",
        "bboxSR": 4326, "imageSR": 4326,
        "size": f"{w},{h}",
        "format": "png",
        "renderingRule": json.dumps({"rasterFunction": "Hillshade Gray-Stretch"}),
        "f": "image",
    }
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(f"{TOPO_IMAGESERVER}?{qs}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        body = r.read()
    return np.array(Image.open(io.BytesIO(body)))


def render_topography_basemap(out_filename, title=None):
    bbox = bc.BBOX
    lat_mid = (bbox["min_lat"] + bbox["max_lat"]) / 2
    geo_aspect = 1 / math.cos(math.radians(lat_mid))
    lon_span = bbox["max_lon"] - bbox["min_lon"]
    lat_span = bbox["max_lat"] - bbox["min_lat"]

    w = 2400
    h = int(round(w * lat_span / lon_span))
    print(f"Requesting {w}x{h} grayscale hillshade over the full study area...")
    img = _fetch_hillshade(bbox, (w, h))

    fig_w = 12
    fig_h = fig_w * (lat_span * geo_aspect) / lon_span
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    # Terrain background -- light grayscale, sits below everything else.
    # Alpha < 1 lightens it further so the black reference lines/labels
    # drawn on top (same convention as every other figure) stay legible,
    # the same way a printed topo map screens its relief shading back.
    ax.imshow(img, extent=(bbox["min_lon"], bbox["max_lon"], bbox["min_lat"], bbox["max_lat"]),
              origin="upper", zorder=0, alpha=0.75)

    # From here down: identical reference layers to
    # basemap_common.render_figure(), same colors/widths/zorder, just
    # without the death points, water stations, fence lines, or legend.
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

    for name, (lon, lat) in bc.CITIES.items():
        ax.annotate(name, (lon, lat), textcoords="offset points", xytext=(4, 4), fontsize=8, zorder=6)

    bc.draw_scale_bar(ax, lon0=-115.05, lat0=31.05, at_latitude=32.0)
    bc.draw_north_arrow(ax, lon=-114.9, lat=31.3)

    ax.set_xlim(bbox["min_lon"], bbox["max_lon"])
    ax.set_ylim(bbox["min_lat"], bbox["max_lat"])
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("black")
        spine.set_linewidth(1.0)
    if title:
        ax.set_title(title)
    ax.set_aspect(geo_aspect)

    fig.tight_layout()
    out_path = bc.FIGURES_DIR / out_filename
    fig.savefig(out_path, dpi=200)
    print(f"Saved plot to {out_path}")
    plt.show()
