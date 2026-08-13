# Getis-Ord Gi* hot-spot analysis, implemented from scratch (no ArcGIS, no
# spatial-stats package), for reproducing Figures 6 and 7 from Bansak,
# Blanco, Coon & Dieringer (2025), plus the same analysis applied to the
# complete 2000-2019 dataset. This is an R port of hotspot_common.py, kept
# functionally identical -- same formula, same parameter choices, same
# grid/distance-band calibration -- so results match between the two
# languages.
#
# See "Claude Hotspot documentation.md" for the full statistical write-up:
# what's computed, why these specific parameter choices, and where this
# reproduction is known to diverge from the paper's original ArcGIS
# "Optimized Hot Spot Analysis" output.
#
# Not run directly -- figure6.R / figure7.R / figure3_hotspot.R source()
# this file (which itself sources basemap_common.R).

# Colors sampled directly from the original Figures 6/7 legend swatches.
HOT_99 <- "#d62f29"
HOT_95 <- "#ed7553"
# Not part of the original figures (which only show the two tiers above) --
# a paler continuation of the same red family, for cells with a recorded
# death that didn't reach 95%/99% significance.
NOT_SIGNIFICANT <- "#f9ddd2"

# Shared grid cell size (degrees) used for all three analyses -- see the
# methodology write-up for how this was derived and why it's fixed rather
# than auto-computed per dataset.
CELL_SIZE <- 0.044

# Esri's own documented rule of thumb for choosing a default fixed distance
# band: pick the smallest distance such that, on average, each feature has
# at least this many neighbors.
TARGET_AVG_NEIGHBORS <- 8.0

FDR_LEVELS <- c(0.10, 0.05, 0.01)  # -> Gi_Bin +-1, +-2, +-3

# ---------------------------------------------------------------------------
# Step 1: aggregate points into a grid, keeping only populated cells (this
# matches the original ArcGIS output, whose feature count -- 629 pre-SFA,
# 780 post-SFA -- is far smaller than a full-coverage fishnet would produce,
# meaning empty cells were excluded before running Gi*).
# ---------------------------------------------------------------------------
build_grid_counts <- function(lons, lats, cell_size, origin_lon, origin_lat) {
  col <- floor((lons - origin_lon) / cell_size)
  row <- floor((lats - origin_lat) / cell_size)
  key <- paste(row, col, sep = "_")
  tab <- table(key)
  keys <- names(tab)
  parts <- strsplit(keys, "_")
  data.frame(
    row = as.integer(vapply(parts, `[`, character(1), 1)),
    col = as.integer(vapply(parts, `[`, character(1), 2)),
    count = as.numeric(tab),
    stringsAsFactors = FALSE
  )
}

# ---------------------------------------------------------------------------
# Step 2: choose a fixed distance band (in degrees) via Esri's "average N
# neighbors" heuristic, then compute Getis-Ord Gi* for every populated cell.
# ---------------------------------------------------------------------------
.calibrate_distance_band <- function(D, target_avg_neighbors = TARGET_AVG_NEIGHBORS) {
  avg_neighbors_at <- function(radius) mean(rowSums(D <= radius)) - 1  # exclude self
  lo <- 1e-4; hi <- max(D)
  for (i in seq_len(50)) {
    mid <- (lo + hi) / 2
    if (avg_neighbors_at(mid) < target_avg_neighbors) lo <- mid else hi <- mid
  }
  (lo + hi) / 2
}

# Two-tailed p-value from a standard-normal Z-score. R's built-in pnorm()
# gives the exact normal CDF directly (no need for the manual erf-based
# formula the Python version uses to avoid a scipy dependency).
.norm_sf_two_tailed <- function(z) 2 * (1 - pnorm(abs(z)))

# Benjamini-Hochberg critical p-value for false discovery rate q.
.bh_fdr_threshold <- function(pvalues, q) {
  m <- length(pvalues)
  sp <- sort(pvalues)
  k <- seq_len(m)
  ok <- sp <= (k / m) * q
  if (any(ok)) max(sp[ok]) else 0.0
}

compute_gi_star <- function(cells, cell_size, origin_lon, origin_lat) {
  n <- nrow(cells)
  xs <- origin_lon + (cells$col + 0.5) * cell_size
  ys <- origin_lat + (cells$row + 0.5) * cell_size
  vals <- cells$count

  dx <- outer(xs, xs, "-")
  dy <- outer(ys, ys, "-")
  D <- sqrt(dx^2 + dy^2)
  radius <- .calibrate_distance_band(D)
  W <- (D <= radius) * 1.0  # binary weights, self-inclusive (Gi*)
  Wsum <- rowSums(W)

  xbar <- mean(vals)
  s <- sqrt(mean(vals^2) - xbar^2)
  sum_wx <- as.vector(W %*% vals)
  denom <- s * sqrt(Wsum * (n - Wsum) / (n - 1))
  Z <- ifelse(denom == 0, 0, (sum_wx - xbar * Wsum) / denom)
  P <- .norm_sf_two_tailed(Z)

  thresholds <- setNames(vapply(FDR_LEVELS, function(q) .bh_fdr_threshold(P, q), numeric(1)), as.character(FDR_LEVELS))

  classify <- function(z, p) {
    if (z > 0) {
      if (p <= thresholds["0.01"]) return(3)
      if (p <= thresholds["0.05"]) return(2)
      if (p <= thresholds["0.1"])  return(1)
    } else if (z < 0) {
      if (p <= thresholds["0.01"]) return(-3)
      if (p <= thresholds["0.05"]) return(-2)
      if (p <= thresholds["0.1"])  return(-1)
    }
    0
  }
  gi_bin <- mapply(classify, Z, P)

  list(lon = xs, lat = ys, count = vals, z = Z, p = P, gi_bin = gi_bin,
       distance_band_deg = radius, avg_neighbors = mean(Wsum) - 1,
       n_cells = n, fdr_thresholds = thresholds)
}

# ---------------------------------------------------------------------------
# Step 3: render, reusing the exact same basemap layers as figure3/4/5.R.
# ---------------------------------------------------------------------------
render_hotspot_figure <- function(deaths_subset, death_label, title, out_filename) {
  water <- load_water_stations()
  cells <- build_grid_counts(deaths_subset$Longitude, deaths_subset$Latitude,
                              CELL_SIZE, BBOX$min_lon, BBOX$min_lat)
  result <- compute_gi_star(cells, CELL_SIZE, BBOX$min_lon, BBOX$min_lat)
  cat(sprintf("  grid cells: %d, distance band: %.4f deg (avg neighbors: %.1f)\n",
              result$n_cells, result$distance_band_deg, result$avg_neighbors))
  cat("  Gi_Bin counts:", paste(names(table(result$gi_bin)), table(result$gi_bin), sep = "=", collapse = ", "), "\n")

  fence <- load_fence_layers()

  lat_mid <- (BBOX$min_lat + BBOX$max_lat) / 2
  geo_aspect <- 1 / cos(lat_mid * pi / 180)
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

  # Hot-spot grid cells. The original figures only fill the 95%/99% tiers;
  # this reproduction additionally shows every other populated cell (a
  # death was recorded there, just not part of a statistically significant
  # cluster) in a pale tint of the same color family, so no data is hidden.
  half <- CELL_SIZE / 2
  cell_color <- ifelse(result$gi_bin == 3, HOT_99,
                 ifelse(result$gi_bin == 2, HOT_95, NOT_SIGNIFICANT))
  rect(result$lon - half, result$lat - half, result$lon + half, result$lat + half,
       col = cell_color, border = NA)

  # Water stations -- not part of the original figures; see
  # WATER_STATIONS_METHODOLOGY.md for source and positional uncertainty.
  points(water$longitude, water$latitude, pch = 17, col = WATER_STATION_COLOR, cex = 1.1)
  points(water$longitude, water$latitude, pch = 2, col = "black", cex = 1.1, lwd = 0.4)

  draw_cities()
  draw_scale_bar(lon0 = -115.05, lat0 = 31.05, at_latitude = 32.0)
  draw_north_arrow(lon = -114.9, lat = 31.3)
  draw_cell_size_note(CELL_SIZE, lon = -115.05, lat = 30.95, reference_lat = lat_mid)

  # Filled-square swatches (pch=15) for the hot-spot tiers, mixed with line
  # swatches for the boundary/fence layers -- same single-vector-set pattern
  # as basemap_common.R's render_figure() legend, which mixes point and
  # line entries cleanly in one legend() call.
  legend_labels <- c("Hot Spot - 99% Confidence", "Hot Spot - 95% Confidence", "Death Recorded - Not Significant",
                      sprintf("Water stations (~2019, n=%d, ±~5mi)", nrow(water)))
  legend_pch    <- c(15, 15, 15, 17)
  legend_lty    <- c(NA, NA, NA, NA)
  legend_lwd    <- c(NA, NA, NA, NA)
  legend_col    <- c(HOT_99, HOT_95, NOT_SIGNIFICANT, WATER_STATION_COLOR)
  if (fence$have_fence) {
    legend_labels <- c(legend_labels, "Border built 2008 or later", "Border built 2007 or before")
    legend_pch    <- c(legend_pch, NA, NA)
    legend_lty    <- c(legend_lty, "solid", "solid")
    legend_lwd    <- c(legend_lwd, 2.4, 2.4)
    legend_col    <- c(legend_col, FENCE_YELLOW, FENCE_BLUE)
  }
  legend_labels <- c(legend_labels, "Arizona Sonoran Desert", "Tohono O'odham Nation Reservation")
  legend_pch    <- c(legend_pch, NA, NA)
  legend_lty    <- c(legend_lty, "44", "44")
  legend_lwd    <- c(legend_lwd, 1.6, 1.3)
  legend_col    <- c(legend_col, DESERT_BROWN, RESERVATION_PURPLE)

  legend("topright", legend = legend_labels, pch = legend_pch, pt.cex = 1.8,
         lty = legend_lty, lwd = legend_lwd, col = legend_col,
         title = "Legend", title.font = 2, bty = "o", bg = "white", cex = 0.75)

  stamp <- sprintf("generated %s", format(Sys.time(), "%Y-%m-%d %H:%M:%S"))

  dev.off()
  cat("Saved plot to", out_path, "\n")
  cat(stamp, "\n")
  invisible(result)
}
