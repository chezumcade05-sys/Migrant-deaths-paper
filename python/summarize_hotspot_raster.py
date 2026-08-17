"""
Generates the two hot-spot/raster summary tables referenced from
docs/DANGER_INDEX_METHODOLOGY.md and Claude Hotspot documentation.md:
(1) the Getis-Ord Gi* hot-spot analysis results for all three periods
(pre-SFA, post-SFA, all years combined), and (2) the shared raster grid's
specifications (cell size, extent, and how the sparse hot-spot grids
relate to the full bbox-wide danger-index grid).

Not part of the figure-rendering pipeline -- a reporting utility, re-run
whenever the underlying death data or grid parameters change so these
tables don't drift out of sync with the actual numbers.

Writes docs/hotspot_raster_summary.csv (machine-readable) and prints both
tables as Markdown.

To run (from the repo root): .venv/bin/python python/summarize_hotspot_raster.py
"""

import os
import sys
import math
from pathlib import Path
from collections import Counter

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


def hotspot_summary_rows():
    """One row per period: n deaths, populated grid cells, calibrated
    distance band, avg neighbors, and the Gi_Bin distribution. Matches
    exactly what figure6.py/figure7.py/figure9_hotspot.py each print --
    computed the same way (same filters), not read from a stale record."""
    deaths = bc.load_deaths()
    periods = [
        ("Pre-SFA (2000-2007)", deaths[deaths["is_pre_sfa"]]),
        ("Post-SFA (2008-2019)", deaths[deaths["is_post_sfa"]]),
        ("All years (2000-2019)", deaths[deaths["is_pre_sfa"] | deaths["is_post_sfa"]]),
    ]
    lat_mid = (bc.BBOX["min_lat"] + bc.BBOX["max_lat"]) / 2
    miles_per_deg = (69.17 + 69.17 * abs(math.cos(math.radians(lat_mid)))) / 2

    rows = []
    for label, subset in periods:
        counts = hc.build_grid_counts(subset["Longitude"], subset["Latitude"],
                                       hc.CELL_SIZE, bc.BBOX["min_lon"], bc.BBOX["min_lat"])
        result = hc.compute_gi_star(counts, hc.CELL_SIZE, bc.BBOX["min_lon"], bc.BBOX["min_lat"])
        gi = Counter(result["gi_bin"])
        rows.append({
            "period": label,
            "n_deaths": len(subset),
            "n_cells": result["n_cells"],
            "distance_band_deg": result["distance_band_deg"],
            "distance_band_mi": result["distance_band_deg"] * miles_per_deg,
            "avg_neighbors": result["avg_neighbors"],
            "hot_99": gi.get(3, 0), "hot_95": gi.get(2, 0), "hot_90": gi.get(1, 0),
            "not_sig": gi.get(0, 0),
            "cold_90": gi.get(-1, 0), "cold_95": gi.get(-2, 0), "cold_99": gi.get(-3, 0),
        })
    return rows


def raster_spec():
    lat_mid = (bc.BBOX["min_lat"] + bc.BBOX["max_lat"]) / 2
    miles_per_deg_lat = 69.17
    miles_per_deg_lon = 69.17 * abs(math.cos(math.radians(lat_mid)))

    result = dc.compute_danger_index()
    sf = shapefile.Reader(str(bc.SHAPE_DIR / "tl_2021_us_state" / "tl_2021_us_state.shp"))
    field_names = [f[0] for f in sf.fields[1:]]
    az_shape = None
    for sr in sf.iterShapeRecords():
        if dict(zip(field_names, sr.record))["STATEFP"] == "04":
            az_shape = shapely_shape(sr.shape.__geo_interface__)
            break
    az_prepared = prep(az_shape)
    in_az = np.array([az_prepared.contains(Point(lo, la)) for lo, la in zip(result["lon"], result["lat"])])
    keep = in_az & ~np.isnan(result["composite"])

    return {
        "cell_size_deg": hc.CELL_SIZE,
        "cell_w_mi": hc.CELL_SIZE * miles_per_deg_lon,
        "cell_h_mi": hc.CELL_SIZE * miles_per_deg_lat,
        "bbox_lon_span_mi": (bc.BBOX["max_lon"] - bc.BBOX["min_lon"]) * miles_per_deg_lon,
        "bbox_lat_span_mi": (bc.BBOX["max_lat"] - bc.BBOX["min_lat"]) * miles_per_deg_lat,
        "n_rows": result["n_rows"], "n_cols": result["n_cols"],
        "n_cells_total": result["n_rows"] * result["n_cols"],
        "n_cells_valid_bboxwide": int((~np.isnan(result["composite"])).sum()),
        "n_cells_in_az": int(keep.sum()),
    }


def main():
    hs_rows = hotspot_summary_rows()
    spec = raster_spec()

    print("\n## Table: Hot-spot analysis summary\n")
    print("| Period | N deaths | N grid cells | Distance band | Avg. neighbors | Hot 99% | Hot 95% | Hot 90% | Not sig. |")
    print("|---|---|---|---|---|---|---|---|---|")
    for r in hs_rows:
        print(f"| {r['period']} | {r['n_deaths']} | {r['n_cells']} | "
              f"{r['distance_band_deg']:.4f}° (~{r['distance_band_mi']:.1f} mi) | {r['avg_neighbors']:.1f} | "
              f"{r['hot_99']} | {r['hot_95']} | {r['hot_90']} | {r['not_sig']} |")
    print("\n(Cold-spot tiers -90/-95/-99% omitted: 0 cells in every period.)")

    print("\n## Table: Raster grid specification\n")
    print(f"| Property | Value |")
    print(f"|---|---|")
    print(f"| Cell size | {spec['cell_size_deg']}° (~{spec['cell_w_mi']:.2f} × {spec['cell_h_mi']:.2f} mi) |")
    print(f"| Study area extent | ~{spec['bbox_lon_span_mi']:.0f} × {spec['bbox_lat_span_mi']:.0f} mi |")
    print(f"| Full grid dimensions | {spec['n_rows']} rows × {spec['n_cols']} cols = {spec['n_cells_total']} cells |")
    print(f"| Valid cells (bbox-wide) | {spec['n_cells_valid_bboxwide']} |")
    print(f"| Valid cells (within Arizona) | {spec['n_cells_in_az']} |")

    out_path = bc.REPO_ROOT / "docs" / "hotspot_raster_summary.csv"
    lines = ["period,n_deaths,n_cells,distance_band_deg,distance_band_mi,avg_neighbors,hot_99,hot_95,hot_90,not_sig,cold_90,cold_95,cold_99"]
    for r in hs_rows:
        lines.append(",".join(str(r[k]) for k in [
            "period", "n_deaths", "n_cells", "distance_band_deg", "distance_band_mi", "avg_neighbors",
            "hot_99", "hot_95", "hot_90", "not_sig", "cold_90", "cold_95", "cold_99"]))
    lines.append("")
    lines.append("property,value")
    for k, v in spec.items():
        lines.append(f"{k},{v}")
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
