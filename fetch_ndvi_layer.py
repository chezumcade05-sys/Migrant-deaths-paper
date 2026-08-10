"""
One-off data-acquisition script: adds an "ndvi" column to
"Danger Index Environmental Layers.csv" for the danger index's 6th
factor -- vegetation density, following the exact formula used by Boyce,
Chambers & Launius (2019), "Bodily Inertia and the Weaponization of the
Sonoran Desert in US Boundary Enforcement" (their "ruggedness index"),
which a peer reviewer pointed to as precedent for including a
vegetation/"shade" factor in a migrant-crossing danger index:

    NDVI = (NIR - Red) / (NIR + Red)

That paper treats denser vegetation as MORE dangerous, not as protective
shade -- dense vegetation slows travel, disorients, and increases
exertion. This reproduction keeps that same direction; see
DANGER_INDEX_METHODOLOGY.md for the full writeup and citation.

Data source: USGS National Map's 4-band NAIP aerial imagery (Red, Green,
Blue, Near-Infrared) -- see REFERENCES.md. Queried via the same USGS
ImageServer REST pattern already used here for elevation/slope: an
unauthenticated /exportImage call, no GDAL/rasterio needed, decoded with
Pillow (already a project dependency via matplotlib).

Run this once (or re-run to refresh) to (re)generate the "ndvi" column.
Safe to re-run: it recomputes that column and merges it into the existing
CSV by (row, col), leaving slope_deg/july_tmax_c untouched.

    .venv/bin/python fetch_ndvi_layer.py
"""

import io
import os
import sys
import urllib.request
from pathlib import Path

_VENV_DIR = Path(__file__).resolve().parent / ".venv"
_VENV_PYTHON = _VENV_DIR / "bin" / "python"
if _VENV_PYTHON.exists() and Path(sys.prefix).resolve() != _VENV_DIR.resolve():
    os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

import numpy as np
import pandas as pd
from PIL import Image

import basemap_common as bc
import hotspot_common as hc

ENV_CSV = bc.DATA_DIR / "Danger Index Environmental Layers.csv"

NAIP_IMAGESERVER = (
    "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer/exportImage"
)

# Sub-grid oversampling factor, matching the same approach used for slope
# (danger_index_common's elevation pull): request the raster 10x finer
# than the target grid in each dimension, then block-average down, rather
# than asking the server to resample directly to the coarse grid.
OVERSAMPLE = 10


def _fetch_naip_bands(bbox, size):
    """Returns (red, nir) arrays, each shape (height, width), float."""
    w, h = size
    params = {
        "bbox": f"{bbox['min_lon']},{bbox['min_lat']},{bbox['max_lon']},{bbox['max_lat']}",
        "bboxSR": 4326, "imageSR": 4326,
        "size": f"{w},{h}",
        "format": "tiff", "pixelType": "U8",
        # Nearest-neighbor, not bilinear: bilinear blends real pixels with
        # neighboring nodata pixels right at the edge of NAIP's coverage
        # (e.g. the south edge of the study area, near the border), which
        # produced a handful of spurious near -1/+1 NDVI values that
        # weren't caught by the red==0-and-nir==0 nodata check. Nearest
        # neighbor never mixes a real pixel with a nodata one.
        "interpolation": "RSP_NearestNeighbor",
        "f": "image",
    }
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(f"{NAIP_IMAGESERVER}?{qs}", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        body = r.read()
    arr = np.array(Image.open(io.BytesIO(body))).astype(float)
    # This mosaic's band order is 1=Red, 2=Green, 3=Blue, 4=NIR -- confirmed
    # against the ImageServer's own documented raster functions
    # (NaturalColor = bands "1,2,3"; FalseColorComposite = bands "4,1,2",
    # i.e. NIR,Red,Green). Pillow decodes the 4-plane TIFF as RGBA purely
    # by band count; plane 0 is still raw band-1 (Red) data and plane 3 is
    # raw band-4 (NIR) data, not a real alpha channel.
    red, nir = arr[:, :, 0], arr[:, :, 3]
    return red, nir


def compute_ndvi_grid():
    bbox = bc.BBOX
    cell_size = hc.CELL_SIZE
    n_cols = int(round((bbox["max_lon"] - bbox["min_lon"]) / cell_size))
    n_rows = int(round((bbox["max_lat"] - bbox["min_lat"]) / cell_size))
    w, h = n_cols * OVERSAMPLE, n_rows * OVERSAMPLE

    print(f"Requesting {w}x{h} NAIP raster (Red + NIR bands) over the full study area...")
    red, nir = _fetch_naip_bands(bbox, (w, h))

    # Pixels outside NAIP's coverage (e.g. over Mexico, south of the study
    # area) are mostly exact (0, 0), but the fringe right at the coverage
    # boundary has a thin band of near-zero noise pixels too (observed:
    # red=1, nir=0), which would otherwise compute as a spurious exact
    # NDVI of -1. A small combined-signal floor catches both: real desert
    # reflectance is comfortably above this (bare soil is typically
    # 80-150+ combined), so this doesn't discard genuine low-vegetation
    # cells, just the boundary noise.
    nodata = (red + nir) < 10
    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = (nir - red) / (nir + red)
    ndvi[nodata] = np.nan

    # Bin every fine pixel into its target grid cell by lon/lat, using the
    # exact same cell-center convention as the rest of the grid:
    # origin + (idx + 0.5) * cell_size (see hotspot_common.compute_gi_star).
    py, px = np.indices((h, w))
    lon = bbox["min_lon"] + (px + 0.5) / w * (bbox["max_lon"] - bbox["min_lon"])
    lat = bbox["max_lat"] - (py + 0.5) / h * (bbox["max_lat"] - bbox["min_lat"])
    col = np.clip(((lon - bbox["min_lon"]) / cell_size).astype(int), 0, n_cols - 1)
    row = np.clip(((lat - bbox["min_lat"]) / cell_size).astype(int), 0, n_rows - 1)

    sums = np.zeros((n_rows, n_cols))
    counts = np.zeros((n_rows, n_cols))
    valid = ~np.isnan(ndvi)
    np.add.at(sums, (row[valid], col[valid]), ndvi[valid])
    np.add.at(counts, (row[valid], col[valid]), 1)

    # Cells straddling the actual edge of NAIP's coverage (mostly the
    # southern border, where the mosaic's real footprint doesn't line up
    # exactly with the study bbox) can end up averaging just a handful of
    # the OVERSAMPLE**2=100 sub-pixels -- e.g. a cell with only 3 or 4
    # valid pixels produced wildly unstable, unrepresentative averages
    # (observed NDVI values near +/-1, versus a realistic desert range of
    # roughly -0.1 to 0.4). Requiring at least half the sub-pixels keeps
    # every well-covered cell (interior cells all have ~100) while
    # dropping the noisy fringe.
    min_valid = (OVERSAMPLE ** 2) // 2
    with np.errstate(invalid="ignore"):
        grid_ndvi = np.where(counts >= min_valid, sums / counts, np.nan)
    n_missing = np.isnan(grid_ndvi).sum()
    print(f"NDVI grid: {n_rows}x{n_cols} cells, {n_missing} with <{min_valid}/{OVERSAMPLE**2} "
          f"valid NAIP sub-pixels (excluded)")
    return grid_ndvi


def main():
    grid_ndvi = compute_ndvi_grid()
    df = pd.read_csv(ENV_CSV)
    df["ndvi"] = [grid_ndvi[int(r), int(c)] for r, c in zip(df["row"], df["col"])]
    df.to_csv(ENV_CSV, index=False)
    print(f"Wrote 'ndvi' column to {ENV_CSV}")
    print(df["ndvi"].describe())


if __name__ == "__main__":
    main()
