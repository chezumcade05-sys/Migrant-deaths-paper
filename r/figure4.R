# Reproduce Figure 4 from Bansak, Blanco, Coon & Dieringer (2025),
# "Border Walls and Death on the US-Mexico Border":
#     Figure 4. Migrant Deaths, 2000-2007 (pre-Secure Fence Act)
#
# R port of figure4.py -- shares its base layer with figure3.R/figure5.R via
# basemap_common.R, and produces the same n counts / classification as the
# Python version. See README.md for the full pipeline description.
#
# Requires the "sf" package: install.packages("sf")
#
# To run (from the repo root): Rscript r/figure4.R
#   (or open in RStudio and click Source -- either way, the script locates
#   its own folder automatically, so your working directory doesn't matter)

.get_script_dir <- function() {
  cmd_args <- commandArgs(trailingOnly = FALSE)
  file_flag <- "--file="
  m <- grep(file_flag, cmd_args)
  if (length(m) > 0) return(dirname(normalizePath(sub(file_flag, "", cmd_args[m]))))
  rp <- tryCatch({
    if (requireNamespace("rstudioapi", quietly = TRUE) && rstudioapi::isAvailable())
      rstudioapi::getActiveDocumentContext()$path else NULL
  }, error = function(e) NULL)
  if (!is.null(rp) && nzchar(rp)) return(dirname(normalizePath(rp)))
  getwd()
}
SCRIPT_DIR <- .get_script_dir()
source(file.path(SCRIPT_DIR, "basemap_common.R"))

deaths <- load_deaths()
subset <- deaths[deaths$is_pre_sfa, ]
cat(sprintf("Pre-SFA (2000-2007) deaths in this extract: %d\n", nrow(subset)))
if (nrow(subset) != 1215) {
  cat("NOTE: this does not match the paper's reported 1,215 -- the CSV\n",
      "may have been updated with additional records since the paper's\n",
      "data pull. Check the count above against Table 4.\n")
}

render_figure(
  deaths_subset = subset,
  death_label = "Location of Remains 2000-2007",
  title = "Figure 4: Migrant Deaths, 2000-2007",
  out_filename = "figure4_reproduction_R.png"
)
