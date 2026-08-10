# Reproduce Figure 5 from Bansak, Blanco, Coon & Dieringer (2025),
# "Border Walls and Death on the US-Mexico Border":
#     Figure 5. Migrant Deaths, 2008-2019 (post-Secure Fence Act)
#
# R port of figure5.py -- shares its base layer with figure3.R/figure4.R via
# basemap_common.R. See README.md for the full pipeline description.
#
# Note: the original figure's legend reads "Location of Remains 2008-2020",
# but the paper's own Table 4 defines the post-SFA window as 2008-2019 (12
# years, excluding blank-postmortem records) -- this script matches Table 4
# for consistency with figure3.R/figure4.R, same as the Python version.
#
# Requires the "sf" package: install.packages("sf")
# To run: Rscript figure5.R

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
subset <- deaths[deaths$is_post_sfa, ]
cat(sprintf("Post-SFA (2008-2019) deaths in this extract: %d\n", nrow(subset)))
if (nrow(subset) != 1826) {
  cat("NOTE: this does not match the paper's reported 1,826 -- the CSV\n",
      "may have been updated with additional records since the paper's\n",
      "data pull. Check the count above against Table 4.\n")
}

render_figure(
  deaths_subset = subset,
  death_label = "Location of Remains 2008-2019",
  title = "Figure 5: Migrant Deaths, 2008-2019",
  out_filename = "figure5_reproduction_R.png"
)
