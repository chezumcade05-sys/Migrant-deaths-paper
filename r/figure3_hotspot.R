# Hot-spot analysis of the complete 2000-2019 migrant death dataset (the
# same points used in figure3.R). There is no directly corresponding
# numbered figure in Bansak, Blanco, Coon & Dieringer (2025) -- the paper
# only runs this analysis split by pre-/post-SFA period (Figures 6 and 7,
# reproduced in figure6.R / figure7.R) -- but the same Getis-Ord Gi* method
# (see hotspot_common.R) is applied here to the full dataset for comparison.
#
# R port of figure3_hotspot.py.
# See "Claude Hotspot documentation.md" for the full statistical write-up.
# Requires the "sf" package: install.packages("sf")
# To run (from the repo root): Rscript r/figure3_hotspot.R

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

deaths <- load_deaths()
subset <- deaths[deaths$is_pre_sfa | deaths$is_post_sfa, ]
cat(sprintf("All deaths, 2000-2019, in this extract: %d\n", nrow(subset)))

render_hotspot_figure(
  deaths_subset = subset,
  death_label = "Location of Remains 2000-2019",
  title = "Hot-Spot Analysis (no paper equivalent): Migrant Deaths, 2000-2019",
  out_filename = "figure3_hotspot_reproduction_R.png"
)
