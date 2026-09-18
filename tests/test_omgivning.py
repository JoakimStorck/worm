"""Omgivningens underlag (core/omgivning.py, docs/omgivning.md steg O1)."""
import sqlite3

import numpy as np
import pandas as pd
import pytest

from core.omgivning import Omgivning

REGION = ["2062", "2034"]          # Mora och Orsa; Falun (2080) och Rättvik (2031) utanför


def _db(utan=()):
    conn = sqlite3.connect(":memory:")
    if "commuting" not in utan:
        rader = [("2062", "2062", 100), ("2062", "2034", 10), ("2034", "2062", 20),
                 ("2034", "2034", 50), ("2062", "2080", 30), ("2062", "2031", 10),
                 ("2031", "2062", 40), ("2080", "2034", 5), ("2080", "2080", 999)]
        pd.DataFrame([(b, a, 2023, n) for b, a, n in rader]
                     + [("2062", "2080", 2020, 777)],
                     columns=["home_municipality", "work_municipality", "year",
                              "employed"]).to_sql("commuting", conn, index=False)
    if "deso" not in utan:
        def ruta(x0, y0):
            return f"POLYGON (({x0} {y0}, {x0 + 1000} {y0}, {x0 + 1000} {y0 + 1000}, " \
                   f"{x0} {y0 + 1000}, {x0} {y0}))"
        pd.DataFrame([("2080A0010", 300, ruta(0, 0)), ("2080A0020", 100, ruta(10000, 0)),
                      ("2080A0030", 0, ruta(50000, 0)), ("2031A0010", 50, ruta(0, 20000))],
                     columns=["deso_code", "population", "geom_wkt"]).to_sql(
            "deso", conn, index=False)
    return conn


def test_matrisen_delas_i_inom_ut_och_in():
    o = Omgivning(_db(), REGION)
    assert o.ar == 2023, "äldre år ska inte läsas"
    assert int(o.inom.n.sum()) == 180
    assert o.utpendling.set_index("arb").n.to_dict() == {"2080": 30, "2031": 10}
    assert set(zip(o.inpendling.bo, o.inpendling.arb)) == {("2031", "2062"), ("2080", "2034")}
    assert (o.inpendling.bo.isin(REGION) | o.utpendling.arb.isin(REGION)).sum() == 0


def test_nivaerna_raknar_pendlarna():
    """Kolumnsumman är alla jobb i kommunen, radsumman alla sysselsatta
    invånare -- till skillnad från delmatrisen i jobbandelar."""
    o = Omgivning(_db(), [2062, 2034])            # heltalskoder duger
    assert o.jobb("2062") == 100 + 20 + 40
    assert o.sysselsatta("2062") == 100 + 10 + 30 + 10
    assert o.andel_utpendling("2062") == pytest.approx(40 / 150)
    assert o.andel_inpendling("2034") == pytest.approx(5 / 65)


def test_destination_och_ursprung_dras_ur_matrisen():
    o = Omgivning(_db(), REGION)
    rng = np.random.default_rng(1)
    dest = pd.Series([o.dra_destination("2062", rng) for _ in range(4000)])
    assert dest.value_counts(normalize=True)["2080"] == pytest.approx(0.75, abs=0.03)
    assert set(o.dra_ursprung("2062", rng) for _ in range(50)) == {"2031"}
    with pytest.raises(ValueError, match="Ingen utpendling från 2034"):
        o.dra_destination("2034", rng)


def test_platsen_ar_en_deso_dragen_med_befolkningen():
    o = Omgivning(_db(), REGION)
    rng = np.random.default_rng(2)
    xs = pd.Series([o.dra_plats("2080", rng)[0] for _ in range(4000)])
    assert set(xs.round()) == {500.0, 10500.0}, "tomma DeSO ska inte dras"
    assert (xs == 500.0).mean() == pytest.approx(0.75, abs=0.03)
    with pytest.raises(ValueError, match="2081"):
        o.dra_plats("2081", rng)


def test_saknat_underlag_kastar():
    with pytest.raises(ValueError, match="commuting saknas"):
        Omgivning(_db(utan=("commuting",)), REGION)
    with pytest.raises(ValueError, match="saknar kommunerna"):
        Omgivning(_db(), ["2062", "2039"])


# ---------------------------------------------------------------------------
# O2: bokföringen med öppen rand
# ---------------------------------------------------------------------------

def _randvarld():
    """Invånare: tre arbetar i regionen, en utpendlar, två arbetslösa, en
    utanför arbetskraften. Två inpendlare. Regionen har fem aktiva jobb (alla
    tillsatta: tre invånare, två inpendlare) och ett förstört; utpendlarens
    jobb är externt."""
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from conftest import make_world
    w = make_world(n_employers=1, size=7)
    w.jobs = w.jobs.iloc[:7].copy()
    w.jobs["active"] = [True] * 5 + [False, True]
    w.jobs["extern"] = [False] * 6 + [True]
    w.individuals = pd.DataFrame({
        "individual_id": [f"i{k}" for k in range(9)],
        "status": ["employed"] * 4 + ["unemployed"] * 2 + ["not_in_labor_force"]
                  + ["employed"] * 2,
        "extern": [False] * 7 + [True, True],
        "job_id": list(w.jobs.job_id.iloc[[0, 1, 2, 6]]) + [None] * 3
                  + list(w.jobs.job_id.iloc[[3, 4]]),
    })
    innehavare = {0: "i0", 1: "i1", 2: "i2", 3: "i7", 4: "i8", 6: "i3"}
    w.jobs["individual_id"] = [innehavare.get(k) for k in range(7)]
    return w


def test_arbetskraften_ar_invanarna_och_jobben_regionens():
    from core.statistics.basic_stats import analyze_world
    s = analyze_world(_randvarld())
    assert (s["employed_individuals"], s["unemployed_individuals"],
            s["individuals_not_in_labour_force"]) == (4, 2, 1)
    assert s["total_individuals"] == 7, "inpendlarna är inte invånare"
    assert (s["total_jobs"], s["unmatched_jobs"]) == (5, 0), "det externa jobbet är inte regionens"
    assert (s["in_commuters"], s["out_commuters"]) == (2, 1)
    L = s["employed_individuals"] + s["unemployed_individuals"]
    U = s["unemployed_individuals"]
    assert U == L - s["total_jobs"] + s["unmatched_jobs"] \
        + s["in_commuters"] - s["out_commuters"]
    assert U != L - s["total_jobs"] + s["unmatched_jobs"], \
        "fixturen ska skilja den nya identiteten från den gamla"


def test_tidsserien_raknar_randen_och_gamla_loggar_ar_slutna():
    from core.analysis.eventlog import timeseries_table
    rad = {"event": "new_month", "time": 30.0, "month": 1, "employed": 4, "unemployed": 2,
           "unmatched_jobs": 0, "active_jobs": 5, "posted": 0, "not_in_labour_force": 1}
    ts = timeseries_table([dict(rad, in_commuters=2, out_commuters=1),
                           dict(rad, unmatched_jobs=1)])   # sluten: 4 = 5 - 1
    assert ts["identity_residual"].tolist() == [0.0, 0.0]


def test_varlden_bar_kolumnen_extern():
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from conftest import make_world
    w = make_world(n_employers=2, size=2)
    w.individuals = pd.DataFrame({"individual_id": ["a"], "status": ["unemployed"],
                                  "job_id": [None]})
    w.prepare()
    assert "extern" in w.individuals.columns and "extern" in w.jobs.columns
    assert not w.individuals["extern"].any() and not w.jobs["extern"].any()


# ---------------------------------------------------------------------------
# O3a: jobbmålet och de sysselsatta invånarna med öppen rand
# ---------------------------------------------------------------------------

def _byggare(conn):
    from core.scenariobuilder import ScenarioBuilder
    sb = ScenarioBuilder.__new__(ScenarioBuilder)
    sb.conn = conn
    return sb


def test_marginalerna_ar_hela_kolumn_och_radsumman():
    """Jobben räknar inpendlarna och invånarna utpendlarna. Delmatrisen, som
    stängde scenariot, gav Mora 120 jobb och 110 sysselsatta här."""
    m = _byggare(_db()).pendlingsmarginaler([2062, 2034])
    assert m["jobb"] == {"2062": 160, "2034": 65}
    assert m["boende"] == {"2062": 150, "2034": 70}


def test_en_ensam_kommun_far_ocksa_sin_rand():
    """Scenarier med en kommun hoppade över matrisen helt."""
    m = _byggare(_db()).pendlingsmarginaler(["2034"])
    assert m == {"jobb": {"2034": 65}, "boende": {"2034": 70}}


def test_utan_matris_ingen_tyst_reserv():
    with pytest.raises(ValueError, match="commuting saknas"):
        _byggare(_db(utan=("commuting",))).pendlingsmarginaler(REGION)
