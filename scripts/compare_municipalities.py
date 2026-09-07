"""
compare_municipalities.py  (scripts/)
-------------------------------------
Ställer flera körningar sida vid sida och relaterar uppgiftsrummets TUNNHET
till arbetsmarknadens utfall.

Bakgrund. Hypotesen i papper 4 är att en kommun vars jobb täcker en gles
delmängd av uppgiftsrummet absorberar strukturförändring sämre: när ett
kluster slås ut finns inga närliggande jobb lokalt, och arbetaren måste
antingen pendla längre eller flytta längre i planet.

Måtten per körning:

  täckning C(s)     andel av enhetsskivans yta inom avståndet s från något
                    aktivt jobb, sysselsättningsviktad. Hög täckning = tjockt
                    uppgiftsrum.
  tunnhet T(s)      1 - C(s)
  median u_R        övergångarnas längd i task-radier (jfr 1.03 nationellt)
  marknadstryck     vakanser per arbetslös
  arbetslöshet      andel av arbetskraften
  pendling          medianavstånd i km för realiserade matchningar

    python scripts/compare_municipalities.py output/run_A output/run_B ...
    python scripts/compare_municipalities.py --all        # alla körningar
"""
import os
import sys

import numpy as np
import pandas as pd


def find_repo_root(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, "core")) and os.path.isdir(os.path.join(d, "scenarios")):
            return d
        p = os.path.dirname(d)
        if p == d:
            raise RuntimeError("Hittade ingen repo-rot.")
        d = p


ROOT = find_repo_root(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def metrics(run_dir):
    """Nyckeltal ur den exporterade summary-tabellen.

    Täckning, arbetslöshet, vakansgrad, marknadstryck och median u_R räknas
    på ett ställe, i core/analysis/eventlog.py, i stället för med egen logik
    per skript."""
    from core.analysis.eventlog import load_tables

    s = load_tables(run_dir)["summary"]
    return {
        "körning": s.get("run", os.path.basename(run_dir.rstrip("/"))),
        "jobb": s.get("active_jobs", np.nan),
        "C(0.15)": s.get("coverage_0.15", np.nan),
        "C(0.25)": s.get("coverage_0.25", np.nan),
        "u %": s.get("u_pct", np.nan),
        "v %": s.get("v_pct", np.nan),
        "tryck": s.get("tightness", np.nan),
        "median u_R": s.get("median_u_R", np.nan),
        "övergångar": s.get("n_cps_sample", 0),
        "lönekvot": s.get("median_wage_ratio", np.nan),
        "residual": s.get("identity_residual_max", np.nan),
    }


def main(dirs):
    rows = []
    for d in dirs:
        try:
            rows.append(metrics(d))
        except Exception as e:
            print(f"hoppar över {os.path.basename(d)}: {type(e).__name__}: {e}")
    if not rows:
        raise SystemExit("Inga körningar kunde läsas.")
    df = pd.DataFrame(rows).sort_values("jobb")
    pd.set_option("display.width", 160)
    print(df.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    print("\nSamband med täckning (Spearman, parvis kompletta rader):")
    any_shown = False
    for col in ("u %", "median u_R", "tryck", "lönekvot"):
        if col not in df.columns:
            continue
        sub = df[["C(0.25)", col]].dropna()
        if len(sub) >= 3:
            r = sub.corr(method="spearman").iloc[0, 1]
            print(f"  C(0.25) mot {col:12s} {r:+.2f}   (n={len(sub)})")
            any_shown = True
        else:
            print(f"  C(0.25) mot {col:12s} —      (n={len(sub)}, minst 3 krävs)")
    if any_shown:
        print("\nHypotesen förutsäger negativ korrelation mot arbetslöshet och mot")
        print("median u_R: tjockare uppgiftsrum ger kortare omställningar.")
    print("\nOBS: jämför bara körningar från samma kodversion och parametrar.")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--all"]
    if "--all" in sys.argv or not args:
        outdir = os.path.join(ROOT, "output")
        args = sorted(os.path.join(outdir, d) for d in os.listdir(outdir)
                      if os.path.isfile(os.path.join(outdir, d, "final_state_jobs.csv")))
        if not args:
            raise SystemExit("Inga körningar med final_state_jobs.csv under output/.")
        print(f"({len(args)} körningar)\n")
    main(args)
