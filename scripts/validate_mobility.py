"""
validate_mobility.py  (scripts/)
--------------------------------
Jämför WORM:s simulerade yrkesmobilitet mot den empiriska fördelningen i
"Two scales of occupational mobility" (CPS 2020-2024).

Referensvärden (normaliserat avstånd u_R = d / R_källa):

    median u_R              1.03
    inom 1/3 task-radie     ~10 %
    inom 1/2 task-radie     ~20 %
    inom 1 task-radie       ~50 %
    inom 2 task-radier      >80 %
    absolut median          0.28   (task-radie ~0.272)

Teoretisk förväntan: med lokalt likformig jobbtäthet i planet och gaussisk
acceptans är accepterat avstånd Rayleigh-fördelat med skala sigma, median
1.1774*sigma. Empirisk median 1.03 ger sigma = 0.875 * r_o, alltså
sigma_gamma = 0.875.

    python scripts/validate_mobility.py                 # senaste körningen
    python scripts/validate_mobility.py output/run_...
"""
import os
import sys

import numpy as np

REFERENCE = {
    "median_uR": 1.03,
    "within": [(1 / 3, 0.10), (0.5, 0.20), (1.0, 0.50), (2.0, 0.80)],
    "median_abs": 0.28,
}


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
    """Eventloggen är inte CSV utan 'tid, händelse, nyckel värde, ...'."""
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


def collect(run_dir):
    path = os.path.join(run_dir, "eventlog.csv")
    if not os.path.isfile(path):
        raise SystemExit(f"Saknar {path}")
    uR, d_abs = [], []
    for line in open(path, "r", encoding="utf-8", errors="replace"):
        if "u_R" not in line and "d_task" not in line:
            continue
        rec = _parse(line)
        if rec is None:
            continue
        try:
            if "u_R" in rec:
                uR.append(float(rec["u_R"]))
            if "d_task" in rec:
                d_abs.append(float(rec["d_task"]))
        except ValueError:
            continue
    return np.array(uR), np.array(d_abs)


def report(run_dir):
    uR, d_abs = collect(run_dir)
    if uR.size == 0:
        raise SystemExit(
            "Inga övergångar med u_R i eventloggen.\n"
            "Kör en simulering efter att u_R-loggningen införts.")

    print(f"Övergångar: {uR.size}\n")
    print(f"{'':26} {'modell':>10} {'empiri':>10}   avvikelse")
    print("-" * 62)
    m = float(np.median(uR))
    print(f"{'median u_R':26} {m:10.2f} {REFERENCE['median_uR']:10.2f}   "
          f"{m - REFERENCE['median_uR']:+.2f}")
    if d_abs.size:
        ma = float(np.median(d_abs))
        print(f"{'median absolut avstånd':26} {ma:10.3f} {REFERENCE['median_abs']:10.3f}   "
              f"{ma - REFERENCE['median_abs']:+.3f}")
    print()
    for frac, ref in REFERENCE["within"]:
        got = float((uR <= frac).mean())
        label = {1/3: "inom 1/3 radie", 0.5: "inom 1/2 radie",
                 1.0: "inom 1 radie", 2.0: "inom 2 radier"}[frac]
        print(f"{label:26} {100*got:9.1f}% {100*ref:9.0f}%   {100*(got-ref):+.1f} pe")

    print("\nFördelning av u_R:")
    for q in (10, 25, 50, 75, 90, 99):
        print(f"  p{q:<3d} {np.percentile(uR, q):.2f}")

    # Implicerad kärnbredd om fördelningen vore Rayleigh
    sigma_implied = m / np.sqrt(2 * np.log(2))
    print(f"\nImplicerad sigma_gamma ur modellens median: {sigma_implied:.3f}")
    print("  (empirin ger 0.875; stora avvikelser betyder att jobbtätheten runt")
    print("   arbetarna inte är lokalt likformig, eller att reservationslönen binder)")


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
