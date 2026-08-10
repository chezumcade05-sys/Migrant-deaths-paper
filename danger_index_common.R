# A rebuilt version of the paper's danger index (Section 4.1 / Figure 2),
# using a different factor set and a different scoring method than the
# original -- see DANGER_INDEX_METHODOLOGY.md for the full write-up.
#
# R port of danger_index_common.py -- kept functionally identical. Requires
# basemap_common.R and hotspot_common.R already sourced by the entry script.

suppressPackageStartupMessages(library(sf))

ENV_CSV <- file.path(DATA_DIR, "Danger Index Environmental Layers.csv")

# Real, substantial Arizona cities only -- the small border towns in
# CITIES (Nogales, Sasabe, Sonoyta) are map-orientation labels, not the
# "major city" reference points this factor is meant to represent.
MAJOR_CITIES <- list(Phoenix = CITIES$Phoenix, Tucson = CITIES$Tucson)

.min_dist_to_points <- function(lons, lats, ref_list) {
  d <- rep(Inf, length(lons))
  for (ref in ref_list) {
    d <- pmin(d, sqrt((lons - ref[1])^2 + (lats - ref[2])^2))
  }
  d
}

.min_dist_to_roads <- function(lons, lats) {
  roads <- st_read(file.path(SHAPE_DIR, "tl_2021_04_prisecroads", "tl_2021_04_prisecroads.shp"), quiet = TRUE)
  roads <- roads[roads$RTTYP %in% c("I", "U", "S"), ]
  roads_union <- st_union(st_geometry(roads))
  pts <- st_as_sf(data.frame(lon = lons, lat = lats), coords = c("lon", "lat"), crs = st_crs(roads))
  # sf's default st_distance() on unprojected (lon/lat) geometry uses
  # spherical (s2) great-circle distance in meters. Every other factor
  # here (city, water) is Euclidean degree-space distance -- matching how
  # the Python version computes this via Shapely, which has no CRS
  # awareness and is always planar. Stripping the CRS (rather than toggling
  # sf_use_s2(), which pulls in the optional lwgeom package for this GEOS
  # fallback path) makes GEOS treat the coordinates as plain planar
  # numbers, keeping all four distance-based factors on the same
  # (degree-space) footing without adding a dependency.
  st_crs(pts) <- NA
  st_crs(roads_union) <- NA
  as.numeric(st_distance(pts, roads_union))
}

.min_dist_to_water <- function(lons, lats) {
  water <- load_water_stations()
  d <- rep(Inf, length(lons))
  for (i in seq_len(nrow(water))) {
    d <- pmin(d, sqrt((lons - water$longitude[i])^2 + (lats - water$latitude[i])^2))
  }
  d
}

zscore <- function(x) (x - mean(x, na.rm = TRUE)) / sd(x, na.rm = TRUE)

compute_danger_index <- function() {
  env <- read.csv(ENV_CSV, stringsAsFactors = FALSE)
  lons <- env$longitude
  lats <- env$latitude

  dist_city  <- .min_dist_to_points(lons, lats, MAJOR_CITIES)
  dist_road  <- .min_dist_to_roads(lons, lats)
  dist_water <- .min_dist_to_water(lons, lats)
  slope <- env$slope_deg
  tmax  <- env$july_tmax_c
  ndvi  <- env$ndvi

  z_temp  <- zscore(tmax)
  z_city  <- zscore(dist_city)
  z_road  <- zscore(dist_road)
  z_water <- zscore(dist_water)
  z_slope <- zscore(slope)
  # Higher NDVI (denser vegetation) is treated as MORE dangerous, not as
  # protective shade -- matching Boyce, Chambers & Launius (2019)'s
  # "ruggedness index", the precedent for including a vegetation/"shade"
  # factor here: dense vegetation slows travel, disorients, and increases
  # exertion. See DANGER_INDEX_METHODOLOGY.md.
  z_ndvi  <- zscore(ndvi)
  composite <- z_temp + z_city + z_road + z_water + z_slope + z_ndvi

  list(row = env$row, col = env$col, lon = lons, lat = lats,
       dist_city_deg = dist_city, dist_road_deg = dist_road, dist_water_deg = dist_water,
       slope_deg = slope, july_tmax_c = tmax, ndvi = ndvi,
       z_temp = z_temp, z_city = z_city, z_road = z_road, z_water = z_water,
       z_slope = z_slope, z_ndvi = z_ndvi,
       composite = composite,
       n_rows = max(env$row) + 1, n_cols = max(env$col) + 1)
}

# Pale yellow (relatively less dangerous) -> orange -> dark red (most
# dangerous). Deliberately NOT the original paper's green-to-red scheme:
# green reads as "safe," which is the wrong message for a desert crossing
# where even the "least dangerous" areas are still hazardous -- and
# red-green is also the single most common form of color blindness.
# ColorBrewer's "YlOrRd" sequential palette (colorblind-safe, no green),
# matching the Python version's matplotlib YlOrRd colormap.
.danger_palette <- colorRampPalette(c("#ffffcc", "#ffeda0", "#fed976", "#feb24c",
                                        "#fd8d3c", "#fc4e2a", "#e31a1c", "#bd0026", "#800026"))

# Adds a min/max/mean table for the 5 raw (pre-Z-score) factors in the
# dedicated bottom panel of the layout() split (see render_danger_index).
# Distance factors are stored in Euclidean degree-space; converted here to
# an approximate miles figure using the mid-latitude average of a
# longitude-degree and a latitude-degree's real length -- a rough
# conversion, consistent with how distance is approximated elsewhere in
# this project (see DANGER_INDEX_METHODOLOGY.md), not a precise geodesic
# distance. Mirrors _draw_factor_summary() in danger_index_common.py.
.draw_factor_summary <- function(result, in_az, lat_mid) {
  miles_per_deg_lat <- 69.17
  miles_per_deg_lon <- 69.17 * abs(cos(lat_mid * pi / 180))
  miles_per_deg <- (miles_per_deg_lat + miles_per_deg_lon) / 2

  keep <- in_az & !is.na(result$composite)
  rows <- list(
    list("Ambient summer (July) temperature", result$july_tmax_c[keep], "C", 1),
    list("Distance to major city", result$dist_city_deg[keep] * miles_per_deg, "mi", 1),
    list("Distance to major road", result$dist_road_deg[keep] * miles_per_deg, "mi", 1),
    list("Distance to water source", result$dist_water_deg[keep] * miles_per_deg, "mi", 1),
    list("Slope", result$slope_deg[keep], "deg", 1),
    list("Vegetation density (NDVI)", result$ndvi[keep], "", 3)
  )

  lines <- sprintf("Danger index factors (n=%d grid cells within Arizona, min / mean / max):", sum(keep))
  for (row in rows) {
    name <- row[[1]]; values <- row[[2]]; unit <- row[[3]]; dp <- row[[4]]
    fmt <- sprintf("  %%-38s %%6.%df  /  %%6.%df  /  %%6.%df  %%s", dp, dp, dp)
    lines <- c(lines, sprintf(fmt, name, min(values), mean(values), max(values), unit))
  }

  plot.new()
  text(0, 1, paste(lines, collapse = "\n"), adj = c(0, 1), family = "mono", cex = 0.85)
}

render_danger_index <- function(out_filename = "figure2_reproduction_R.png",
                                 title = "Figure 2: Danger Index") {
  result <- compute_danger_index()
  n_nan <- sum(is.na(result$composite))
  cat(sprintf("  grid cells: %d (%d rows x %d cols)\n", length(result$composite), result$n_rows, result$n_cols))
  cat(sprintf("  composite index range: %.2f to %.2f (%d cells with missing slope and/or NDVI data, excluded)\n",
              min(result$composite, na.rm = TRUE), max(result$composite, na.rm = TRUE), n_nan))

  # Mask to cells within Arizona -- a full rectangular bbox would color
  # parts of Mexico/California/New Mexico that aren't meaningful here.
  state <- st_read(file.path(SHAPE_DIR, "tl_2021_us_state", "tl_2021_us_state.shp"), quiet = TRUE)
  az <- state[state$STATEFP == "04", ]
  pts <- st_as_sf(data.frame(lon = result$lon, lat = result$lat), coords = c("lon", "lat"), crs = st_crs(az))
  in_az <- as.logical(st_intersects(pts, az, sparse = FALSE)[, 1])

  fence <- load_fence_layers()

  lat_mid <- (BBOX$min_lat + BBOX$max_lat) / 2
  geo_aspect <- 1 / cos(lat_mid * pi / 180)
  lon_span <- BBOX$max_lon - BBOX$min_lon
  lat_span <- BBOX$max_lat - BBOX$min_lat
  fig_w_in <- 12
  map_h_in <- fig_w_in * (lat_span * geo_aspect) / lon_span
  # Extra vertical space reserved below the map for the factor-summary
  # table, drawn as a second layout() panel -- base R has no equivalent
  # of matplotlib's tight_layout() auto-reserving room for extra text, so
  # the panel split has to be done explicitly instead.
  summary_h_in <- 1.9
  fig_h_in <- map_h_in + summary_h_in

  out_path <- file.path(DATA_DIR, out_filename)
  png(out_path, width = fig_w_in, height = fig_h_in, units = "in", res = 200)
  layout(matrix(1:2, nrow = 2), heights = c(map_h_in, summary_h_in))
  par(mar = c(1, 1, 3, 1))
  plot(1, type = "n", xlim = c(BBOX$min_lon, BBOX$max_lon), ylim = c(BBOX$min_lat, BBOX$max_lat),
       asp = 1 / cos(lat_mid * pi / 180), xaxt = "n", yaxt = "n", xlab = "", ylab = "", bty = "o")
  title(main = title, cex.main = 1.3)

  # Danger index raster drawn FIRST -- unlike matplotlib, base R graphics
  # has no z-order; whatever is plotted later simply paints over whatever
  # came before. The boundary lines below need to render on TOP of the
  # raster fill, so they must be plotted after it, not before.
  vabs <- max(abs(result$composite[in_az]), na.rm = TRUE)
  half <- CELL_SIZE / 2
  keep <- in_az & !is.na(result$composite)
  frac <- (result$composite[keep] + vabs) / (2 * vabs)
  frac <- pmin(pmax(frac, 0), 1)
  cell_colors <- .danger_palette(101)[round(frac * 100) + 1]
  rect(result$lon[keep] - half, result$lat[keep] - half,
       result$lon[keep] + half, result$lat[keep] + half,
       col = cell_colors, border = NA)

  plot(st_geometry(az), add = TRUE, border = "grey30", lwd = 0.8, col = NA)
  roads <- st_read(file.path(SHAPE_DIR, "tl_2021_04_prisecroads", "tl_2021_04_prisecroads.shp"), quiet = TRUE)
  roads <- roads[roads$RTTYP %in% c("I", "U", "S"), ]
  plot(st_geometry(roads), add = TRUE, col = "grey15", lwd = 0.5)
  desert <- st_read(file.path(SHAPE_DIR, "deserts_sw", "deserts_sw.shp"), quiet = TRUE)
  desert <- desert[desert$NAME %in% c("Colorado Sonoran Desert", "Arizona Sonoran Desert"), ]
  desert <- st_transform(desert, 4326)
  plot(st_geometry(desert), add = TRUE, border = DESERT_BROWN, lwd = 1.6, lty = "44", col = NA)
  reservation <- st_read(file.path(SHAPE_DIR, "tl_2021_us_aiannh", "tl_2021_us_aiannh.shp"), quiet = TRUE)
  reservation <- reservation[reservation$NAMELSAD == "Tohono O'odham Nation Reservation", ]
  plot(st_geometry(reservation), add = TRUE, border = RESERVATION_PURPLE, lwd = 1.3, lty = "44", col = NA)

  water <- load_water_stations()
  points(water$longitude, water$latitude, pch = 17, col = WATER_STATION_COLOR, cex = 1.0)
  points(water$longitude, water$latitude, pch = 2, col = "black", cex = 1.0, lwd = 0.4)

  for (name in names(CITIES)) {
    xy <- CITIES[[name]]
    text(xy[1], xy[2], labels = name, cex = 0.65, adj = c(-0.1, -0.4))
  }

  draw_scale_bar(lon0 = -115.05, lat0 = 31.05, at_latitude = 32.0)
  draw_north_arrow(lon = -114.9, lat = 31.3)
  draw_cell_size_note(CELL_SIZE, lon = -115.05, lat = 30.95, reference_lat = lat_mid)

  n_swatches <- 5
  edges <- seq(-vabs, vabs, length.out = n_swatches + 1)
  swatch_labels <- character(n_swatches)
  swatch_colors <- character(n_swatches)
  for (i in seq_len(n_swatches)) {
    mid <- (edges[i] + edges[i + 1]) / 2
    frac_i <- min(max((mid + vabs) / (2 * vabs), 0), 1)
    swatch_colors[i] <- .danger_palette(101)[round(frac_i * 100) + 1]
    tag <- if (i == n_swatches) "  Most dangerous" else if (i == 1) "  Relatively least dangerous" else ""
    swatch_labels[i] <- sprintf("%+.1f to %+.1f%s", edges[i], edges[i + 1], tag)
  }

  legend_labels <- c(swatch_labels, sprintf("Water stations (n=%d)", nrow(water)),
                      "Arizona Sonoran Desert", "Tohono O'odham Nation Reservation")
  legend_pch <- c(rep(15, n_swatches), 17, NA, NA)
  legend_lty <- c(rep(NA, n_swatches), NA, "44", "44")
  legend_lwd <- c(rep(NA, n_swatches), NA, 1.6, 1.3)
  legend_col <- c(swatch_colors, WATER_STATION_COLOR, DESERT_BROWN, RESERVATION_PURPLE)

  legend("topright", legend = legend_labels, pch = legend_pch, pt.cex = 1.5,
         lty = legend_lty, lwd = legend_lwd, col = legend_col,
         title = "Danger Index (sum of 6 Z-scores)", title.font = 2, bty = "o", bg = "white", cex = 0.68)

  # Second layout() panel: factor-summary table.
  par(mar = c(0.2, 0.2, 0.2, 0.2))
  .draw_factor_summary(result, in_az, lat_mid)
  stamp <- sprintf("generated %s", format(Sys.time(), "%Y-%m-%d %H:%M:%S"))

  dev.off()
  cat("Saved plot to", out_path, "\n")
  cat(stamp, "\n")
  invisible(result)
}

# ---------------------------------------------------------------------------
# Figure 8: hot spots (both periods) overlaid on the danger index. R port
# of render_overlay_figure() in danger_index_common.py -- see that
# function's docstring for the full design rationale (two stacked panels
# rather than one combined map, unfilled outlined cells reusing
# hotspot_common's HOT_99/HOT_95 colors exactly, shared legend/summary).
# ---------------------------------------------------------------------------
.draw_danger_raster <- function(result, in_az, vabs) {
  half <- CELL_SIZE / 2
  keep <- in_az & !is.na(result$composite)
  frac <- pmin(pmax((result$composite[keep] + vabs) / (2 * vabs), 0), 1)
  cell_colors <- .danger_palette(101)[round(frac * 100) + 1]
  rect(result$lon[keep] - half, result$lat[keep] - half,
       result$lon[keep] + half, result$lat[keep] + half,
       col = cell_colors, border = NA)
}

.draw_hotspot_outlines <- function(gi) {
  half <- CELL_SIZE / 2
  is99 <- gi$gi_bin == 3
  is95 <- gi$gi_bin == 2
  if (any(is99)) {
    rect(gi$lon[is99] - half, gi$lat[is99] - half, gi$lon[is99] + half, gi$lat[is99] + half,
         col = NA, border = HOT_99, lwd = 2.2)
  }
  if (any(is95)) {
    rect(gi$lon[is95] - half, gi$lat[is95] - half, gi$lon[is95] + half, gi$lat[is95] + half,
         col = NA, border = HOT_95, lwd = 1.6)
  }
}

.draw_overlay_panel <- function(result, in_az, vabs, gi, fence, water, lat_mid, title, show_legend) {
  plot(1, type = "n", xlim = c(BBOX$min_lon, BBOX$max_lon), ylim = c(BBOX$min_lat, BBOX$max_lat),
       asp = 1 / cos(lat_mid * pi / 180), xaxt = "n", yaxt = "n", xlab = "", ylab = "", bty = "o")
  title(main = title, cex.main = 1.1)

  # Raster first, then boundaries, then hot-spot outlines -- base R paints
  # in call order (no z-order), so this ordering is what makes the
  # boundaries and outlines visible on top of the raster fill.
  .draw_danger_raster(result, in_az, vabs)

  state <- st_read(file.path(SHAPE_DIR, "tl_2021_us_state", "tl_2021_us_state.shp"), quiet = TRUE)
  az <- state[state$STATEFP == "04", ]
  plot(st_geometry(az), add = TRUE, border = "grey30", lwd = 0.8, col = NA)
  roads <- st_read(file.path(SHAPE_DIR, "tl_2021_04_prisecroads", "tl_2021_04_prisecroads.shp"), quiet = TRUE)
  roads <- roads[roads$RTTYP %in% c("I", "U", "S"), ]
  plot(st_geometry(roads), add = TRUE, col = "grey15", lwd = 0.5)
  desert <- st_read(file.path(SHAPE_DIR, "deserts_sw", "deserts_sw.shp"), quiet = TRUE)
  desert <- desert[desert$NAME %in% c("Colorado Sonoran Desert", "Arizona Sonoran Desert"), ]
  desert <- st_transform(desert, 4326)
  plot(st_geometry(desert), add = TRUE, border = DESERT_BROWN, lwd = 1.6, lty = "44", col = NA)
  reservation <- st_read(file.path(SHAPE_DIR, "tl_2021_us_aiannh", "tl_2021_us_aiannh.shp"), quiet = TRUE)
  reservation <- reservation[reservation$NAMELSAD == "Tohono O'odham Nation Reservation", ]
  plot(st_geometry(reservation), add = TRUE, border = RESERVATION_PURPLE, lwd = 1.3, lty = "44", col = NA)

  if (fence$have_fence) {
    for (gdf in fence$after)  if (nrow(gdf) > 0) plot(st_geometry(gdf), add = TRUE, col = FENCE_YELLOW, lwd = 2.0)
    for (gdf in fence$before) if (nrow(gdf) > 0) plot(st_geometry(gdf), add = TRUE, col = FENCE_BLUE, lwd = 2.0)
  }

  .draw_hotspot_outlines(gi)

  points(water$longitude, water$latitude, pch = 17, col = WATER_STATION_COLOR, cex = 1.0)
  points(water$longitude, water$latitude, pch = 2, col = "black", cex = 1.0, lwd = 0.4)
  for (name in names(CITIES)) {
    xy <- CITIES[[name]]
    text(xy[1], xy[2], labels = name, cex = 0.65, adj = c(-0.1, -0.4))
  }
  draw_scale_bar(lon0 = -115.05, lat0 = 31.05, at_latitude = 32.0)
  draw_north_arrow(lon = -114.9, lat = 31.3)
  draw_cell_size_note(CELL_SIZE, lon = -115.05, lat = 30.95, reference_lat = lat_mid)

  if (show_legend) {
    n_swatches <- 5
    edges <- seq(-vabs, vabs, length.out = n_swatches + 1)
    swatch_labels <- character(n_swatches)
    swatch_colors <- character(n_swatches)
    for (i in seq_len(n_swatches)) {
      mid <- (edges[i] + edges[i + 1]) / 2
      frac_i <- min(max((mid + vabs) / (2 * vabs), 0), 1)
      swatch_colors[i] <- .danger_palette(101)[round(frac_i * 100) + 1]
      tag <- if (i == n_swatches) "  Most dangerous" else if (i == 1) "  Relatively least dangerous" else ""
      swatch_labels[i] <- sprintf("%+.1f to %+.1f%s", edges[i], edges[i + 1], tag)
    }
    legend_labels <- c(swatch_labels, "Hot Spot - 99% Confidence", "Hot Spot - 95% Confidence",
                        sprintf("Water stations (n=%d)", nrow(water)))
    legend_pch <- c(rep(15, n_swatches), 0, 0, 17)
    legend_lty <- c(rep(NA, n_swatches), NA, NA, NA)
    legend_lwd <- c(rep(NA, n_swatches), 2.2, 1.6, NA)
    legend_col <- c(swatch_colors, HOT_99, HOT_95, WATER_STATION_COLOR)
    if (fence$have_fence) {
      legend_labels <- c(legend_labels, "Border built 2008 or later", "Border built 2007 or before")
      legend_pch    <- c(legend_pch, NA, NA)
      legend_lty    <- c(legend_lty, "solid", "solid")
      legend_lwd    <- c(legend_lwd, 2.0, 2.0)
      legend_col    <- c(legend_col, FENCE_YELLOW, FENCE_BLUE)
    }
    legend_labels <- c(legend_labels, "Arizona Sonoran Desert", "Tohono O'odham Nation Reservation")
    legend_pch    <- c(legend_pch, NA, NA)
    legend_lty    <- c(legend_lty, "44", "44")
    legend_lwd    <- c(legend_lwd, 1.6, 1.3)
    legend_col    <- c(legend_col, DESERT_BROWN, RESERVATION_PURPLE)

    legend("topright", legend = legend_labels, pch = legend_pch, pt.cex = 1.3,
           lty = legend_lty, lwd = legend_lwd, col = legend_col,
           title = "Danger Index (sum of 6 Z-scores) + Hot Spots", title.font = 2, bty = "o", bg = "white", cex = 0.58)
  }
}

render_overlay_figure <- function(out_filename = "figure8_reproduction_R.png",
                                   title_pre = "Figure 8a: Danger Index and Hot Spots, Pre-SFA (2000-2007)",
                                   title_post = "Figure 8b: Danger Index and Hot Spots, Post-SFA (2008-2019)") {
  result <- compute_danger_index()

  state <- st_read(file.path(SHAPE_DIR, "tl_2021_us_state", "tl_2021_us_state.shp"), quiet = TRUE)
  az <- state[state$STATEFP == "04", ]
  pts <- st_as_sf(data.frame(lon = result$lon, lat = result$lat), coords = c("lon", "lat"), crs = st_crs(az))
  in_az <- as.logical(st_intersects(pts, az, sparse = FALSE)[, 1])
  vabs <- max(abs(result$composite[in_az]), na.rm = TRUE)

  deaths <- load_deaths()
  pre_cells <- build_grid_counts(deaths$Longitude[deaths$is_pre_sfa], deaths$Latitude[deaths$is_pre_sfa],
                                  CELL_SIZE, BBOX$min_lon, BBOX$min_lat)
  post_cells <- build_grid_counts(deaths$Longitude[deaths$is_post_sfa], deaths$Latitude[deaths$is_post_sfa],
                                   CELL_SIZE, BBOX$min_lon, BBOX$min_lat)
  pre_gi <- compute_gi_star(pre_cells, CELL_SIZE, BBOX$min_lon, BBOX$min_lat)
  post_gi <- compute_gi_star(post_cells, CELL_SIZE, BBOX$min_lon, BBOX$min_lat)
  cat(sprintf("  pre-SFA:  %d grid cells, Gi_Bin counts: %s\n", pre_gi$n_cells,
              paste(names(table(pre_gi$gi_bin)), table(pre_gi$gi_bin), sep = "=", collapse = ", ")))
  cat(sprintf("  post-SFA: %d grid cells, Gi_Bin counts: %s\n", post_gi$n_cells,
              paste(names(table(post_gi$gi_bin)), table(post_gi$gi_bin), sep = "=", collapse = ", ")))

  fence <- load_fence_layers()
  water <- load_water_stations()

  lat_mid <- (BBOX$min_lat + BBOX$max_lat) / 2
  geo_aspect <- 1 / cos(lat_mid * pi / 180)
  lon_span <- BBOX$max_lon - BBOX$min_lon
  lat_span <- BBOX$max_lat - BBOX$min_lat
  fig_w_in <- 12
  panel_h_in <- fig_w_in * (lat_span * geo_aspect) / lon_span
  summary_h_in <- 1.9
  fig_h_in <- panel_h_in * 2 + summary_h_in

  out_path <- file.path(DATA_DIR, out_filename)
  png(out_path, width = fig_w_in, height = fig_h_in, units = "in", res = 200)
  layout(matrix(1:3, nrow = 3), heights = c(panel_h_in, panel_h_in, summary_h_in))

  par(mar = c(1, 1, 2.5, 1))
  .draw_overlay_panel(result, in_az, vabs, pre_gi, fence, water, lat_mid, title_pre, show_legend = TRUE)
  .draw_overlay_panel(result, in_az, vabs, post_gi, fence, water, lat_mid, title_post, show_legend = FALSE)

  par(mar = c(0.2, 0.2, 0.2, 0.2))
  .draw_factor_summary(result, in_az, lat_mid)
  stamp <- sprintf("generated %s", format(Sys.time(), "%Y-%m-%d %H:%M:%S"))

  dev.off()
  cat("Saved plot to", out_path, "\n")
  cat(stamp, "\n")
  invisible(list(pre = pre_gi, post = post_gi, danger_index = result))
}
