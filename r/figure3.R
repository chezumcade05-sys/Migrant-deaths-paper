# Reproduce Figure 3 from Bansak, Blanco, Coon & Dieringer (2025),
# "Border Walls and Death on the US-Mexico Border":
#     Figure 3. Migrant Deaths, 2000-2019 (complete data set)
#
# R port of figure3.py -- shares its base layer with figure4.R/figure5.R via
# basemap_common.R. See README.md for the full pipeline description.
#
# Requires the "sf" package: install.packages("sf")
# To run (from the repo root): Rscript r/figure3.R

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
subset <- deaths[deaths$is_pre_sfa | deaths$is_post_sfa, ]
cat(sprintf("All deaths, 2000-2019, in this extract: %d\n", nrow(subset)))
if (nrow(subset) != 3041) {
  cat("NOTE: this does not match the paper's reported 3,041 -- the CSV\n",
      "may have been updated with additional records since the paper's\n",
      "data pull. Check the count above against Table 4.\n")
}

render_figure(
  deaths_subset = subset,
  death_label = "Location of Remains 2000-2019",
  title = "Figure 3: Migrant Deaths, 2000-2019",
  out_filename = "figure3_reproduction_R.png"
)
