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


# ---------------------------------------------------------------------------
# O3b: inpendlingsreservoaren
# ---------------------------------------------------------------------------

def _varld(n_employers=4, size=2, **sim):
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from conftest import make_world
    return make_world(n_employers=n_employers, size=size, simulation=sim)


def _personer(statusar, extern, **extra):
    n = len(statusar)
    d = {"individual_id": [f"p{k}" for k in range(n)], "status": list(statusar),
         "extern": list(extern), "job_id": pd.Series([None] * n, dtype="object"),
         "w_res": 0.3, "chi": 0.3, "xi": 0.3, "r_i": 0.0, "x_occ": 0.3, "y_occ": 0.1,
         "x": 0.0, "y": 0.0, "w_neg": np.nan, "q_last": np.nan,
         "propensity_start_education": 0.0, "propensity_internal_training": 0.0,
         "propensity_quit_job": 0.0, "propensity_career_break": 0.0,
         "propensity_internal_job_change": 0.0}
    d.update(extra)
    return pd.DataFrame(d, index=range(n))


def _anstall(w, idx, pos):
    jid = w.jobs.at[pos, "job_id"]
    w.individuals.at[idx, "status"] = "employed"
    w.individuals.at[idx, "job_id"] = jid
    w.jobs.at[pos, "individual_id"] = w.individuals.at[idx, "individual_id"]
    w.set_job_filled(jid, True)
    return jid


def test_en_extern_sokande_ar_behorig_och_kan_vinna():
    """Utan behörigheten föll varje extern ansökan tyst i urvalet: 12 048
    ansökningar och ingen inpendlare på två år."""
    from core.event_handlers import handle_close_vacancy
    w = _varld(application_window_days=40)
    w._pushed = []
    orig = w._push_event
    w._push_event = lambda ev, _o=orig: (w._pushed.append(ev), _o(ev))[1]
    w.individuals = _personer(["unemployed", "extern"], [False, True])
    jid = w.jobs.iloc[0]["job_id"]
    for i, q in enumerate((0.31, 0.92)):
        w.file_application(jid, i, 0.0, q=q, w_neg=0.8, surplus=0.1, commute_km=5.0)
    handle_close_vacancy({"time": 40.0, "agent_id": 0, "event_type": "close_vacancy",
                          "params": {"job_id": jid}}, w)
    vinnare = [e["agent_id"] for e in w._pushed if e["event_type"] == "start_job"]
    assert vinnare == [1]


def test_inpendlaren_som_mister_jobbet_atergar_till_omgivningen():
    """Hon blir inte arbetslös i regionen: hon ingår inte i arbetskraften."""
    from core.event_handlers import handle_destroy_job, _become_unemployed
    from core.statistics.basic_stats import analyze_world
    w = _varld()
    w.individuals = _personer(["unemployed", "unemployed", "unemployed"],
                              [True, True, False], pi_o=1.2)
    w.prepare()
    j0 = _anstall(w, 0, 0)
    _anstall(w, 1, 1)
    _anstall(w, 2, 2)
    handle_destroy_job({"time": 10.0, "agent_id": None, "event_type": "destroy_job",
                        "params": {"job_id": j0}}, w)
    _become_unemployed(w, 1, 12.0)
    _become_unemployed(w, 2, 12.0)
    assert w.individuals["status"].tolist() == ["extern", "extern", "unemployed"]
    assert w.individuals["job_id"].isna().all()
    assert w.individuals.at[0, "w_res"] == pytest.approx(0.7 * 1.2)
    assert np.isfinite(w.individuals.at[0, "next_search_time"])
    s = analyze_world(w)
    assert (s["unemployed_individuals"], s["in_commuters"]) == (1, 0)


def test_reservoaren_soker_med_egen_takt():
    w = _varld(inpendling_sokfaktor=2.0, on_the_job_search_factor=5.0)
    w.individuals = _personer(["extern", "employed"], [True, False])
    np.random.seed(0)
    ext = [w.search_interval(0, 0.0) for _ in range(4000)]
    ans = [w.search_interval(1, 0.0) for _ in range(4000)]
    assert np.mean(ext) / np.mean(ans) == pytest.approx(2.0 / 5.0, rel=0.1)


def test_reservoaren_far_ansoka():
    """apply_once släppte bara igenom anställda och arbetslösa."""
    from core.matching_core import apply_once
    w = _varld(application_window_days=40)
    w.individuals = _personer(["extern"], [True])
    w.prepare()
    np.random.seed(1)
    assert apply_once(w, 0, 1.0)[0] is not None


def test_reservoaren_aldras_inte_och_gar_inte_i_pension():
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from test_alder import _varld_med_individer, _arsskifte, _profil
    # hasarden 1 vid 71, den nya åldern: invånaren som fyller 71 lämnar säkert
    # Inpendlaren är redan 71: hasarden är 1 för henne utan att hon åldras,
    # så pensionsundantaget prövas skilt från åldersundantaget.
    w = _varld_med_individer([70.0, 71.0], ["employed", "employed"],
                             profil=_profil({71: 1.0}))
    w.individuals["extern"] = [False, True]
    _arsskifte(w)
    assert w.individuals["age"].tolist() == [71.0, 71.0], "inpendlaren åldrades"
    assert w.individuals.at[0, "status"] == "not_in_labor_force", "fixturen ska pensionera invånaren"
    assert w.individuals.at[1, "status"] == "employed", "inpendlaren pensionerades"


def test_uppstarten_tar_med_reservoarens_startdel():
    from core.matching_core import bootstrap_matching
    w = _varld(n_employers=10, size=2, application_window_days=40)
    w.individuals = _personer(["extern"] * 2, [True] * 2, extern_start=[True, False])
    w.jobs["r_req"] = 0.0
    bootstrap_matching(w, 0.0, log=None)
    assert w.individuals["status"].tolist() == ["employed", "extern"]


def test_uppehall_for_en_inpendlare_ar_en_aterkomst_till_omgivningen():
    from core.event_handlers import handle_career_break
    w = _varld()
    w.individuals = _personer(["unemployed"], [True], pi_o=1.0)
    w.prepare()
    _anstall(w, 0, 0)
    handle_career_break({"time": 5.0, "agent_id": 0, "event_type": "career_break",
                         "params": {}}, w)
    assert w.individuals.at[0, "status"] == "extern"


def test_reservoaren_fordelas_pa_ursprung_och_startdelen_ar_stocken():
    """Storleken är faktor gånger stocken, fördelad efter inpendlingen;
    startdelen är stocken. generate_individuals ersätts: den prövas för
    regionens invånare, här prövas fördelningen."""
    from core.scenariobuilder import ScenarioBuilder
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from conftest import FakeConfig
    sb = ScenarioBuilder.__new__(ScenarioBuilder)
    sb.rng = np.random.default_rng(0)
    sb.cfg_reader = FakeConfig({"inpendling_reservoar_faktor": 2.0})
    sb._omgivning = Omgivning(_db(), REGION)          # inpendling 40 + 5 = 45
    anrop = {}

    def gen(kod, befolkning, andel, u, year=None):
        anrop[kod] = befolkning
        n = int(round(befolkning * andel))
        return pd.DataFrame({"municipal_code": kod, "status": ["unemployed"] * n
                             + ["not_in_labor_force"] * (befolkning - n),
                             "pi_o": 1.0, "w_res": 0.7})
    sb.generate_individuals = gen
    res = sb.generate_inpendlingsreservoar(2024)
    assert res["municipal_code"].value_counts().to_dict() == {"2031": 80, "2080": 10}
    assert (res["status"] == "extern").all() and res["extern"].all()
    assert int(res["extern_start"].sum()) == 45
    assert res["w_neg"].isna().all()
