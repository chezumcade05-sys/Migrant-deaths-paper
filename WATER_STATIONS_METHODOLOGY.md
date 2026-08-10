# Water Station Data: Source, Extraction Method, and Uncertainty

`Water Stations 2000-2019.csv` (used by all six figure scripts, in both the
Python and R versions, regardless of period) is **not** survey data and was
**not** provided with the paper's original files. It was extracted by
Claude from a public poster published by Humane Borders, the same
organization that is the paper's own source for the migrant-death data.
This document explains exactly how, so the coordinates can be checked
rather than taken on faith — and also documents an earlier, separate
extraction (from a 2000-2007 poster) that was tried, found less reliable,
and dropped in favor of using this single dataset everywhere.

## 1. Source

Humane Borders publishes combined "Migrant Deaths, Rescue Beacons, Water
Stations" posters on their [Printable Maps & Posters](https://www.humaneborders.org/newpage)
page.

| File | Poster | Status |
|---|---|---|
| `Water Stations 2000-2019.csv` | `deathpostercumulative_2019_stewardship_mid.pdf` | **In use**, for every figure |
| ~~`Water Stations 2000-2007.csv`~~ | `cumulativemap20002007.pdf` | Tried, found less reliable, **removed** — see §5 |

Both are PDFs Humane Borders explicitly permits reproducing, with credit.
The rest of this document describes both extractions, since understanding
why the 2007 one was dropped is part of the record for the one still in use.

## 2. Why extraction was possible at all

Both PDFs turned out to be **vector** exports from GIS software (ArcMap),
not flattened images. Every marker on the map — death, water station,
border crossing — is a real drawn object (or, in the 2019 poster, a
placed text glyph from a custom point-symbol font) sitting at a specific
(x, y) position on the PDF page, in PDF's own internal coordinate space (points, not
degrees). Two different technical encodings were involved:

- **2007 poster**: markers are vector paths. Water stations turned out to
  be small solid shapes filled with a single consistent color
  (`RGB(0, 0.53, 1.0)`, a saturated blue), distinguishable by that fill
  color from every other layer on the map.
- **2019 poster**: markers are single Unicode-range characters rendered in
  an `ESRIAMFMElectric`/`ESRIDefaultMarker` symbol font, positioned like
  ordinary text. The poster's own legend (extracted as plain text) gave an
  explicit key: `¼ = Water Stations`, `!( = Migrant Deaths`,
  `#* = US Border Crossings` — so the correct glyph/font/color combination
  didn't have to be guessed, it was read directly off the map.

## 3. Converting PDF page coordinates to real longitude/latitude

Neither poster's marker positions are already in geographic coordinates —
they're in the PDF page's own point-based coordinate system. To convert:

1. Extracted the pixel positions of ~8-12 city name labels already printed
   on each poster (Tucson, Nogales, Phoenix, Sasabe, Naco, Douglas, Sells,
   Ajo, and — 2019 poster only — Yuma, Lukeville, Bisbee, Arivaca).
2. Paired each label's PDF position with that city's real, well-known
   longitude/latitude.
3. Fit a 6-parameter affine transform (least squares) mapping PDF
   coordinates to (longitude, latitude) from those control points.
4. Applied that transform to every water-station marker's PDF position.

This is the same general idea as georeferencing a scanned map, just against
labels already on the page instead of a separate reference grid.

## 4. Quantified uncertainty

The affine fit's residuals at the calibration points (i.e., how far off the
predicted position was for each city, whose *true* position is known)
give a direct measure of accuracy:

| Poster | Mean residual | Max residual |
|---|---|---|
| 2007 poster | ~0.06° (~3.6 mi) | ~0.16° (~9.7 mi) |
| 2019 poster | ~0.09° (~5.6 mi) | ~0.16° (~9.7 mi) |

**In short: individual water station positions should be trusted to
roughly ±5 miles, not treated as survey-grade.** Two things contribute to
this: (a) the affine transform is a single best-fit correction applied
uniformly across the whole map, so any real printing/projection distortion
that varies across the page isn't fully captured, and (b) city text labels
are typically drawn with a small, not-perfectly-consistent offset from the
exact point they label. This is precise enough to show *which corridor* a
station is in and its position relative to the death clusters, but not
precise enough for anything requiring exact GPS coordinates.

The legend swatch shown in the map's own key counts as a "marker" to a
naive extraction and had to be explicitly excluded — both posters placed
one extra marker glyph directly in their legend box (visually obvious as an
outlier far from the real geographic cluster, e.g. at longitude -114.5 when
every real station was between -113.3 and -109.6). Both were caught and
removed by inspecting the extracted point cloud for outliers before saving
the final CSVs — 47 real stations remain in each file, not 48.

## 5. Why the 2007 extraction was dropped

Both files were originally used: 2007 for the pre-SFA figures (4, 6), 2019
for post-SFA/all-data figures (3, 5, 7, and the extra hot-spot figure).
Two problems surfaced with the 2007 one, and it's been retired in favor of
using the 2019 extraction for every figure regardless of period:

**Points south of the border.** Humane Borders only operates in Arizona,
USA — there are no real water stations south of the international line.
That's a hard constraint the extracted data can be checked against
directly, and it caught a real problem: **11 of the 47 points in the 2007
extraction** landed south of 31°20'N (31.3333°), the exact surveyed
AZ-Mexico boundary latitude for the longitude range they fell in (-109.57
to -109.83, the Naco/Douglas corridor — this stretch of the border is a
straight parallel of latitude, a fixed historical fact from the Gadsden
Purchase survey, not an approximation). These were correctable (snapped to
31.34°N, just north of the line) and initially were corrected in place —
but their existence was itself a signal of a less trustworthy source
extraction. The 2019 extraction had **zero** such violations from the start.

**Large disagreement with the 2019 set.** A direct comparison found the
average distance between a 2007-set station and its nearest 2019-set
counterpart is **~29 miles** — only 2 of 47 stations had a near-identical
match — far larger than the ~5 mile calibration uncertainty from §4 alone
would explain. Some of that could reflect a real network change over 12
years, but combined with the border violations above and a user's direct
visual comparison against the real map (the 2019/Figure 7 version was
judged noticeably more accurate), it pointed to the 2007 poster extraction
being meaningfully less reliable, not just differently-dated.

**Decision:** rather than keep two datasets of uneven trustworthiness in
use, `Water Stations 2000-2007.csv` was removed from the project and every
figure now uses `Water Stations 2000-2019.csv`, regardless of which period
(pre- or post-SFA) that figure otherwise shows.

## 6. Other known limitations

- **This is a snapshot, not a live feed.** The file reflects whatever
  network existed when the 2019 poster was made; it is not a historically
  exact record of which stations existed in which specific year, and it's
  used as-is even for the pre-SFA figures (4, 6), which show an earlier
  period than the poster's own vintage.
- **No station metadata** (name, install date, active/decommissioned
  status) was extracted, only coordinates — the poster PDFs don't encode
  that information for the water-station layer the way the fence
  geodatabase encodes install dates.
- **Not yet used for any quantitative analysis** (e.g., distance-to-
  nearest-water-station). Currently these points are a visual reference
  layer only, added to the existing figures. Any future quantitative use
  (e.g., as an input to a reconstructed danger index) should account for
  the ±5 mile positional uncertainty explicitly, since it's large enough to
  matter for that kind of measurement.

## 7. How to verify this independently

The extraction logic (PyMuPDF-based: locate marker glyphs/shapes by
font+color, locate city label text, fit the affine transform, apply it) was
exploratory work done in a scratch session and isn't currently saved as a
script in this project. If you want to re-derive or audit the coordinates,
the source PDFs are public at the URLs in §1, and the method in §§2-4 above
is a complete enough recipe to reproduce independently.
