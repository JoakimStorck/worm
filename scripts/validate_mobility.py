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

# OBS: 1.03 är CPS globala median och en blandning: inom delsystem ~0.7 (73 %
# av övergångarna), över delsystemgräns 1.93 (27 %). En gles kommun med få
# tvärövergångar bör ligga under 1.03. Jämför mot 0.7 om marknaden är tunn.
REFERENCE = {
    "median_uR": 1.03,
    "median_uR_within": 0.70,
    "median_uR_cross": 1.93,
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
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def collect(run_dir):
    """Övergångar ur den exporterade tabellen. Parsningen görs en gång, i
    core/analysis/eventlog.py, i stället för i varje skript."""
    from core.analysis.eventlog import load_tables

    tr = load_tables(run_dir)["transitions"]
    if tr.empty or "u_R_occ" not in tr.columns:
        raise SystemExit(
            "Inga övergångar med u_R_occ.\n"
            "Kör en simulering efter att u_R-loggningen införts.")
    n = len(tr)
    n_same = int((~tr["occ_change"].fillna(True).astype(bool)).sum())
    n_mgmt = int((tr["occ_change"].fillna(False).astype(bool)
                  & tr["is_mgmt"].fillna(False).astype(bool)).sum())
    cps = tr[tr["in_cps_sample"].fillna(False).astype(bool)]

    print("(u_R mätt från senaste yrkes centroid, som CPS)")
    print(f"(tillträden totalt {n}: återgång till eget yrke {n_same} "
          f"= {100*n_same/max(n,1):.1f} % utesluts som i CPS; "
          f"chefsövergångar {n_mgmt} = {100*n_mgmt/max(n,1):.1f} % utesluts "
          f"eftersom de är befordran, inte uppgiftsbaserad rörlighet)")
    if n_mgmt:
        m = tr[tr["occ_change"].fillna(False).astype(bool)
               & tr["is_mgmt"].fillna(False).astype(bool)]["u_R_occ"].median()
        print(f"(median u_R för chefsövergångarna separat: {m:.2f}, jfr CPS tvär 1.93)")
    print()
    return (cps["u_R_occ"].dropna().to_numpy(),
            cps["d_task"].dropna().to_numpy())


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
          f"{m - REFERENCE['median_uR']:+.2f}   (global CPS)")
    print(f"{'':26} {'':10} {REFERENCE['median_uR_within']:10.2f}   "
          f"{m - REFERENCE['median_uR_within']:+.2f}   (inom delsystem, 73 %)")
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
    print(f"\nImplicerad sigma_gamma ur modellens median: {sigma_implied:.3f}"
          f"  (empirin ger 0.875)")
    target = REFERENCE["median_uR_within"]     # inom delsystem: modellens mål
    if m > target * 1.15:
        print("\n  Övergångarna är LÄNGRE än inom-delsystem-värdet 0.70. Det globala")
        print("  1.03 gäller en tjock marknad (CPS, hela USA). Är vakanspoolen tunn")
        print("  sätts avståndet av knapphet snarare än av kärnbredden: man tar det")
        print("  som finns. Kontrollera marknadstrycket med diagnose_mismatch innan")
        print("  sigma_gamma justeras -- i en gles kommun är längre övergångar en")
        print("  PREDIKTION, inte ett kalibreringsfel.")
    elif m < target * 0.85:
        print("\n  Övergångarna är KORTARE än inom-delsystem-värdet 0.70. Det tyder på")
        print("  att kravet för")
        print("  acceptans binder (reservationslön eller pendlingskostnad), eller att")
        print("  tilldelningen väljer närmaste jobb i stället för högsta överskott.")


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
