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


def coverage(jobs, s, n_grid=200):
    """Andel av enhetsskivan inom avståndet s från något aktivt jobb."""
    if "x_occ" not in jobs.columns or "y_occ" not in jobs.columns:
        return np.nan                     # körning från före geometrin
    if "active" in jobs.columns:
        jobs = jobs[jobs["active"].astype(bool)]
    x = jobs["x_occ"].dropna().to_numpy()
    y = jobs["y_occ"].dropna().to_numpy()
    if x.size == 0:
        return np.nan
    g = np.linspace(-1, 1, n_grid)
    gx, gy = np.meshgrid(g, g)
    inside = gx ** 2 + gy ** 2 <= 1.0
    px, py = gx[inside], gy[inside]
    covered = np.zeros(px.size, dtype=bool)
    for st in range(0, x.size, 500):                 # blockvis för minnet
        bx, by = x[st:st + 500], y[st:st + 500]
        d2 = (px[:, None] - bx[None, :]) ** 2 + (py[:, None] - by[None, :]) ** 2
        covered |= (d2 <= s * s).any(axis=1)
        if covered.all():
            break
    return float(covered.mean())


def _parse(line):
    parts = [p.strip() for p in line.rstrip("\n").split(",")]
    if len(parts) < 2:
        return None
    rec = {}
    try:
        rec["time"] = float(parts[0])
    except ValueError:
        return None
    rec["event"] = parts[1]
    for f in parts[2:]:
        if f:
            k, _, v = f.partition(" ")
            rec[k] = v.strip()
    return rec


def metrics(run_dir):
    ind = pd.read_csv(os.path.join(run_dir, "final_state_individuals.csv"))
    jobs = pd.read_csv(os.path.join(run_dir, "final_state_jobs.csv"))
    if "status" not in ind.columns or "individual_id" not in jobs.columns:
        return {"körning": os.path.basename(run_dir.rstrip("/")), "jobb": len(jobs)}
    act = jobs["active"].astype(bool) if "active" in jobs.columns else pd.Series(True, index=jobs.index)

    unemp = int((ind["status"] == "unemployed").sum())
    emp = int((ind["status"] == "employed").sum())
    vac = int((jobs["individual_id"].isna() & act).sum())

    uR = []
    path = os.path.join(run_dir, "eventlog.csv")
    if os.path.isfile(path):
        for line in open(path, encoding="utf-8", errors="replace"):
            if "u_R" not in line:
                continue
            rec = _parse(line)
            if rec and "u_R" in rec:
                try:
                    uR.append(float(rec["u_R"]))
                except ValueError:
                    pass
    uR = np.array(uR)

    return {
        "körning": os.path.basename(run_dir.rstrip("/")),
        "jobb": int(act.sum()),
        "C(0.15)": coverage(jobs, 0.15),
        "C(0.25)": coverage(jobs, 0.25),
        "u %": 100 * unemp / max(emp + unemp, 1),
        "v %": 100 * vac / max(int(act.sum()), 1),
        "tryck": vac / max(unemp, 1),
        "median u_R": float(np.median(uR)) if uR.size else np.nan,
        "övergångar": int(uR.size),
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

    if len(df) >= 3 and df["C(0.25)"].notna().all():
        print("\nSamband med täckning (Spearman):")
        for col in ("u %", "median u_R", "tryck"):
            if df[col].notna().sum() >= 3:
                r = df[["C(0.25)", col]].corr(method="spearman").iloc[0, 1]
                print(f"  C(0.25) mot {col:12s} {r:+.2f}")
        print("\nHypotesen förutsäger negativ korrelation mot arbetslöshet och mot")
        print("median u_R: tjockare uppgiftsrum ger kortare omställningar.")
    else:
        print("\n(minst tre körningar krävs för korrelationer)")


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
