"""
analysis.py  (scripts/)
-----------------------
Från körningar till manuskript i ett kommando.

Vägen dit har varit en serie skript i rätt ordning -- export_tables,
validate_mobility, convergence, check_invariants, figures,
compare_municipalities -- och det är där fel smyger in. Detta kör dem i
ordning, grupperar körningar per scenario, redovisar spridning över frön och
skriver en sammanfattning.

    python scripts/analysis.py --all                  # allt under output/
    python scripts/analysis.py output/run_A output/run_B
    python scripts/analysis.py --all --since 47da14ab # en kodversion
    python scripts/analysis.py --all --no-figures

Skriver till analysis/:
    runs.csv          en rad per körning, med härkomst
    by_scenario.csv   median och spridning per scenario
    report.md         sammanfattning med jämförelse mot referensvärden
    figures/          figurer med data och manifest
"""
import argparse
import datetime
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.analysis.eventlog import collect_runs, group_stats, export

REF = {"median_u_R": 0.70, "u_pct": 7.5, "v_pct": 2.0}


def runs_under(outdir):
    return sorted(os.path.join(outdir, d) for d in os.listdir(outdir)
                  if d != "arkiv" and os.path.isdir(os.path.join(outdir, d))
                  and os.path.isfile(os.path.join(outdir, d, "eventlog.csv")))


def _fmt(v, nd=2):
    return "—" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:.{nd}f}"


def write_report(df, grouped, out, run_dirs, figdir=None):
    lines = []
    A = lines.append
    A("# Analys av WORM-körningar\n")
    A(f"Genererad {datetime.datetime.now().isoformat(timespec='seconds')} "
      f"ur {len(df)} körningar.\n")

    # Härkomst först: en jämförelse över blandade kodversioner mäter kodhistorik
    if "commit" in df.columns:
        commits = sorted(df["commit"].dropna().unique())
        A("## Härkomst\n")
        if len(commits) > 1:
            A(f"**Varning:** körningarna kommer från {len(commits)} kodversioner "
              f"({', '.join(commits)}). En jämförelse mellan dem mäter kodhistorik "
              f"snarare än skillnader mellan scenarier. Använd `--since`.\n")
        elif commits:
            A(f"Samtliga körningar är gjorda på commit `{commits[0]}`.\n")
        if df.get("dirty", pd.Series(dtype=bool)).any():
            A(f"**Varning:** {int(df['dirty'].sum())} körning(ar) gjordes med "
              f"ocommittade ändringar och går inte att återskapa.\n")
        if "seed" in df.columns:
            per = df.groupby("scenario")["seed"].nunique() if "scenario" in df else None
            if per is not None:
                A("Frön per scenario: "
                  + ", ".join(f"{k}: {v}" for k, v in per.items()) + "\n")

    # Bokföringen: en modell vars aggregat inte stämmer går inte att dra slutsatser ur
    A("## Bokföring\n")
    if "identity_residual_max" in df.columns:
        bad = df[df["identity_residual_max"].abs() > 0.5]
        if bad.empty:
            A("Identiteten $U = L - J + V$ håller exakt i samtliga körningar.\n")
        else:
            A(f"**Varning:** {len(bad)} körning(ar) bryter identiteten "
              f"$U = L - J + V$ (störst avvikelse "
              f"{bad['identity_residual_max'].abs().max():.0f}). Kör "
              f"`scripts/check_invariants.py` på dem.\n")

    A("## Utfall per scenario\n")
    cols = [c for c in ("scenario", "n_runs", "u_pct_median", "v_pct_median",
                        "tightness_median", "median_u_R_median",
                        "median_wage_ratio_median", "coverage_0.25_median")
            if c in grouped.columns]
    if cols:
        g = grouped[cols].copy()
        g.columns = [c.replace("_median", "").replace("_pct", " %") for c in cols]
        A(g.to_markdown(index=False, floatfmt=".3f") + "\n")

    A("## Mot referensvärden\n")
    A("| Storhet | Modell (median) | Spridning över frön | Referens | Källa |")
    A("|---|---|---|---|---|")
    for key, ref, src in (("median_u_R", REF["median_u_R"],
                           "papper 2, inom delsystem"),
                          ("u_pct", REF["u_pct"], "svensk arbetslöshet"),
                          ("v_pct", REF["v_pct"], "svensk vakansgrad")):
        if key not in df.columns:
            continue
        x = pd.to_numeric(df[key], errors="coerce").dropna()
        if x.empty:
            continue
        spread = f"{x.min():.2f}–{x.max():.2f}" if len(x) > 1 else "—"
        A(f"| {key} | {_fmt(float(x.median()))} | {spread} | {ref} | {src} |")
    A("")

    if len(df) > 2 and "coverage_0.25" in df.columns:
        A("## Täckning mot utfall\n")
        A("Hypotesen förutsäger negativ korrelation: ett tjockare uppgiftsrum "
          "ger lägre arbetslöshet och kortare omställningar.\n")
        A("| Utfall | Spearman mot C(0.25) | n |")
        A("|---|---|---|")
        for col in ("u_pct", "median_u_R", "tightness"):
            if col not in df.columns:
                continue
            sub = df[["coverage_0.25", col]].apply(pd.to_numeric, errors="coerce").dropna()
            if len(sub) >= 3:
                A(f"| {col} | {sub.corr(method='spearman').iloc[0,1]:+.2f} | {len(sub)} |")
        A("")

    if figdir:
        A("## Figurer\n")
        for f in sorted(os.listdir(figdir)):
            if f.endswith(".pdf"):
                A(f"- `{f}` (data och manifest bredvid)")
        A("")

    A("## Körningar\n")
    show = [c for c in ("run", "scenario", "seed", "commit", "years", "u_pct",
                        "v_pct", "median_u_R", "n_cps_sample") if c in df.columns]
    A(df[show].to_markdown(index=False, floatfmt=".2f") + "\n")

    path = os.path.join(out, "report.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Sparad: {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--since", default=None, help="bara körningar från denna commit")
    ap.add_argument("--out", default=os.path.join(ROOT, "analysis"))
    ap.add_argument("--no-figures", action="store_true")
    a = ap.parse_args()

    outdir = os.path.join(ROOT, "output")
    runs = a.runs or (runs_under(outdir) if a.all else [])
    if not runs:
        cand = runs_under(outdir)
        if not cand:
            raise SystemExit("Inga körningar under output/.")
        runs = [max(cand, key=os.path.getmtime)]
        print(f"(använder senaste: {os.path.basename(runs[0])})\n")

    print(f"Exporterar tabeller för {len(runs)} körningar ...")
    for rd in runs:
        try:
            export(rd)
        except Exception as e:
            print(f"  hoppar över {os.path.basename(rd)}: {type(e).__name__}: {e}")

    df = collect_runs(runs)
    if df.empty:
        raise SystemExit("Inga körningar kunde läsas.")
    if a.since and "commit" in df.columns:
        keep = df["commit"] == a.since[:8]
        print(f"Filtrerat på commit {a.since[:8]}: {int(keep.sum())} av {len(df)}")
        df = df[keep]
        runs = [r for r in runs if os.path.basename(str(r).rstrip("/"))
                in set(df["run"])]
        if df.empty:
            raise SystemExit("Inga körningar matchade filtret.")

    os.makedirs(a.out, exist_ok=True)
    df.to_csv(os.path.join(a.out, "runs.csv"), index=False)
    by = "scenario" if "scenario" in df.columns else "run"
    grouped = group_stats(df, by=by)
    grouped.to_csv(os.path.join(a.out, "by_scenario.csv"), index=False)
    print(f"Sparad: {os.path.join(a.out, 'runs.csv')}")
    print(f"Sparad: {os.path.join(a.out, 'by_scenario.csv')}")

    figdir = None
    if not a.no_figures:
        import scripts.figures as F  # noqa
        figdir = os.path.join(a.out, "figures")
        os.makedirs(figdir, exist_ok=True)
        F.fig_mobility(runs, figdir)
        F.fig_competence(figdir)
        F.fig_coverage(runs, figdir)
        F.fig_tenure(figdir)
        F.fig_wages(runs, figdir)

    write_report(df, grouped, a.out, runs, figdir)


if __name__ == "__main__":
    main()
