# Reproduce Figure 8 from Bansak, Blanco, Coon & Dieringer (2025),
# "Border Walls and Death on the US-Mexico Border": the danger index
# overlaid with the hot-spot analysis results -- extended to show both the
# pre-SFA and post-SFA hot spots as two stacked panels. See
# render_overlay_figure()'s comments in danger_index_common.R for the
# design rationale, and figure8.py for the Python version (kept
# functionally identical).
#
# Requires the "sf" package: install.packages("sf")
# To run: Rscript figure8.R

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
source(file.path(SCRIPT_DIR, "hotspot_common.R"))
source(file.path(SCRIPT_DIR, "danger_index_common.R"))

render_overlay_figure(out_filename = "figure8_reproduction_R.png")
