# Reproduce Figure 7 from Bansak, Blanco, Coon & Dieringer (2025),
# "Border Walls and Death on the US-Mexico Border":
#     Figure 7. Hot-Spot Analysis, 2008-2019 (post-Secure Fence Act)
#
# R port of figure7.py. Applies the from-scratch Getis-Ord Gi* hot-spot
# analysis (see hotspot_common.R) to the same post-SFA death points used in
# figure5.R, plotted on the same base layer as figure3/4/5.R.
#
# See "Claude Hotspot documentation.md" for the full statistical write-up.
# Requires the "sf" package: install.packages("sf")
# To run (from the repo root): Rscript r/figure7.R

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
subset <- deaths[deaths$is_post_sfa, ]
cat(sprintf("Post-SFA (2008-2019) deaths in this extract: %d\n", nrow(subset)))

render_hotspot_figure(
  deaths_subset = subset,
  death_label = "Location of Remains 2008-2019",
  title = "Figure 7: Hot-Spot Analysis, 2008-2019",
  out_filename = "figure7_reproduction_R.png"
)
