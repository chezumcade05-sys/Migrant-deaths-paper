"""
Generates the two danger-index factor summary tables used in
docs/DANGER_INDEX_METHODOLOGY.md: (1) what each factor is, its data
source, and its direction of danger; (2) descriptive statistics across
the same 7,536 in-Arizona grid cells the figures are drawn from.

Not part of the figure-rendering pipeline -- a reporting utility, re-run
whenever the underlying environmental data changes so the tables in the
methodology doc don't drift out of sync with the actual numbers.

Writes docs/danger_index_factor_summary.csv (machine-readable) and prints
both tables as Markdown (paste directly into DANGER_INDEX_METHODOLOGY.md).

To run (from the repo root): .venv/bin/python python/summarize_danger_factors.py
"""

import os
import sys
import math
from pathlib import Path

_VENV_DIR = Path(__file__).resolve().parent.parent / ".venv"
_VENV_PYTHON = _VENV_DIR / "bin" / "python"
if _VENV_PYTHON.exists() and Path(sys.prefix).resolve() != _VENV_DIR.resolve():
    os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

import numpy as np
import shapefile
from shapely.geometry import Point, shape as shapely_shape
from shapely.prepared import prep

import basemap_common as bc
import hotspot_common as hc
import danger_index_common as dc

FACTOR_DEFINITIONS = [
    # name, data source, direction, method/resolution
    ("Ambient summer temperature", "PRISM Climate Group (July tmax, 2014-2023 average)",
     "Hotter = more dangerous", "4km raster, averaged to grid cell"),
    ("Distance to major city", "Straight-line distance to Phoenix or Tucson",
     "Farther = more dangerous", "Euclidean, degree-space"),
    ("Distance to major road", "Straight-line distance to nearest Interstate/US/State highway (TIGER/Line 2021)",
     "Farther = more dangerous", "Euclidean, degree-space"),
    ("Distance to water source", "Straight-line distance to nearest Humane Borders water station",
     "Farther = more dangerous", "Euclidean, degree-space"),
    ("Slope", "USGS 3DEP elevation, slope computed manually from raw elevation",
     "Steeper = more dangerous", "~10x-oversampled, block-averaged to grid cell"),
    ("Vegetation density (NDVI)", "USGS NAIP 4-band aerial imagery, (NIR-Red)/(NIR+Red)",
     "Denser = more dangerous (obstacle, not shade -- see Boyce et al. 2019)", "~1m native, block-averaged to grid cell"),
]


def in_arizona_mask(result):
    sf = shapefile.Reader(str(bc.SHAPE_DIR / "tl_2021_us_state" / "tl_2021_us_state.shp"))
    field_names = [f[0] for f in sf.fields[1:]]
    az_shape = None
    for sr in sf.iterShapeRecords():
        if dict(zip(field_names, sr.record))["STATEFP"] == "04":
            az_shape = shapely_shape(sr.shape.__geo_interface__)
            break
    az_prepared = prep(az_shape)
    return np.array([az_prepared.contains(Point(lo, la)) for lo, la in zip(result["lon"], result["lat"])])


def main():
    result = dc.compute_danger_index()
    in_az = in_arizona_mask(result)
    keep = in_az & ~np.isnan(result["composite"])
    n = int(keep.sum())

    lat_mid = (bc.BBOX["min_lat"] + bc.BBOX["max_lat"]) / 2
    miles_per_deg = (69.17 + 69.17 * math.cos(math.radians(lat_mid))) / 2

    stat_rows = [
        ("Ambient summer temperature", result["july_tmax_c"][keep], "C", 1),
        ("Distance to major city", result["dist_city_deg"][keep] * miles_per_deg, "mi", 1),
        ("Distance to major road", result["dist_road_deg"][keep] * miles_per_deg, "mi", 1),
        ("Distance to water source", result["dist_water_deg"][keep] * miles_per_deg, "mi", 1),
        ("Slope", result["slope_deg"][keep], "deg", 2),
        ("Vegetation density (NDVI)", result["ndvi"][keep], "(unitless)", 3),
    ]

    print(f"\n## Table 1: Danger index factors\n")
    print("| Factor | Data source | Direction | Method |")
    print("|---|---|---|---|")
    for name, source, direction, method in FACTOR_DEFINITIONS:
        print(f"| {name} | {source} | {direction} | {method} |")

    print(f"\n## Table 2: Descriptive statistics (n={n} grid cells within Arizona)\n")
    print("| Factor | Min | Mean | Max | Std dev | Unit |")
    print("|---|---|---|---|---|---|")
    csv_lines = ["factor,min,mean,max,std_dev,unit,n"]
    for name, vals, unit, dp in stat_rows:
        lo, mean, hi = np.min(vals), np.mean(vals), np.max(vals)
        sd = np.std(vals, ddof=1)
        print(f"| {name} | {lo:.{dp}f} | {mean:.{dp}f} | {hi:.{dp}f} | {sd:.{dp}f} | {unit or '—'} |")
        csv_lines.append(f'"{name}",{lo:.{dp}f},{mean:.{dp}f},{hi:.{dp}f},{sd:.{dp}f},{unit},{n}')

    out_path = bc.REPO_ROOT / "docs" / "danger_index_factor_summary.csv"
    out_path.write_text("\n".join(csv_lines) + "\n")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
