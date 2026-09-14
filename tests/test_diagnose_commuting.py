"""Pendlingsdiagnosen: dag/natt och flödesasymmetri, modell mot SCB.

Modellens pendling är symmetrisk per konstruktion, eftersom scenariobuilder
sätter target_jobs = workforce - n_unemployed per kommun. Diagnosen mäter hur
stor den saknade frihetsgraden är innan target_jobs läggs om, så att
omläggningen har en baslinje att jämföras mot.
"""
import json
import os
import sqlite3

import pandas as pd
import pytest

from scripts.diagnose_commuting import _dagnatt, modellens_flode, scb_flode

KOMMUNER = ["2062", "2034", "2031"]


def _skriv_korning(d, flode):
    """final_state med ett jobb per anställd, i den kommun flödet säger."""
    os.makedirs(d, exist_ok=True)
    ind, jobb, jid = [], [], 0
    raknare = {}
    for (hem, arb), n in flode.items():
        for _ in range(n):
            i = raknare.get(hem, 0)
            raknare[hem] = i + 1
            j = f"J{jid:07d}"
            jid += 1
            ind.append({"individual_id": f"{hem}_i{i:06d}", "job_id": j})
            jobb.append({"job_id": j, "municipal_code": arb})
    pd.DataFrame(ind).to_csv(os.path.join(d, "final_state_individuals.csv"),
                             index=False)
    pd.DataFrame(jobb).to_csv(os.path.join(d, "final_state_jobs.csv"), index=False)
    with open(os.path.join(d, "run_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"municipalities": KOMMUNER}, f)


def _skriv_db(path, rader):
    conn = sqlite3.connect(path)
    pd.DataFrame(rader).to_sql("commuting", conn, if_exists="replace", index=False)
    conn.close()


def test_modellens_flode_ur_slutlaget(tmp_path):
    """Modellens sida måste vara en STOCK. share_hires_cross_municipality är
    ett flöde, och en kvot mellan ett flöde och SCB:s stock mäter skillnaden
    mellan flöde och stock lika mycket som mellan modell och verklighet."""
    d = str(tmp_path / "run")
    _skriv_korning(d, {("2062", "2062"): 5, ("2034", "2062"): 3,
                       ("2034", "2034"): 2})
    f = modellens_flode(d)
    assert f[("2034", "2062")] == 3
    assert f[("2062", "2062")] == 5
    assert ("2062", "2034") not in f


def test_dagnatt_ar_ett_for_symmetrisk_modell():
    """Lika många jobb som sysselsatta invånare i varje kommun ger kvoten
    1.00 överallt, oavsett hur stora bruttoflödena är."""
    flode = {("2062", "2062"): 700, ("2062", "2034"): 300,
             ("2034", "2034"): 700, ("2034", "2062"): 300}
    dag, natt = _dagnatt(flode, ["2062", "2034"])
    assert dag["2062"] / natt["2062"] == 1.0
    assert dag["2034"] / natt["2034"] == 1.0


def test_dagnatt_fangar_arbetsplatskommunen():
    """SCB:s tal ska ge Mora över 1 och Orsa under."""
    flode = {("2062", "2062"): 8360, ("2062", "2034"): 431,
             ("2034", "2062"): 1219, ("2034", "2034"): 1759}
    dag, natt = _dagnatt(flode, ["2062", "2034"])
    assert dag["2062"] / natt["2062"] > 1.05
    assert dag["2034"] / natt["2034"] < 0.85


def test_scb_flode_avgransas_till_scenariots_kommuner(tmp_path):
    """Jämförelsen måste gälla samma kommuner som modellen känner. En Morabo
    som pendlar till Falun är i SCB:s tal en pendlare, men Falun finns inte i
    modellen."""
    db = str(tmp_path / "db.sqlite3")
    _skriv_db(db, [
        {"home_municipality": "2062", "work_municipality": "2062",
         "year": 2023, "employed": 800},
        {"home_municipality": "2062", "work_municipality": "2034",
         "year": 2023, "employed": 100},
        {"home_municipality": "2062", "work_municipality": "2080",
         "year": 2023, "employed": 100},      # Falun: utanför scenariot
    ])
    flode, (ar, utanfor) = scb_flode(["2062", "2034"], db)
    assert ("2062", "2080") not in flode
    assert ar == 2023
    assert round(utanfor["2062"], 2) == 0.10


def test_senaste_aret_valjs(tmp_path):
    db = str(tmp_path / "db.sqlite3")
    _skriv_db(db, [
        {"home_municipality": "2062", "work_municipality": "2034",
         "year": 2019, "employed": 1},
        {"home_municipality": "2062", "work_municipality": "2034",
         "year": 2023, "employed": 431},
    ])
    flode, (ar, _) = scb_flode(["2062", "2034"], db)
    assert ar == 2023 and flode[("2062", "2034")] == 431


def test_saknad_tabell_ger_tomt(tmp_path):
    flode, meta = scb_flode(["2062"], str(tmp_path / "finns-inte.sqlite3"))
    assert flode == {} and meta is None
