# Data Sources and References

Every external data source pulled in while building these figures, in one
place. Data already provided with the paper (the death records, the fence
geodatabase, the authors' own precomputed hot-spot output) is listed too,
for completeness, even though I didn't have to go find that myself. Full
methodology for *how* each source was used lives in the corresponding
`*_METHODOLOGY.md` file — this page is the citation list, not the write-up.

## Provided with the original paper (not independently sourced)

- **Arizona OpenGIS Initiative for Deceased Migrants.** Pima County Office
  of the Medical Examiner and Humane Borders, Inc. `Original death data.csv`.
  https://humaneborders.info
- **CBP tactical infrastructure geodatabase** (pedestrian fence and vehicle
  barrier locations by install date). `Original Fence data/01-ORIGINAL.gdb`.
  Internal metadata marks this **FOUO** (For Official Use Only, a DHS
  sensitivity marking) — see `README.md` for that caveat. Note the paper's
  own reference list cites fencing data to Castañeda, L., and Guerrero, J.
  (2017), "Decades-Long Struggle to Secure US–Mexico Border," KPBS,
  https://www.kpbs.org/news/border-immigration/2017/11/13/americas-wall —
  a different, public-facing source than this geodatabase; I did not
  independently verify the two agree.
- **The paper's own ArcGIS Hot Spot Analysis output.**
  `HotBeforejuly2023.dbf` / `HotAfterJuly2023.dbf` — used as ground truth to
  validate the from-scratch Gi\* reimplementation in `hotspot_common.py`/`.R`
  (see `Claude Hotspot documentation.md` §4).

## Basemap geography (`Shape Files/`)

- **U.S. Census Bureau, TIGER/Line Shapefiles, 2021 vintage.**
  - Counties: https://www2.census.gov/geo/tiger/TIGER2021/COUNTY/tl_2021_us_county.zip
  - Tribal areas (AIANNH — used for the Tohono O'odham Nation Reservation boundary): https://www2.census.gov/geo/tiger/TIGER2021/AIANNH/tl_2021_us_aiannh.zip
  - Primary/secondary roads, Arizona (FIPS 04): https://www2.census.gov/geo/tiger/TIGER2021/PRISECROADS/tl_2021_04_prisecroads.zip
  - States: https://www2.census.gov/geo/tiger/TIGER2021/STATE/tl_2021_us_state.zip
  - Accessed 2026-07-21.
- **Faunt, C.C., 2006.** *Deserts of the southwestern United States, for
  the Death Valley regional ground-water flow system study, Nevada and
  California.* U.S. Geological Survey data release.
  https://doi.org/10.5066/P944GEAY — catalog page:
  https://www.sciencebase.gov/catalog/item/63140573d34e36012efa2c5a.
  This is the exact 2006 survey the original paper cites for its Sonoran
  Desert boundary (Section 4.2). Accessed 2026-07-21.

## Water station locations (`Water Stations 2000-2019.csv`)

- **Humane Borders, Inc.**, "Printable Maps & Posters,"
  https://www.humaneborders.org/newpage. Coordinates were extracted (not
  provided as data by Humane Borders) from the poster PDF:
  *Migrants Deaths, Rescue Beacons, Water Stations 2000-2019*,
  https://irp.cdn-website.com/5818aa7e/files/uploaded/deathpostercumulative_2019_stewardship_mid.pdf.
  A second poster, *...2000-2007*,
  https://irp.cdn-website.com/5818aa7e/files/uploaded/cumulativemap20002007.pdf,
  was also extracted but later dropped as less reliable — both the
  extraction method and why the 2007 version was discarded are in
  `WATER_STATIONS_METHODOLOGY.md`. Accessed 2026-07-29.

## Danger index environmental inputs (`Danger Index Environmental Layers.csv`)

- **PRISM Climate Group, Oregon State University**, https://prism.oregonstate.edu
  — data citation, per PRISM's own citation guidance
  (https://prism.oregonstate.edu/documents/PRISM_terms_of_use.pdf). Monthly
  4km tmax (maximum temperature) rasters for July, 2014–2023, pulled
  individually and averaged into a 10-year proxy for "ambient summer
  temperature" (see `DANGER_INDEX_METHODOLOGY.md` §1 and §8 — this is an
  approximate normal, not PRISM's official 30-year 1991–2020 normal
  product, which needed a different access path than the one used here).
  Data service used: https://services.nacse.org/prism/data/get/us/4km/tmax/{YYYYMM}
  (e.g. `.../tmax/201407` for July 2014). Accessed 2026-08-03.

  PRISM also asks the underlying methodology paper be cited alongside the
  data itself:
  Daly, C., Halbleib, M., Smith, J.I., Gibson, W.P., Doggett, M.K., Taylor,
  G.H., Curtis, J., and Pasteris, P.P., 2008. "Physiographically sensitive
  mapping of climatological temperature and precipitation across the
  conterminous United States." *International Journal of Climatology*,
  28(15): 2031–2064.
- **U.S. Geological Survey, 3D Elevation Program (3DEP).** Elevation data,
  used to derive slope (see `DANGER_INDEX_METHODOLOGY.md` §4 for why slope
  couldn't be pulled directly and had to be computed manually from raw
  elevation instead). Service:
  https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer.
  Accessed 2026-08-03.
- **U.S. Geological Survey, National Agriculture Imagery Program (NAIP),**
  via USGS National Map's 4-band imagery mosaic. Used to compute NDVI
  (vegetation density), the danger index's 6th factor — see
  `DANGER_INDEX_METHODOLOGY.md` §3 for the formula, the literature
  precedent (Boyce, Chambers & Launius 2019, below) that motivated adding
  this factor, and a data-quality fix at the edge of the imagery's
  coverage. Service:
  https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPPlus/ImageServer.
  Accessed 2026-08-06.
- **Boyce, G.A., Chambers, S.N., and Launius, S., 2019.** "Bodily Inertia
  and the Weaponization of the Sonoran Desert in US Boundary Enforcement:
  A GIS Modeling of Migration Routes through Arizona's Altar Valley."
  *Journal on Migration and Human Security*, 7(1).
  https://doi.org/10.1177/2331502419825610. Not a data source itself, but
  the methodological precedent for including a vegetation/"shade" factor
  in a migrant-crossing danger index — their "ruggedness index" is the
  source of the NDVI formula and, notably, the direction convention this
  reproduction follows (denser vegetation = more dangerous, not
  protective shade). A peer reviewer's report pointed to "shade" as having
  precedent in past literature without naming a specific source; this is
  the closest matching precedent found.

## Reference coordinates used for map calibration/labels

City/town coordinates used for map labels, port-of-entry markers, and
georeferencing the Humane Borders posters (Phoenix, Tucson, Nogales,
Sasabe, Sonoyta, Yuma, Lukeville, Bisbee, Arivaca, Naco, Douglas, Sells,
Ajo) are standard, publicly known geographic coordinates, not drawn from a
single citable dataset — used the same way an atlas would be.
