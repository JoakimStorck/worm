"""
load_occupation_weights.py  (scripts/)
--------------------------------------
Läser yrkesvikter per kommun till tabellen occupation_weights_by_municipality,
som scenariobyggaren använder när scenariot anger

    simulation:
      occupation_source: register

i stället för SNI-fördelning x sni_onet_link.

Indata: en CSV med kolumnerna
    municipal_code, occupation_code, weight[, year]
t.ex. SCB:s yrkesregister (dagbefolkning, SSYK4, kommun) eller höstprojektets
per-kommun-fördelning. weight kan vara antal anställda eller andel.

Kodsystem. Geometritabellen deklarerar sitt kodsystem i kolumnen code_system.
Är indata i ett annat system (t.ex. SSYK 2012 mot O*NET-SOC) anges en
crosswalk-CSV med kolumnerna
    occupation_code, onet_code, share
där share anger hur en källkod fördelas över målkoder (summerar till 1 per
källkod). Vikten sprids proportionellt.

    python scripts/load_occupation_weights.py data/weights.csv
    python scripts/load_occupation_weights.py data/weights_ssyk.csv --crosswalk data/ssyk_to_onet.csv
    python scripts/load_occupation_weights.py data/weights.csv --dry-run
"""
import argparse
import os
import sqlite3
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
DB_PATH = os.path.join(ROOT, "data", "worm.sqlite3")


def build(weights_csv, crosswalk_csv=None, db_path=DB_PATH):
    w = pd.read_csv(weights_csv, dtype={"municipal_code": str, "occupation_code": str})
    need = {"municipal_code", "occupation_code", "weight"}
    missing = need - set(w.columns)
    if missing:
        raise SystemExit(f"Saknar kolumner i {weights_csv}: {sorted(missing)}")
    if "year" not in w.columns:
        w["year"] = pd.NA
    w["weight"] = pd.to_numeric(w["weight"], errors="coerce").fillna(0.0)

    conn = sqlite3.connect(db_path)
    try:
        geom = pd.read_sql("SELECT onet_code, code_system FROM onet_occupation_space", conn)
    except Exception as e:
        raise SystemExit(f"Kan inte läsa onet_occupation_space ({e}). Kör load_task_geometry.py först.")
    code_system = str(geom["code_system"].iloc[0]) if "code_system" in geom.columns else "onet_soc"
    known = set(geom["onet_code"])

    if crosswalk_csv:
        cw = pd.read_csv(crosswalk_csv, dtype={"occupation_code": str, "onet_code": str})
        cw_need = {"occupation_code", "onet_code", "share"}
        if cw_need - set(cw.columns):
            raise SystemExit(f"Crosswalk saknar kolumner: {sorted(cw_need - set(cw.columns))}")
        cw["share"] = pd.to_numeric(cw["share"], errors="coerce").fillna(0.0)
        tot = cw.groupby("occupation_code")["share"].transform("sum")
        cw["share"] = cw["share"] / tot.where(tot > 0, 1.0)
        n_before = w["occupation_code"].nunique()
        w = w.merge(cw, on="occupation_code", how="left")
        unmapped = w["onet_code"].isna()
        if unmapped.any():
            print(f"crosswalk: {w.loc[unmapped, 'occupation_code'].nunique()} av {n_before} källkoder "
                  f"saknar mappning och släpps (vikt {w.loc[unmapped, 'weight'].sum():.0f}).")
            w = w[~unmapped]
        w["weight"] = w["weight"] * w["share"]
        w = w.drop(columns=["occupation_code", "share"])
    else:
        w = w.rename(columns={"occupation_code": "onet_code"})

    unknown = ~w["onet_code"].isin(known)
    if unknown.any():
        print(f"geometri: {w.loc[unknown, 'onet_code'].nunique()} koder saknas i onet_occupation_space "
              f"({code_system}) och släpps, t.ex. {list(w.loc[unknown, 'onet_code'].unique()[:5])}")
        w = w[~unknown]

    out = (w.groupby(["municipal_code", "onet_code", "year"], dropna=False)["weight"].sum()
             .reset_index())
    out = out[out["weight"] > 0]
    return out, code_system, conn


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("weights_csv")
    ap.add_argument("--crosswalk", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    out, code_system, conn = build(a.weights_csv, a.crosswalk)
    print(f"kodsystem i geometrin: {code_system}")
    print(f"rader: {len(out)}   kommuner: {out['municipal_code'].nunique()}   "
          f"yrken: {out['onet_code'].nunique()}")
    print(out.head(8).to_string(index=False))
    if a.dry_run:
        print("\n(dry-run: inget skrivet)")
        return
    out.to_sql("occupation_weights_by_municipality", conn, if_exists="replace", index=False)
    conn.commit(); conn.close()
    print("\nSkrev tabellen occupation_weights_by_municipality. Sätt occupation_source: register i scenariot.")


if __name__ == "__main__":
    main()
