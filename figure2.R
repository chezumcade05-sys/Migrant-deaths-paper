# Reproduce Figure 2 from Bansak, Blanco, Coon & Dieringer (2025),
# "Border Walls and Death on the US-Mexico Border": the danger index map --
# but with a rebuilt index using different factors and a different scoring
# method than the paper's original. See DANGER_INDEX_METHODOLOGY.md for the
# full write-up of what changed and why.
#
# R port of figure2.py.
# Requires the "sf" package: install.packages("sf")
# To run: Rscript figure2.R

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

render_danger_index(
  out_filename = "figure2_reproduction_R.png",
  title = "Figure 2: Danger Index"
)
