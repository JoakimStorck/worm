"""
convergence.py  (scripts/)
--------------------------
Svarar på frågan om en körning har nått jämvikt, och skattar hur långt det är
kvar om den inte har det.

Modellen har en jämvikt, och den är delvis analytisk:

  JOBBSTOCKEN   dJ/dt = fill*(T - J) - (delta/12)*J  har fixpunkten
                J* = T / (1 + (delta/12)/fill).  Exponentiellt stabil.

  IDENTITETEN   U = L - J + V   (arbetskraft minus jobb plus vakanser).
                Med L och J* givna är V den enda fria storheten, och
                arbetslösheten har en strukturell miniminivå
                u_min = (L - J*)/L  som nås när V = 0.

  VAKANSERNA    V bestäms av flödesbalans mellan nyskapande och matchning.
                Det är den enda storhet som geometrin påverkar.

Skriptet anpassar y(t) = y_inf + (y0 - y_inf)*exp(-t/tau) till serierna och
rapporterar asymptot och tidskonstant, samt hur många år som krävs för att nå
inom en given tolerans.

    python scripts/convergence.py                  # senaste körningen
    python scripts/convergence.py output/run_...
"""
import os
import sys

import numpy as np


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


def series(run_dir):
    rows = []
    path = os.path.join(run_dir, "eventlog.csv")
    for line in open(path, encoding="utf-8", errors="replace"):
        if "new_month" not in line:
            continue
        r = _parse(line)
        if r is None or r.get("event") != "new_month":
            continue
        try:
            rows.append({k: float(r[k]) for k in
                         ("time", "employed", "unemployed", "unmatched_jobs")}
                        | {"active_jobs": float(r.get("active_jobs", "nan"))})
        except (KeyError, ValueError):
            continue
    if not rows:
        raise SystemExit("Inga användbara new_month-rader.")
    return {k: np.array([r[k] for r in rows]) for k in rows[0]}


def fit_exponential(t, y):
    """y(t) = y_inf + (y0 - y_inf) exp(-t/tau). Skattar y_inf och tau genom
    att söka det y_inf som gör log|y - y_inf| mest linjärt i t."""
    if y.size < 5 or np.allclose(y, y[0]):
        return float(y[-1]), np.nan, np.nan
    lo, hi = (0.0, float(y.min())) if y[-1] < y[0] else (float(y.max()), float(y.max()) * 3)
    best = (None, -np.inf, np.nan)
    for cand in np.linspace(lo, hi, 400):
        d = y - cand
        if np.any(np.abs(d) < 1e-9) or np.any(np.sign(d) != np.sign(d[0])):
            continue
        z = np.log(np.abs(d))
        A = np.vstack([t, np.ones_like(t)]).T
        coef, res, *_ = np.linalg.lstsq(A, z, rcond=None)
        pred = A @ coef
        ss = 1 - np.sum((z - pred) ** 2) / max(np.sum((z - z.mean()) ** 2), 1e-12)
        if ss > best[1] and coef[0] < 0:
            best = (cand, ss, -1.0 / coef[0])
    return best[0] if best[0] is not None else float(y[-1]), best[2], best[1]


def report(run_dir):
    s = series(run_dir)
    t = s["time"] / 365.25
    L = s["employed"] + s["unemployed"]
    J = s["active_jobs"]
    V = s["unmatched_jobs"]
    U = s["unemployed"]

    print(f"Körning: {os.path.basename(run_dir.rstrip('/'))}   "
          f"{len(t)} månader ({t[-1]:.2f} år)\n")

    # Identiteten
    resid = np.abs(U - (L - J + V))
    print(f"Identiteten U = L - J + V: största avvikelse {resid.max():.0f} individer")
    u_min = 100 * (L[-1] - J[-1]) / L[-1]
    print(f"Strukturell miniminivå (V=0): u_min = {u_min:.2f} %   "
          f"nu: {100*U[-1]/L[-1]:.2f} %")
    print("  Arbetslösheten är bunden av arbetskraft mot jobbstock, inte av")
    print("  geometrin. Endast vakanserna är fria.\n")

    for namn, y in (("aktiva jobb J", J), ("vakanser V", V), ("arbetslösa U", U)):
        y_inf, tau, r2 = fit_exponential(t, y)
        rel = abs(y[-1] - y_inf) / max(abs(y_inf), 1.0)
        line = (f"{namn:15s} nu {y[-1]:8.0f}   asymptot {y_inf:8.0f}   "
                f"tau {tau:.2f} år" if np.isfinite(tau) else
                f"{namn:15s} nu {y[-1]:8.0f}   (ingen tydlig exponentiell trend)")
        print(line)
        if np.isfinite(tau) and tau > 0:
            for tol in (0.05, 0.01):
                need = tau * np.log(abs(y[0] - y_inf) / max(tol * abs(y_inf), 1e-9))
                print(f"{'':15s}   inom {100*tol:.0f} % efter {need:.1f} år"
                      f"{'  (uppnått)' if t[-1] >= need else ''}")
            print(f"{'':15s}   kvar till jämvikt nu: {100*rel:.1f} %")
        print()

    print("Rekommendation: kör tills vakanserna ligger inom någon procent av sin")
    print("asymptot. Jämförelser mellan kommuner i transient tillstånd mäter")
    print("konvergenshastighet snarare än jämvikt.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_dir = sys.argv[1]
    else:
        outdir = os.path.join(ROOT, "output")
        cands = [os.path.join(outdir, d) for d in os.listdir(outdir)
                 if os.path.isfile(os.path.join(outdir, d, "eventlog.csv"))]
        if not cands:
            raise SystemExit("Ingen körning med eventlog.csv under output/.")
        run_dir = max(cands, key=os.path.getmtime)
        print(f"(använder senaste: {os.path.basename(run_dir)})\n")
    report(run_dir)
