"""Startpopulationens utbildning givet yrket, steg 6a-ii (core/priming.py,
prima_utbildningen; docs/utbildningsmodell.md, beslut 5 alternativ b)."""
import os
import sqlite3
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import make_world  # noqa: E402
from core.occupations.competence import EDU_RADIUS2, EMPTY  # noqa: E402

LAGE = {"SJUK": (0.6, 0.2), "BUTIK": (-0.3, -0.4), "STAD": (-0.2, 0.5), "START": (0.3, 0.1)}


def _db(joint, cw, syss, arbl, kommun="2062"):
    """De tre utbildningstabellerna ur en fördelning (ssyk, nivå, inriktning)
    -> antal, 25-29 år, ett kön; befolkningen (25-34) har samma samband.
    cw: ssyk -> O*NET. syss och arbl: TAB6666:s antal per nivågrupp."""
    conn = sqlite3.connect(":memory:")
    j = pd.DataFrame([(o, l, f, n) for (o, l, f), n in joint.items()],
                     columns=["ssyk_code", "level", "field", "n"])
    bas = {"age_class": "25-29", "sex": "1", "year": 2024}
    of = j.groupby(["ssyk_code", "field"], as_index=False).n.sum().rename(columns={"n": "employed"})
    ol = j.groupby(["ssyk_code", "level"], as_index=False).n.sum().rename(columns={"n": "employed"})
    lf = j.groupby(["level", "field"], as_index=False).n.sum().rename(columns={"n": "population"})
    of.assign(**bas).to_sql("employment_occupation_field", conn, index=False)
    ol.assign(**bas).to_sql("employment_occupation_level", conn, index=False)
    lf.assign(age_class="25-34", sex="1", year=2024, background="S").to_sql(
        "population_level_field", conn, index=False)
    pd.DataFrame([(s, o, 1.0) for s, o in cw.items()],
                 columns=["occupation_code", "onet_code", "share"]).to_sql(
        "ssyk3_onet_crosswalk", conn, index=False)
    pd.DataFrame([{"onet_code": k, "chi": 0.3, "xi": 0.3, "x_occ": x, "y_occ": y, "r_o": 0.27,
                   "w_rel": 1.0, "r_req": 0.1, "geom_source": "occupation"}
                  for k, (x, y) in LAGE.items()]).to_sql("onet_occupation_space", conn, index=False)
    pd.DataFrame([{"municipal_code": kommun, "level_group": g, "employed": syss.get(g, 0),
                   "unemployed": arbl.get(g, 0), "period": "2024M11"}
                  for g in ("21", "3", "4", "5", "61", "US")]).to_sql(
        "employment_education_municipality", conn, index=False)
    return conn


def _varld(conn, anstallda_ssyk, n_arbetslosa=0, kommun="2062"):
    """Anställda på var sitt jobb med jobbets SSYK, och arbetslösa med
    startyrket START. Alla 27 år. Utbildningen från genereringen är nivå 3,
    vars cirkel ligger på startyrkets plats."""
    n_anst = len(anstallda_ssyk)
    w = make_world(n_employers=max(n_anst, 1), size=1)
    n = n_anst + n_arbetslosa
    w.jobs["ssyk_code"] = None
    for k, s in enumerate(anstallda_ssyk):
        w.jobs.at[k, "ssyk_code"] = s
    w.individuals = pd.DataFrame({
        "individual_id": [f"i{k}" for k in range(n)],
        "status": ["employed"] * n_anst + ["unemployed"] * n_arbetslosa,
        "job_id": pd.Series([w.jobs.at[k, "job_id"] for k in range(n_anst)] + [None] * n_arbetslosa,
                            dtype="object"),
        "age": 27.0, "municipal_code": kommun, "extern": False,
        "w_res": 0.5, "chi": 0.3, "xi": 0.3, "r_i": 0.0, "x_occ": 0.3, "y_occ": 0.1,
        "x": 0.0, "y": 0.0, "onet_code": "START", "last_onet_code": "START",
        "r_o_home": 0.27, "tenure_years": 5.0, "education_level": 3,
        "unemployed_since": 0.0, "w_last": 0.5,
        "propensity_start_education": 0.0, "propensity_internal_training": 0.0,
        "propensity_quit_job": 0.0, "propensity_career_break": 0.0,
        "propensity_internal_job_change": 0.0})
    w.prepare()
    w.conn = conn
    w.__dict__.pop("_geom_df", None)          # byggd utan databas i prepare
    return w


def _utbildningscirklar(w, i):
    c = w.circles
    return {c.key_names[c.key[i, k]]: (c.x[i, k], c.y[i, k], c.rho2[i, k])
            for k in np.flatnonzero(c.key[i] != EMPTY)
            if c.key_names[c.key[i, k]].startswith("EDU:")}


JOINT = {("222", "6", "7"): 100, ("522", "4", "0"): 100, ("911", "2", "0"): 100}
CW = {"222": "SJUK", "522": "BUTIK", "911": "STAD"}


def test_utbildningen_dras_givet_yrket_och_cirkeln_hamnar_dar_den_pekade():
    """Sjuksköterskan (222) har bara eftergymnasial vårdutbildning i
    fördelningen: cirkeln läggs på utbildningens yrke med nivåns radie, och
    genereringens cirkel (nivå 3 på startyrket) tas bort. Butiksbiträdet
    har allmän gymnasial utbildning: cirkeln i origo med radien 1. Den med
    förgymnasial utbildning har bara grundskolans cirkel."""
    from core.priming import prima_utbildningen
    conn = _db(JOINT, CW, syss={"61": 1, "4": 1, "21": 1}, arbl={"4": 1})
    w = _varld(conn, ["222", "522", "911"])
    assert "EDU:3" in _utbildningscirklar(w, 0), "fixturen: genereringens cirkel"
    prima_utbildningen(w, np.random.default_rng(0))
    ind = w.individuals
    assert list(ind.education_level[:3]) == [6, 4, 2]
    assert list(ind.education_field[:3]) == ["7", "0", "0"]
    assert list(ind.education_ssyk[:3]) == ["222", None, None]
    e0 = _utbildningscirklar(w, 0)
    assert set(e0) == {"EDU:0", "EDU:6"}
    assert e0["EDU:6"] == pytest.approx((*LAGE["SJUK"], EDU_RADIUS2[6]))
    assert _utbildningscirklar(w, 1)["EDU:4"] == pytest.approx((0.0, 0.0, 1.0))
    assert set(_utbildningscirklar(w, 2)) == {"EDU:0"}


def test_den_arbetslosa_far_yrket_ur_sitt_startyrke():
    """De arbetslösa har bara en O*NET-kod; SSYK dras ur crosswalken."""
    from core.priming import prima_utbildningen
    conn = _db(JOINT, dict(CW, **{"522": "START"}), syss={"61": 1, "4": 1}, arbl={"4": 1})
    w = _varld(conn, ["222"], n_arbetslosa=1)
    prima_utbildningen(w, np.random.default_rng(0))
    assert w.individuals.education_level.iloc[1] == 4


LUTAD = {("222", "6", "7"): 50, ("222", "4", "7"): 50}


def test_kommunens_sysselsatta_far_kommunens_nivaer():
    """Rikets fördelning givet yrket ger hälften eftergymnasial; kommunens
    sysselsatta har 80 procent. Utan lutningen blev Ovansiljans andel 27
    procent mot TAB6666:s 20,5."""
    from core.priming import prima_utbildningen
    conn = _db(LUTAD, {"222": "SJUK"}, syss={"61": 80, "4": 20}, arbl={"4": 1})
    w = _varld(conn, ["222"] * 400)
    prima_utbildningen(w, np.random.default_rng(2))
    assert (w.individuals.education_level == 6).mean() == pytest.approx(0.8, abs=0.05)


def test_de_arbetslosa_far_en_egen_lutning():
    """I Ovansiljan har 31 procent av de arbetslösa förgymnasial utbildning
    mot 10 procent av de sysselsatta. Utan en egen lutning fick de
    arbetslösa de sysselsattas fördelning."""
    from core.priming import prima_utbildningen
    conn = _db(LUTAD, {"222": "SJUK", "000": "START"}, syss={"61": 50, "4": 50},
               arbl={"61": 10, "4": 90})
    # START hör till 222 via crosswalken; lägg en rad för det
    conn.execute("UPDATE ssyk3_onet_crosswalk SET occupation_code='222' WHERE onet_code='START'")
    w = _varld(conn, ["222"] * 200, n_arbetslosa=400)
    prima_utbildningen(w, np.random.default_rng(3))
    ind = w.individuals
    assert (ind.education_level[ind.status == "unemployed"] == 4).mean() == pytest.approx(0.9, abs=0.05)
    assert (ind.education_level[ind.status == "employed"] == 4).mean() == pytest.approx(0.5, abs=0.08)


def test_en_kommun_utan_niva_i_tab6666_ar_ett_fel():
    from core.priming import prima_utbildningen
    conn = _db(JOINT, CW, syss={"61": 1}, arbl={"4": 1}, kommun="2062")
    w = _varld(conn, ["222"], kommun="2034")
    with pytest.raises(ValueError, match="2034"):
        prima_utbildningen(w, np.random.default_rng(0))
