#!/usr/bin/env bash
# kor_0077.sh — det normala körskriptet. Körs från repo-roten:
#
#     bash kor_0077.sh                       # mora_baseline, frön 1-5
#     bash kor_0077.sh "1 2"                 # valda frön
#     SCENARIO=scenarios/siljan_3_kommuner.yml bash kor_0077.sh
#
# Vägrar starta med ocommittade ändringar: frö 3 i 0089-körningen gjordes
# på ett smutsigt träd och rapporten kunde bara varna i efterhand. Testerna
# körs först och avbryter vid rött (set -e).
set -euo pipefail

FRON="${1:-1 2 3 4 5}"
SCENARIO="${SCENARIO:-scenarios/mora_baseline.yml}"
[ -f "$SCENARIO" ] || { echo "Scenariot finns inte: $SCENARIO"; exit 1; }
git diff --quiet || { echo "Ocommittade ändringar: körningen blir inte återskapbar. Committa eller stasha."; exit 1; }
git log -1 --format='HEAD %h  %s'
echo "scenario $SCENARIO"
( cd tests && python -m pytest -q )

python scripts/prune_runs.py --keep-commit "$(git rev-parse --short=8 HEAD)"

for s in $FRON; do
    echo "--- frö $s ---"
    WORM_SEED=$s python -c \
      "import core.scenario_runner as r; r.run_and_log_scenario('$SCENARIO')"
done

python scripts/analysis.py --all

python - <<'PYEOF'
import os
import numpy as np, pandas as pd

runs = pd.read_csv("analysis/runs.csv")
frames = [pd.read_csv(f).assign(run=r) for r in runs["run"]
          for f in [os.path.join("output", r, "tables", "transitions.csv")]
          if os.path.exists(f)]
tr = pd.concat(frames, ignore_index=True)

# UPPSTARTEN UT. 10 200 av 21 500 rader är initialiseringar (0073) och har
# systematiskt andra värden: median u_R_occ 0.76 mot körningens 0.72, och
# sämre passform. De hör inte till mobiliteten.
boot = tr["is_bootstrap"].fillna(False).astype(bool) if "is_bootstrap" in tr else False
run = tr[~boot]
cps = run[run["in_cps_sample"].fillna(False).astype(bool)]
print(f"\n{len(tr)} rader: {int(np.sum(boot))} uppstart, {len(run)} under körning, "
      f"{len(cps)} i CPS-urvalet")

# u_R_occ, mellan YRKEN, inte u_R från individens position (0074)
q = pd.qcut(cps["r_req"], 4, duplicates="drop")
g = cps.groupby(q, observed=True)
print(f"\nmedian u_R_occ: {cps['u_R_occ'].median():.3f}  (mål 0.70)")
print(g[["u_R_occ", "n_applicants", "q_hire"]].median().round(3).to_string())

print(f"\nsökande per vakans: median {run['n_applicants'].median():.0f}  "
      f"medel {run['n_applicants'].mean():.2f}")
print(f"median q vid anställning: {run['q_hire'].median():.3f}   "
      f"andel q<0.40: {(run['q_hire'] < 0.40).mean():.1%}")
km = run["commute_km"].dropna()
print(f"pendling km: median {km.median():.1f}  p90 {km.quantile(.9):.1f}")

wr = run["wage_ratio"].dropna()
p10, p50, p90 = wr.quantile(.10), wr.median(), wr.quantile(.90)
print(f"\nlönekvot w/Pi_o (flöde)  p10 {p10:.4f}  p50 {p50:.4f}  p90 {p90:.4f}")
print(f"  P90/P50 {p90/p50:.3f}   P50/P10 {p50/p10:.3f}   (lika om lognormal)")
print(f"  över Pi: {(wr > 1).mean():.1%}   andel q>1 vid anställning: "
      f"{(run['q_hire'] > 1).mean():.1%}")

# --- KONVERGENS: årsserierna, inte slutvärdena ---------------------------
from core.analysis.eventlog import read_events
print("\n--- konvergens, per år och körning ---")
for r in runs["run"]:
    ny = [e for e in read_events(os.path.join("output", r))
          if e.get("event") == "new_year"]
    if not ny:
        continue
    rader = [(e.get("year"), e.get("stock_share_above_pi"), e.get("stock_sd_log_w"),
              e.get("unemployed"), e.get("unmatched_jobs"), e.get("revision_d_bar"))
             for e in ny]
    d = pd.DataFrame(rader, columns=["år", "över_Pi", "sd_log_w", "arbetslösa",
                                     "vakanser", "d_bar"])
    print(f"\n{r}")
    print(d.to_string(index=False))
    for kol in ("över_Pi", "sd_log_w"):
        v = pd.to_numeric(d[kol], errors="coerce").dropna()
        if len(v) >= 4:
            tidig, sen = v.iloc[:len(v)//2].mean(), v.iloc[len(v)//2:].mean()
            print(f"  {kol}: första halvan {tidig:.4f}, andra {sen:.4f}, "
                  f"skillnad {100*(sen/tidig - 1):+.1f} %")
PYEOF
