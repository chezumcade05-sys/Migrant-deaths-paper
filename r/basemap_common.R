# Shared basemap/plotting logic for reproducing Figures 3, 4, and 5 from
# Bansak, Blanco, Coon & Dieringer (2025), "Border Walls and Death on the
# US-Mexico Border." This is an R port of basemap_common.py -- see that file
# and README.md for the full explanation of the pipeline; this file is kept
# functionally identical (same classification rule, same colors, same
# layers, same layout) so results match between the two languages.
#
# Not run directly -- figure3.R / figure4.R / figure5.R / figure6.R /
# figure7.R / figure9_hotspot.R each source() this file.

suppressPackageStartupMessages(library(sf))

# ---------------------------------------------------------------------------
# Colors sampled directly from the original figures' legend swatches (the
# embedded JPEGs inside the .docx) -- identical hex values to basemap_common.py.
# ---------------------------------------------------------------------------
DEATH_GREEN         <- "#27e32c"
FENCE_BLUE           <- "#205aae"   # "Border built 2007 or before"
FENCE_YELLOW         <- "#ffe600"   # "Border built 2008 or later"
DESERT_BROWN         <- "#82604f"
RESERVATION_PURPLE   <- "#3d1a5b"
# Not sourced from the paper -- a distinct teal, chosen to read clearly
# against both the green death markers and the navy fence lines.
WATER_STATION_COLOR  <- "#00b7c3"

# ---------------------------------------------------------------------------
# Every entry script (figure3.R, figure4.R, ...) determines its own location
# and sets SCRIPT_DIR *before* sourcing this file -- that has to happen in
# the entry script itself (can't be done from in here: we need to know
# where this file is in order to source() it in the first place). See the
# top of any figureN.R for that bootstrap snippet.
# ---------------------------------------------------------------------------
if (!exists("SCRIPT_DIR")) stop("SCRIPT_DIR must be set before sourcing basemap_common.R -- see the top of figure4.R")
# Repo layout: this file lives in r/, siblings to python/, data/, figures/,
# and docs/ at the repo root -- REPO_ROOT is r/'s parent.
REPO_ROOT   <- dirname(SCRIPT_DIR)
DATA_DIR    <- file.path(REPO_ROOT, "data")
FIGURES_DIR <- file.path(REPO_ROOT, "figures")
DEATH_CSV  <- file.path(DATA_DIR, "Original death data.csv")
FENCE_GDB  <- file.path(DATA_DIR, "Original Fence data", "01-ORIGINAL.gdb")
SHAPE_DIR  <- file.path(DATA_DIR, "Shape Files")
# Extracted from Humane Borders' own public poster -- see
# WATER_STATIONS_METHODOLOGY.md for how, and for the ~5 mile positional
# uncertainty this carries. Used for all figures regardless of period: an
# earlier 2000-2007-poster extraction was tried and dropped -- it needed a
# manual correction for points landing south of the border and disagreed
# with this dataset by ~29 miles on average, so this (2000-2019) extraction
# is the one now used everywhere as the more reliable of the two.
WATER_STATIONS_CSV <- file.path(DATA_DIR, "Water Stations 2000-2019.csv")

# Study-area bounding box (roughly southern Arizona) -- identical to Python.
BBOX <- list(min_lon = -115.2, max_lon = -109.0, min_lat = 30.8, max_lat = 34.3)

FENCE_LAYERS <- c(
  "obp_baseline_ti_ped_fence_LIMIT_GOV_USE",
  "obp_baseline_ti_veh_barrier_LIMIT_GOV_USE"
)

CITIES <- list(
  Phoenix  = c(-112.0740, 33.4484),
  Tucson   = c(-110.9265, 32.2217),
  Nogales  = c(-110.9370, 31.3379),
  Sasabe   = c(-111.5410, 31.4890),
  Sonoyta  = c(-112.8380, 31.8620)
)

# ---------------------------------------------------------------------------
# draw_scale_bar / draw_north_arrow -- identical geometry/logic to the
# Python versions, just using base R graphics primitives instead of
# matplotlib patches.
# ---------------------------------------------------------------------------
draw_scale_bar <- function(lon0, lat0, at_latitude, miles = c(0, 15, 30, 60)) {
  miles_per_degree <- 69.17 * abs(cos(at_latitude * pi / 180))
  deg_per_mile <- 1 / miles_per_degree
  tick_h <- 0.045
  for (i in seq_len(length(miles) - 1)) {
    x0 <- lon0 + miles[i] * deg_per_mile
    x1 <- lon0 + miles[i + 1] * deg_per_mile
    face <- if (i %% 2 == 1) "black" else "white"
    rect(x0, lat0, x1, lat0 + tick_h / 3, col = face, border = "black", lwd = 0.6)
  }
  for (m in miles) {
    x <- lon0 + m * deg_per_mile
    segments(x, lat0, x, lat0 + tick_h, col = "black", lwd = 0.6)
    text(x, lat0 - 0.02, labels = as.character(m), cex = 0.55, adj = c(0.5, 1))
  }
  end_x <- lon0 + miles[length(miles)] * deg_per_mile
  text(end_x + 0.05, lat0, labels = "Miles", cex = 0.55, adj = c(0, 0.5))
}

draw_north_arrow <- function(lon, lat, size = 0.12) {
  arrows(lon, lat, lon, lat + size, length = 0.08, angle = 20, lwd = 1.2, col = "black")
  text(lon, lat + size + 0.03, labels = "N", cex = 0.9, font = 2)
}

# A text note (not a true-to-scale box -- a single 0.044 deg cell would be
# an imperceptible speck at this map's zoom level) stating the raster
# grid's cell size, in degrees and in approximate real-world miles at the
# study area's latitude. For figures that render data as a fixed-size grid
# of cells (hot-spot analysis, danger index) rather than individual points.
# Mirrors draw_cell_size_note() in basemap_common.py.
draw_cell_size_note <- function(cell_size_deg, lon, lat, reference_lat, cex = 0.6) {
  miles_per_deg_lat <- 69.17
  miles_per_deg_lon <- 69.17 * abs(cos(reference_lat * pi / 180))
  h_mi <- cell_size_deg * miles_per_deg_lat
  w_mi <- cell_size_deg * miles_per_deg_lon
  label <- sprintf("Grid cell size: %g° (≈%.1f x %.1f mi)", cell_size_deg, w_mi, h_mi)
  text(lon, lat, labels = label, cex = cex, adj = c(0, 1))
}

# ---------------------------------------------------------------------------
# 1. Load migrant death data and reproduce the paper's pre/post-SFA split
#    (Section 4.2). Verified to match the paper's reported totals:
#    1,215 pre-SFA / 1,826 post-SFA / 3,041 combined (Table 4), and verified
#    to match the Python implementation's counts exactly.
# ---------------------------------------------------------------------------
load_deaths <- function() {
  deaths <- read.csv(DEATH_CSV, stringsAsFactors = FALSE)
  dates <- as.Date(deaths$Reporting.Date, format = "%m/%d/%Y")
  year  <- as.integer(format(dates, "%Y"))
  pmi <- trimws(deaths$Post.Mortem.Interval)
  pmi[pmi == ""] <- NA

  # A 2008 discovery whose postmortem interval was "> 6-8 months" is moved
  # into the pre-SFA bucket, since the death itself likely occurred in 2007
  # even though the remains were found in 2008 (paper, Sec. 4.2). Using
  # %in% rather than == keeps NA years/pmi values safely FALSE instead of NA.
  reclassified_2008 <- (year %in% 2008) & !is.na(pmi) & (pmi == "> 6-8 months")

  deaths$year <- year
  deaths$is_pre_sfa  <- (year %in% 2000:2007) | reclassified_2008
  deaths$is_post_sfa <- (year %in% 2008:2019) & !is.na(pmi) & !reclassified_2008
  # Standardize coordinate column names used throughout the rest of the code.
  deaths$Longitude <- deaths$Longitude
  deaths$Latitude  <- deaths$Latitude
  deaths
}

# ---------------------------------------------------------------------------
# 2. Load border fencing, both periods -- the original Figure 4 legend shows
#    "Border built 2008 or later" (yellow) alongside "...2007 or before"
#    (blue) on the SAME map as the pre-SFA death points, so viewers can
#    compare where deaths clustered against the eventual full build-out.
# ---------------------------------------------------------------------------
.date_in_year <- function(x) {
  m <- regmatches(x, regexpr("^[0-9]{4}", x))
  suppressWarnings(as.integer(ifelse(nzchar(m), m, NA)))
}

load_fence_layers <- function() {
  result <- tryCatch({
    before_list <- list()
    after_list  <- list()
    for (layer in FENCE_LAYERS) {
      gdf <- st_read(FENCE_GDB, layer = layer, quiet = TRUE)  # already EPSG:4326
      gdf <- gdf[gdf$STATE_ABBR == "AZ", ]
      gdf$year_in <- .date_in_year(gdf$DATE_IN)
      before_list[[layer]] <- gdf[!is.na(gdf$year_in) & gdf$year_in <= 2007, ]
      after_list[[layer]]  <- gdf[!is.na(gdf$year_in) & gdf$year_in >= 2008, ]
    }
    list(before = before_list, after = after_list, have_fence = TRUE)
  }, error = function(e) {
    cat("Could not load fence geodatabase layers (", conditionMessage(e), ").\n", sep = "")
    cat("To include fence lines, install a working GIS stack: install.packages(\"sf\")\n")
    list(before = list(), after = list(), have_fence = FALSE)
  })
  result
}

# Coordinates were extracted from a Humane Borders published poster, not
# surveyed directly -- see WATER_STATIONS_METHODOLOGY.md for the method and
# its uncertainty.
load_water_stations <- function() {
  read.csv(WATER_STATIONS_CSV, stringsAsFactors = FALSE)
}

# ---------------------------------------------------------------------------
# 3. Basemap layers shared by every figure (state boundary, roads, desert,
#    reservation, fence). Draws into whatever plot device is already open.
# ---------------------------------------------------------------------------
draw_basemap_layers <- function(fence) {
  state <- st_read(file.path(SHAPE_DIR, "tl_2021_us_state", "tl_2021_us_state.shp"), quiet = TRUE)
  state <- state[state$STATEFP == "04", ]
  plot(st_geometry(state), add = TRUE, border = "grey70", lwd = 0.7, col = NA)

  roads <- st_read(file.path(SHAPE_DIR, "tl_2021_04_prisecroads", "tl_2021_04_prisecroads.shp"), quiet = TRUE)
  roads <- roads[roads$RTTYP %in% c("I", "U", "S"), ]
  plot(st_geometry(roads), add = TRUE, col = "grey60", lwd = 0.5)

  desert <- st_read(file.path(SHAPE_DIR, "deserts_sw", "deserts_sw.shp"), quiet = TRUE)
  desert <- desert[desert$NAME %in% c("Colorado Sonoran Desert", "Arizona Sonoran Desert"), ]
  desert <- st_transform(desert, 4326)  # native reprojection -- no manual UTM math needed
  plot(st_geometry(desert), add = TRUE, border = DESERT_BROWN, lwd = 1.6, lty = "44", col = NA)

  reservation <- st_read(file.path(SHAPE_DIR, "tl_2021_us_aiannh", "tl_2021_us_aiannh.shp"), quiet = TRUE)
  reservation <- reservation[reservation$NAMELSAD == "Tohono O'odham Nation Reservation", ]
  plot(st_geometry(reservation), add = TRUE, border = RESERVATION_PURPLE, lwd = 1.3, lty = "44", col = NA)

  if (fence$have_fence) {
    for (gdf in fence$after)  if (nrow(gdf) > 0) plot(st_geometry(gdf), add = TRUE, col = FENCE_YELLOW, lwd = 2.4)
    for (gdf in fence$before) if (nrow(gdf) > 0) plot(st_geometry(gdf), add = TRUE, col = FENCE_BLUE, lwd = 2.4)
  }
}

draw_cities <- function() {
  for (name in names(CITIES)) {
    xy <- CITIES[[name]]
    text(xy[1], xy[2], labels = name, cex = 0.65, adj = c(-0.1, -0.4))
  }
}

# ---------------------------------------------------------------------------
# 4. Full point-map figure (Figures 3/4/5): basemap + death points + legend.
# ---------------------------------------------------------------------------
render_figure <- function(deaths_subset, death_label, title, out_filename) {
  fence <- load_fence_layers()
  water <- load_water_stations()

  lat_mid <- (BBOX$min_lat + BBOX$max_lat) / 2
  geo_aspect <- 1 / cos(lat_mid * pi / 180)   # matplotlib's ax.set_aspect(geo_aspect) equivalent
  lon_span <- BBOX$max_lon - BBOX$min_lon
  lat_span <- BBOX$max_lat - BBOX$min_lat
  fig_w_in <- 12
  fig_h_in <- fig_w_in * (lat_span * geo_aspect) / lon_span

  out_path <- file.path(FIGURES_DIR, out_filename)
  png(out_path, width = fig_w_in, height = fig_h_in, units = "in", res = 200)
  par(mar = c(1, 1, 3, 1))
  plot(1, type = "n", xlim = c(BBOX$min_lon, BBOX$max_lon), ylim = c(BBOX$min_lat, BBOX$max_lat),
       asp = 1 / cos(lat_mid * pi / 180), xaxt = "n", yaxt = "n", xlab = "", ylab = "", bty = "o")
  title(main = title, cex.main = 1.3)

  draw_basemap_layers(fence)

  points(deaths_subset$Longitude, deaths_subset$Latitude, pch = 21,
         bg = DEATH_GREEN, col = "black", cex = 0.55, lwd = 0.3)

  # Water stations -- not part of the original figures; see
  # WATER_STATIONS_METHODOLOGY.md for source and positional uncertainty.
  points(water$longitude, water$latitude, pch = 17,
         col = WATER_STATION_COLOR, cex = 1.1)
  points(water$longitude, water$latitude, pch = 2,
         col = "black", cex = 1.1, lwd = 0.4)

  draw_cities()
  draw_scale_bar(lon0 = -115.05, lat0 = 31.05, at_latitude = 32.0)
  draw_north_arrow(lon = -114.9, lat = 31.3)

  # NOTE: lty must stay a character vector throughout -- mixing NA/numeric/
  # string entries via c() silently coerces the whole vector to character,
  # turning a numeric 1 ("solid") into the invalid string "1".
  legend_labels <- c(sprintf("%s (n=%d)", death_label, nrow(deaths_subset)),
                      sprintf("Water stations (~2019, n=%d, ±~5mi)", nrow(water)))
  legend_pch    <- c(21, 17)
  legend_pt_bg  <- c(DEATH_GREEN, NA)
  legend_lty    <- c(NA, NA)
  legend_lwd    <- c(NA, NA)
  legend_col    <- c("black", WATER_STATION_COLOR)
  if (fence$have_fence) {
    legend_labels <- c(legend_labels, "Border built 2008 or later", "Border built 2007 or before")
    legend_pch    <- c(legend_pch, NA, NA)
    legend_pt_bg  <- c(legend_pt_bg, NA, NA)
    legend_lty    <- c(legend_lty, "solid", "solid")
    legend_lwd    <- c(legend_lwd, 2.4, 2.4)
    legend_col    <- c(legend_col, FENCE_YELLOW, FENCE_BLUE)
  }
  legend_labels <- c(legend_labels, "Arizona Sonoran Desert", "Tohono O'odham Nation Reservation")
  legend_pch    <- c(legend_pch, NA, NA)
  legend_pt_bg  <- c(legend_pt_bg, NA, NA)
  legend_lty    <- c(legend_lty, "44", "44")
  legend_lwd    <- c(legend_lwd, 1.6, 1.3)
  legend_col    <- c(legend_col, DESERT_BROWN, RESERVATION_PURPLE)

  legend("topright", legend = legend_labels, pch = legend_pch, pt.bg = legend_pt_bg,
         lty = legend_lty, lwd = legend_lwd, col = legend_col, pt.cex = 1.1,
         title = "Legend", title.font = 2, bty = "o", bg = "white", cex = 0.75)

  stamp <- sprintf("generated %s", format(Sys.time(), "%Y-%m-%d %H:%M:%S"))

  dev.off()
  cat("Saved plot to", out_path, "\n")
  cat(stamp, "\n")
}
