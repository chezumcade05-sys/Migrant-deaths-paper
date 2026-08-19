#!/usr/bin/env python3
"""
Panel-building pipeline for the Poisson DiD analysis.

Steps
-----
1. Compute the danger index (6 Z-scored factors) from danger_index_common
2. Bin pre/post-SFA deaths to the 0.044° grid
3. Assemble the panel dataset (cell x period)
4. Add distance to nearest fence segment (from CBP GDB)
5. Add distance to nearest fence gap (derived from AZ border minus fence)
6. Add interactions and sector apprehension offset

Output: docs/panel_data.csv  (read by poisson_tables.py)

Run this script whenever the danger index or underlying data changes.
All paths are resolved relative to this script — no hardcoded user paths.
"""

import os, sys, warnings
from pathlib import Path

_VENV = Path(__file__).resolve().parent.parent / ".venv"
_PY   = _VENV / "bin" / "python"
if _PY.exists() and Path(sys.prefix).resolve() != _VENV.resolve():
    os.execv(str(_PY), [str(_PY), str(Path(__file__).resolve()), *sys.argv[1:]])

warnings.filterwarnings("ignore")

import math
import numpy as np
import pandas as pd
from collections import Counter
from scipy.spatial import cKDTree
from pyproj import Transformer
import geopandas as gpd
import shapefile                          # pyshp
from shapely.geometry import shape
from shapely.geometry import box as sbox
from shapely.ops import unary_union

import basemap_common as bc
import hotspot_common as hc
import danger_index_common as dc

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO     = Path(__file__).resolve().parent.parent
DOCS     = REPO / "docs"
OUT_CSV  = DOCS / "panel_data.csv"

# ── Grid (identical to hot-spot analysis) ──────────────────────────────────────
CS   = hc.CELL_SIZE                 # 0.044°
MLON = bc.BBOX["min_lon"]
MLAT = bc.BBOX["min_lat"]

TF = Transformer.from_crs("EPSG:4326", "EPSG:32612", always_xy=True)

# ── Sector apprehensions (Johnston's Archive / CBP) ────────────────────────────
SECTOR_APPREHENSIONS = {
    ("tucson", 0): 431_012,   # FY2000-2007 average
    ("tucson", 1): 125_527,   # FY2008-2019 average
    ("yuma",   0):  84_933,
    ("yuma",   1):  14_620,
}
YUMA_LON_CUTOFF = -113.0


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Danger index
# ══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("STEP 1 — Computing danger index (6 Z-scored factors)")
print("=" * 70)

di_result = dc.compute_danger_index()
di_map = {
    (int(r), int(c)): float(v)
    for r, c, v in zip(di_result["row"], di_result["col"], di_result["composite"])
}
vals = list(di_map.values())
print(f"  D_i range: [{min(vals):.2f}, {max(vals):.2f}]  "
      f"mean={np.mean(vals):.2f}  std={np.std(vals):.2f}")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Load deaths, bin to 0.044° grid
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 2 — Loading deaths")
print("=" * 70)

deaths = bc.load_deaths()
pre    = deaths[deaths["is_pre_sfa"]]
post   = deaths[deaths["is_post_sfa"]]
print(f"  Pre-SFA  (2000-2007): {len(pre)}")
print(f"  Post-SFA (2008-2019): {len(post)}")

def bin_deaths(df):
    cnt = Counter()
    for lon, lat in zip(df["Longitude"], df["Latitude"]):
        col = int((lon - MLON) / CS)
        row = int((lat - MLAT) / CS)
        cnt[(row, col)] += 1
    return cnt

cnt_pre  = bin_deaths(pre)
cnt_post = bin_deaths(post)
cells    = sorted(set(cnt_pre) | set(cnt_post))
print(f"  Active cells (>=1 death): {len(cells)}")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Assemble panel
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 3 — Assembling panel")
print("=" * 70)

rows_list = []
missing_di = 0
for r, c in cells:
    lon = MLON + (c + 0.5) * CS
    lat = MLAT + (r + 0.5) * CS
    di  = di_map.get((r, c), float("nan"))
    if math.isnan(di):
        missing_di += 1
    for post_val in (0, 1):
        count = cnt_pre.get((r, c), 0) if post_val == 0 else cnt_post.get((r, c), 0)
        rows_list.append(dict(
            cell_id   = f"{r}_{c}",
            row       = r,
            col       = c,
            lon       = lon,
            lat       = lat,
            Post      = float(post_val),
            D_i       = di,
            deaths    = int(count),
        ))

panel = pd.DataFrame(rows_list).dropna()
if missing_di:
    print(f"  WARNING: {missing_di} active cells had no D_i value — dropped")
print(f"  {len(panel)} rows | {panel['cell_id'].nunique()} cells x 2 periods")
print(f"  Deaths: pre={int(panel[panel.Post==0]['deaths'].sum())}  "
      f"post={int(panel[panel.Post==1]['deaths'].sum())}")
print(f"  D_i: min={panel['D_i'].min():.2f}  "
      f"mean={panel['D_i'].mean():.2f}  max={panel['D_i'].max():.2f}")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Distance to nearest fence segment
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 4 — Distance to nearest fence segment")
print("=" * 70)

ped    = gpd.read_file(str(bc.FENCE_GDB), layer=0)
veh    = gpd.read_file(str(bc.FENCE_GDB), layer=1)
ped_az = ped[ped["STATE_ABBR"] == "AZ"].to_crs("EPSG:32612")
veh_az = veh[veh["STATE_ABBR"] == "AZ"].to_crs("EPSG:32612")

def extract_coords(geom):
    if geom.geom_type in ("LineString", "LinearRing"):
        return list(geom.coords)
    pts = []
    for part in geom.geoms:
        pts.extend(extract_coords(part))
    return pts

fence_pts = []
for geom in pd.concat([ped_az.geometry, veh_az.geometry]):
    fence_pts.extend(extract_coords(geom))

fence_tree = cKDTree(np.array(fence_pts))
cells_u    = panel[["cell_id","lon","lat"]].drop_duplicates().copy()
gdf_c      = gpd.GeoDataFrame(cells_u,
                 geometry=gpd.points_from_xy(cells_u["lon"], cells_u["lat"]),
                 crs="EPSG:4326").to_crs("EPSG:32612")
xy         = np.column_stack([gdf_c.geometry.x, gdf_c.geometry.y])
dist_m, _  = fence_tree.query(xy)
cells_u["dist_fence_km"] = dist_m / 1000.0
panel = panel.merge(cells_u[["cell_id","dist_fence_km"]], on="cell_id")
print(f"  dist_fence_km: min={panel['dist_fence_km'].min():.1f}  "
      f"mean={panel['dist_fence_km'].mean():.1f}  "
      f"max={panel['dist_fence_km'].max():.1f} km")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Distance to nearest fence gap
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 5 — Distance to nearest fence gap")
print("=" * 70)

# The AZ-Mexico border = southern edge of AZ state polygon.
# Clip the AZ boundary to a lat strip spanning the border (~31.2-31.6°).
sf_state = shapefile.Reader(
    str(bc.SHAPE_DIR / "tl_2021_us_state" / "tl_2021_us_state.shp"))
az_geom = None
for sr in sf_state.iterShapeRecords():
    if sr.record["STUSPS"] == "AZ":
        az_geom = shape(sr.shape.__geo_interface__)
        break

border_strip = sbox(-115.0, 31.2, -109.0, 31.6)
az_border    = az_geom.boundary.intersection(border_strip)
az_border_m  = (gpd.GeoDataFrame(geometry=[az_border], crs="EPSG:4326")
                   .to_crs("EPSG:32612").geometry.iloc[0])

# Fence union buffered 2 km; gap = unfenced border
fence_union_m = unary_union(
    list(ped_az.geometry) + list(veh_az.geometry)
).buffer(2000)
gap_m = az_border_m.difference(fence_union_m)
print(f"  Unfenced border: {gap_m.length / 1000:.1f} km")

def sample_gap_pts(geom, spacing_m=500):
    pts  = []
    segs = [geom] if geom.geom_type == "LineString" else list(geom.geoms)
    for seg in segs:
        if seg.length < 100:
            continue
        n = max(2, int(seg.length / spacing_m))
        for i in range(n + 1):
            pt = seg.interpolate(i / n, normalized=True)
            pts.append((pt.x, pt.y))
    return pts

gap_pts = sample_gap_pts(gap_m)
print(f"  Gap sample points: {len(gap_pts)}")

if gap_pts:
    gap_tree  = cKDTree(np.array(gap_pts))
    cells_u2  = panel[["cell_id","lon","lat"]].drop_duplicates().copy()
    gdf_gap   = gpd.GeoDataFrame(cells_u2,
                    geometry=gpd.points_from_xy(cells_u2["lon"], cells_u2["lat"]),
                    crs="EPSG:4326").to_crs("EPSG:32612")
    xy2       = np.column_stack([gdf_gap.geometry.x, gdf_gap.geometry.y])
    d_gap, _  = gap_tree.query(xy2)
    cells_u2["dist_gap_km"] = d_gap / 1000.0
    panel = panel.merge(cells_u2[["cell_id","dist_gap_km"]], on="cell_id")
    print(f"  dist_gap_km: min={panel['dist_gap_km'].min():.1f}  "
          f"mean={panel['dist_gap_km'].mean():.1f}  "
          f"max={panel['dist_gap_km'].max():.1f} km")
else:
    print("  WARNING: no gap points found — dist_gap_km set to 0")
    panel["dist_gap_km"] = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Interactions + sector apprehension offset
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("STEP 6 — Interactions + sector offset")
print("=" * 70)

panel["Post_x_Di"]         = panel["Post"] * panel["D_i"]
panel["Post_x_fence"]      = panel["Post"] * panel["dist_fence_km"]
panel["Post_x_gap"]        = panel["Post"] * panel["dist_gap_km"]
panel["sector"]            = np.where(panel["lon"] < YUMA_LON_CUTOFF, "yuma", "tucson")
panel["apprehensions"]     = panel.apply(
    lambda r: SECTOR_APPREHENSIONS[(r["sector"], int(r["Post"]))], axis=1)
panel["log_apprehensions"] = np.log(panel["apprehensions"])

n_tucson = panel[panel.sector=="tucson"]["cell_id"].nunique()
n_yuma   = panel[panel.sector=="yuma"]["cell_id"].nunique()
print(f"  Tucson sector cells: {n_tucson}  |  Yuma sector cells: {n_yuma}")


# ══════════════════════════════════════════════════════════════════════════════
# Save
# ══════════════════════════════════════════════════════════════════════════════
panel.to_csv(OUT_CSV, index=False)
print(f"\nSaved: {OUT_CSV}")
print(f"  {len(panel)} rows | {panel['cell_id'].nunique()} cells")
print("=" * 70)
print("Done. Run poisson_tables.py to build regression results and Word tables.")
