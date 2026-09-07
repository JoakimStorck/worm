"""
export_tables.py  (scripts/)
----------------------------
Skriver analysklara tabeller ur en körning till <körning>/tables/.

Eventloggen är rader av nyckel-värde-par: bra för felsökning, men varje
analys blir en parsningsövning. Tidigare hade validate_mobility, convergence
och figures varsin kopia av samma parser. Nu görs det en gång, i
core/analysis/eventlog.py, och skripten läser tabellerna.

    transitions.csv   en rad per tillträde: käll- och målyrke, u_R, löner, q,
                      och om det var yrkesbyte, återgång eller chefsövergång
    timeseries.csv    en rad per månad: stockar, flöden, u, v, marknadstryck
                      och identitetens residual
    flows.csv         antal händelser per typ
    summary.csv       en rad per körning: nyckeltalen samlade

Exporten är ett separat steg och inte automatisk, så att tabeller kan
genereras om med ny logik utan att simulera om.

    python scripts/export_tables.py                    # senaste körningen
    python scripts/export_tables.py output/run_A output/run_B
    python scripts/export_tables.py --all --combined runs.csv
"""
import argparse
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core.analysis.eventlog import export


def runs_under(outdir):
    return sorted(os.path.join(outdir, d) for d in os.listdir(outdir)
                  if os.path.isfile(os.path.join(outdir, d, "eventlog.csv")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--all", action="store_true", help="alla körningar under output/")
    ap.add_argument("--since", default=None,
                    help="ta bara med körningar från denna commit")
    ap.add_argument("--combined", default=None,
                    help="skriv en samlad summary över körningarna hit")
    a = ap.parse_args()

    outdir = os.path.join(ROOT, "output")
    if a.all:
        runs = runs_under(outdir)
    elif a.runs:
        runs = a.runs
    else:
        cand = runs_under(outdir)
        if not cand:
            raise SystemExit("Ingen körning med eventlog.csv under output/.")
        runs = [max(cand, key=os.path.getmtime)]
        print(f"(använder senaste: {os.path.basename(runs[0])})\n")

    rows = []
    for rd in runs:
        try:
            res = export(rd)
        except Exception as e:
            print(f"hoppar över {os.path.basename(rd)}: {type(e).__name__}: {e}")
            continue
        rows.append(res["summary"])
        s = res["summary"]
        print(f"{s['run']}: {len(res['transitions'])} tillträden, "
              f"{len(res['timeseries'])} månader -> {res['out_dir']}")
        if "median_u_R" in s:
            print(f"   median u_R {s['median_u_R']:.2f}   u {s.get('u_pct', float('nan')):.2f} %"
                  f"   v {s.get('v_pct', float('nan')):.2f} %"
                  f"   residual {s.get('identity_residual_max', 0):.0f}")

    if a.combined and rows:
        df = pd.DataFrame(rows)
        if a.since:
            before = len(df)
            df = df[df.get("commit", pd.Series(dtype=str)) == a.since[:8]]
            print(f"\nFiltrerat på commit {a.since[:8]}: {len(df)} av {before} körningar")
        path = a.combined if os.path.isabs(a.combined) else os.path.join(ROOT, a.combined)
        df.to_csv(path, index=False)
        print(f"\nSamlad: {path}  ({len(df)} körningar)")

        # Blandade kodversioner gör en jämförelse meningslös: den mäter då
        # kodhistorik snarare än skillnader mellan scenarier.
        if "commit" in df.columns:
            commits = df["commit"].dropna().unique()
            if len(commits) > 1:
                print(f"\nVARNING: körningarna kommer från {len(commits)} olika "
                      f"kodversioner ({', '.join(map(str, commits[:5]))}"
                      f"{' ...' if len(commits) > 5 else ''}).")
                print("Jämför bara körningar från samma commit, annars mäts kodhistorik.")
                print("Använd --since <commit> för att filtrera.")
            if df.get("dirty", pd.Series(dtype=bool)).any():
                n = int(df["dirty"].sum())
                print(f"VARNING: {n} körning(ar) gjordes med ocommittade ändringar "
                      f"och går inte att återskapa.")
        missing = int(df["commit"].isna().sum()) if "commit" in df.columns else len(df)
        if missing:
            print(f"({missing} körning(ar) saknar härkomst, gjorda före run_meta.json "
                  f"infördes -- de bör arkiveras.)")


if __name__ == "__main__":
    main()
