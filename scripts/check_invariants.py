"""
check_invariants.py  (scripts/)
-------------------------------
Pekar ut VILKA individer och positioner som bryter bokföringen, i stället för
att bara konstatera att residualen är skild från noll.

Identiteten U = L - J + V bygger på att antalet sysselsatta är exakt lika med
antalet tillsatta aktiva positioner. Bryts den finns ett av följande fel, och
skriptet räknar och exemplifierar var och en:

  A  sysselsatt utan job_id
  B  sysselsatt vars job_id inte finns i jobbtabellen
  C  sysselsatt vars position är inaktiv (förstörd)
  D  sysselsatt vars position bär någon annans id
  E  aktiv tillsatt position vars innehavare inte är sysselsatt
  F  aktiv tillsatt position vars innehavare inte finns

    python scripts/check_invariants.py                 # senaste körningen
    python scripts/check_invariants.py output/run_...
"""
import os
import sys

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


def report(run_dir):
    ind = pd.read_csv(os.path.join(run_dir, "final_state_individuals.csv"))
    jobs = pd.read_csv(os.path.join(run_dir, "final_state_jobs.csv"))
    act = (jobs["active"].astype(bool) if "active" in jobs.columns
           else pd.Series(True, index=jobs.index))

    emp = ind[ind["status"] == "employed"]
    filled_active = jobs[jobs["individual_id"].notna() & act]
    print(f"sysselsatta: {len(emp)}   tillsatta aktiva positioner: {len(filled_active)}"
          f"   residual: {len(emp) - len(filled_active):+d}\n")

    by_id = jobs.set_index("job_id")
    known_ind = set(ind["individual_id"])

    def show(label, rows, cols):
        if len(rows) == 0:
            return
        print(f"{label}: {len(rows)}")
        print(rows[cols].head(3).to_string(index=False))
        print()

    a = emp[emp["job_id"].isna()]
    show("A  sysselsatt utan job_id", a, ["individual_id", "status"])

    have = emp[emp["job_id"].notna()].copy()
    missing = have[~have["job_id"].isin(by_id.index)]
    show("B  sysselsatt vars job_id saknas i jobbtabellen", missing,
         ["individual_id", "job_id"])

    ok = have[have["job_id"].isin(by_id.index)].copy()
    ok["job_active"] = by_id.loc[ok["job_id"], "active"].to_numpy() if "active" in jobs.columns else True
    ok["job_holder"] = by_id.loc[ok["job_id"], "individual_id"].to_numpy()

    show("C  sysselsatt vars position är inaktiv (förstörd)",
         ok[~ok["job_active"].astype(bool)], ["individual_id", "job_id"])
    show("D  sysselsatt vars position bär någon annans id",
         ok[ok["job_active"].astype(bool) & (ok["job_holder"] != ok["individual_id"])],
         ["individual_id", "job_id", "job_holder"])

    st = ind.set_index("individual_id")["status"]
    fa = filled_active.copy()
    fa["holder_status"] = fa["individual_id"].map(st)
    show("E  aktiv tillsatt position vars innehavare inte är sysselsatt",
         fa[fa["holder_status"].notna() & (fa["holder_status"] != "employed")],
         ["job_id", "individual_id", "holder_status"])
    show("F  aktiv tillsatt position vars innehavare inte finns",
         fa[~fa["individual_id"].isin(known_ind)], ["job_id", "individual_id"])

    if "pending" in jobs.columns:
        pend = jobs[jobs["pending"].astype(bool)]
        print(f"utlovade positioner: {len(pend)}"
              f"   varav tillsatta: {int(pend['individual_id'].notna().sum())}"
              f"   varav inaktiva: {int((~act[pend.index]).sum())}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_dir = sys.argv[1]
    else:
        outdir = os.path.join(ROOT, "output")
        cands = [os.path.join(outdir, d) for d in os.listdir(outdir)
                 if os.path.isfile(os.path.join(outdir, d, "final_state_individuals.csv"))]
        if not cands:
            raise SystemExit("Ingen körning med final_state_individuals.csv under output/.")
        run_dir = max(cands, key=os.path.getmtime)
        print(f"(använder senaste: {os.path.basename(run_dir)})\n")
    report(run_dir)
