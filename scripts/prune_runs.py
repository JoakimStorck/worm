"""
prune_runs.py  (scripts/)
-------------------------
Arkiverar körningar som inte längre är jämförbara, och visar vad som tar plats.

Problemet är inte antalet körningar utan att de kommer från olika
kodversioner. En samlad tabell över dem mäter kodhistorik snarare än
skillnader mellan scenarier. Körningar gjorda före run_meta.json infördes
saknar dessutom härkomst helt och går varken att koppla till kod eller att
upprepa.

Arkivering flyttar till output/arkiv/ i stället för att radera, så att
ingenting går förlorat. Radering kräver --delete och bekräftelse.

    python scripts/prune_runs.py                     # visa vad som finns
    python scripts/prune_runs.py --archive-unknown   # arkivera utan härkomst
    python scripts/prune_runs.py --keep-commit abc12345
    python scripts/prune_runs.py --archive-short 12  # kortare än 12 månader
    python scripts/prune_runs.py --slim              # bantar tillståndsfiler
"""
import argparse
import json
import os
import shutil
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "output")
ARCHIVE = os.path.join(OUT, "arkiv")

# Kolumner som analysen faktiskt använder. Tillståndsfilerna dumpar hela
# tabellen, vilket ger ett par hundra megabyte per körning.
KEEP_IND = ["individual_id", "status", "job_id", "onet_code", "last_onet_code",
            "x_occ", "y_occ", "chi", "xi", "r_i", "R", "w_res", "w_neg",
            "education_level", "tenure_years", "municipal_code", "deso_code",
            "x", "y", "age"]
KEEP_JOB = ["job_id", "employer_id", "individual_id", "onet_code", "active",
            "pending", "x_occ", "y_occ", "r_o", "wage", "x", "y",
            "municipal_code", "deso_code", "geom_source"]


def dir_size(p):
    tot = 0
    for root, _, files in os.walk(p):
        for f in files:
            try:
                tot += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return tot


def runs():
    if not os.path.isdir(OUT):
        return []
    out = []
    for d in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, d)
        if d == "arkiv" or not os.path.isdir(p):
            continue
        meta = {}
        mp = os.path.join(p, "run_meta.json")
        if os.path.isfile(mp):
            try:
                meta = json.load(open(mp, encoding="utf-8"))
            except Exception:
                meta = {}
        months = 0
        tp = os.path.join(p, "tables", "timeseries.csv")
        if os.path.isfile(tp):
            try:
                months = len(pd.read_csv(tp))
            except Exception:
                pass
        out.append({"dir": p, "run": d,
                    "commit": (meta.get("git_commit") or "")[:8] or None,
                    "scenario": meta.get("scenario"),
                    "seed": meta.get("seed"),
                    "months": months,
                    "mb": dir_size(p) / 1e6})
    return out


def show(rs):
    if not rs:
        print("Inga körningar under output/.")
        return
    df = pd.DataFrame(rs).drop(columns=["dir"])
    pd.set_option("display.width", 150)
    print(df.to_string(index=False, float_format=lambda v: f"{v:.0f}"))
    print(f"\nTotalt {len(rs)} körningar, {sum(r['mb'] for r in rs)/1000:.1f} GB.")
    unknown = [r for r in rs if not r["commit"]]
    if unknown:
        print(f"{len(unknown)} saknar härkomst (före run_meta.json) och går varken "
              f"att koppla till kod eller upprepa.")
    commits = {r["commit"] for r in rs if r["commit"]}
    if len(commits) > 1:
        print(f"{len(commits)} olika kodversioner: jämför bara inom en.")


def archive(dirs, delete=False):
    if not dirs:
        print("Inget att arkivera.")
        return
    print(f"{'Raderar' if delete else 'Arkiverar'} {len(dirs)} körningar "
          f"({sum(dir_size(d) for d in dirs)/1e9:.2f} GB):")
    for d in dirs:
        print(f"   {os.path.basename(d)}")
    if delete:
        ans = input("Radera permanent? Skriv 'radera': ")
        if ans.strip() != "radera":
            print("Avbrutet."); return
        for d in dirs:
            shutil.rmtree(d)
    else:
        os.makedirs(ARCHIVE, exist_ok=True)
        for d in dirs:
            shutil.move(d, os.path.join(ARCHIVE, os.path.basename(d)))
    print("Klart.")


def slim(rs):
    """Bantar tillståndsfilerna till de kolumner analysen använder."""
    saved = 0
    for r in rs:
        for name, keep in (("individuals", KEEP_IND), ("jobs", KEEP_JOB)):
            for tag in ("initial", "final"):
                p = os.path.join(r["dir"], f"{tag}_state_{name}.csv")
                if not os.path.isfile(p):
                    continue
                before = os.path.getsize(p)
                try:
                    df = pd.read_csv(p)
                except Exception:
                    continue
                cols = [c for c in keep if c in df.columns]
                if len(cols) == len(df.columns):
                    continue
                df[cols].to_csv(p, index=False)
                saved += before - os.path.getsize(p)
    print(f"Sparade {saved/1e9:.2f} GB genom att behålla bara de kolumner "
          f"analysen använder.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive-unknown", action="store_true",
                    help="arkivera körningar utan härkomst")
    ap.add_argument("--keep-commit", default=None,
                    help="arkivera allt utom denna commit")
    ap.add_argument("--archive-short", type=int, default=None,
                    help="arkivera körningar kortare än N månader")
    ap.add_argument("--slim", action="store_true",
                    help="banta tillståndsfilerna till använda kolumner")
    ap.add_argument("--delete", action="store_true",
                    help="radera i stället för att arkivera (kräver bekräftelse)")
    a = ap.parse_args()

    rs = runs()
    if a.slim:
        slim(rs); return

    sel = []
    if a.archive_unknown:
        sel += [r["dir"] for r in rs if not r["commit"]]
    if a.keep_commit:
        sel += [r["dir"] for r in rs
                if r["commit"] and r["commit"] != a.keep_commit[:8]]
    if a.archive_short is not None:
        sel += [r["dir"] for r in rs if r["months"] < a.archive_short]
    sel = sorted(set(sel))

    if not (a.archive_unknown or a.keep_commit or a.archive_short is not None):
        show(rs); return
    archive(sel, delete=a.delete)


if __name__ == "__main__":
    main()
