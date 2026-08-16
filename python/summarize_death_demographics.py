"""
Generates the paper's Table 4 ("Sample of Summary Statistics") -- gender,
age group, and cause-of-death breakdowns by Total/pre-SFA/post-SFA --
computed directly from data/Original death data.csv using this project's
validated pre-/post-SFA classification (basemap_common.load_deaths()).

Not part of the figure-rendering pipeline -- a reporting utility, re-run
whenever the underlying death-records CSV changes (e.g. new records added
in a future data pull) so this table doesn't drift out of sync.

Writes docs/table4_summary_statistics.csv and prints the table as
Markdown. See build_table4_docx.py for the publication-formatted version.

To run (from the repo root): .venv/bin/python python/summarize_death_demographics.py
"""

import os
import sys
from pathlib import Path

_VENV_DIR = Path(__file__).resolve().parent.parent / ".venv"
_VENV_PYTHON = _VENV_DIR / "bin" / "python"
if _VENV_PYTHON.exists() and Path(sys.prefix).resolve() != _VENV_DIR.resolve():
    os.execv(str(_VENV_PYTHON), [str(_VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

import numpy as np

import basemap_common as bc


def pct(n, total):
    return f"{n:,} ({round(100 * n / total):.0f}%)"


def build_rows():
    deaths = bc.load_deaths()
    groups = {
        "total": deaths[deaths["is_pre_sfa"] | deaths["is_post_sfa"]],
        "before": deaths[deaths["is_pre_sfa"]],
        "after": deaths[deaths["is_post_sfa"]],
    }
    n = {k: len(v) for k, v in groups.items()}

    def gender_row(sex_filter):
        return {k: pct(int(sex_filter(g)), n[k]) for k, g in groups.items()}

    def age_row(age_filter):
        return {k: pct(int(age_filter(g["Age"])), n[k]) for k, g in groups.items()}

    def cod_row(cod_filter):
        return {k: pct(int(cod_filter(g["Cause of Death"].str.lower())), n[k]) for k, g in groups.items()}

    rows = {
        "n": n,
        "male": gender_row(lambda g: (g["Sex"].str.lower() == "male").sum()),
        "female": gender_row(lambda g: (g["Sex"].str.lower() == "female").sum()),
        "gender_unknown": gender_row(lambda g: (~g["Sex"].str.lower().isin(["male", "female"])).sum()),
        "under18": age_row(lambda a: (a < 18).sum()),
        "age_18_30": age_row(lambda a: ((a >= 18) & (a <= 30)).sum()),
        "over30": age_row(lambda a: (a > 30).sum()),
        "age_unknown": age_row(lambda a: a.isna().sum()),
        "exposure": cod_row(lambda c: (c == "exposure").sum()),
        "blunt_force": cod_row(lambda c: (c == "blunt force injury").sum()),
        "undetermined": cod_row(lambda c: c.isin(["undetermined", "skeletal remains"]).sum()),
    }
    rows["other_cod"] = {
        k: pct(n[k] - int(groups[k]["Cause of Death"].str.lower().eq("exposure").sum())
               - int(groups[k]["Cause of Death"].str.lower().eq("blunt force injury").sum())
               - int(groups[k]["Cause of Death"].str.lower().isin(["undetermined", "skeletal remains"]).sum()),
               n[k])
        for k in groups
    }
    years = {"total": 20, "before": 8, "after": 12}
    rows["avg_per_year"] = {k: round(n[k] / years[k]) for k in groups}
    return n, rows


def main():
    n, rows = build_rows()
    print(f"\n## Table 4: Sample of Summary Statistics (Total N={n['total']:,}, "
          f"Before N={n['before']:,}, After N={n['after']:,})\n")
    print("| Characteristic | Total | Before (2000-2007) | After (2008-2019) |")
    print("|---|---|---|---|")
    labels = {
        "male": "Male", "female": "Female", "gender_unknown": "Unknown (gender)",
        "under18": "Under 18", "age_18_30": "18-30", "over30": "Over 30", "age_unknown": "Unknown (age)",
        "exposure": "Exposure", "blunt_force": "Blunt force injury",
        "undetermined": "Undetermined/skeletal remains", "other_cod": "Other",
    }
    for key, label in labels.items():
        r = rows[key]
        print(f"| {label} | {r['total']} | {r['before']} | {r['after']} |")
    print(f"| Total reported deaths | {n['total']:,} | {n['before']:,} ({round(100*n['before']/n['total'])}%) "
          f"| {n['after']:,} ({round(100*n['after']/n['total'])}%) |")
    a = rows["avg_per_year"]
    print(f"| Average deaths per year | {a['total']} | {a['before']} | {a['after']} |")

    out_path = bc.REPO_ROOT / "docs" / "table4_summary_statistics.csv"
    lines = ["characteristic,total,before,after"]
    for key, label in labels.items():
        r = rows[key]
        lines.append(f'"{label}",{r["total"]},{r["before"]},{r["after"]}')
    lines.append(f'"Total reported deaths",{n["total"]},{n["before"]},{n["after"]}')
    lines.append(f'"Average deaths per year",{a["total"]},{a["before"]},{a["after"]}')
    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
