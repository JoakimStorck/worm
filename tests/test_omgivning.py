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


def test_reservoaren_fordelas_pa_par_och_startdelen_ar_parens_stock():
    """Storleken är faktor gånger stocken, fördelad på par av ursprung och
    arbetskommun efter matrisen; startdelen är varje pars egen stock.
    Rättvik (2031) har två arbetskommuner, så att radernas ordning prövas.
    generate_individuals ersätts: den prövas för regionens invånare, här
    prövas fördelningen."""
    from core.scenariobuilder import ScenarioBuilder
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from conftest import FakeConfig
    conn = _db()
    conn.execute("INSERT INTO commuting VALUES ('2031', '2034', 2023, 10)")
    sb = ScenarioBuilder.__new__(ScenarioBuilder)
    sb.rng = np.random.default_rng(0)
    sb.cfg_reader = FakeConfig({"inpendling_reservoar_faktor": 2.0})
    sb._omgivning = Omgivning(conn, REGION)     # 2031->2062 40, 2031->2034 10, 2080->2034 5

    def gen(kod, befolkning, andel, u, year=None):
        n = int(round(befolkning * andel))
        return pd.DataFrame({"municipal_code": kod,
                             "status": ["unemployed"] * n + ["not_in_labor_force"] * (befolkning - n),
                             "pi_o": 1.0, "w_res": 0.7})
    sb.generate_individuals = gen
    fick_yrke = []                                  # yrket prövas för sig nedan
    sb._yrke_ur_arbetskommunen = lambda d: fick_yrke.append(len(d))
    res = sb.generate_inpendlingsreservoar(2024)
    assert sum(fick_yrke) == len(res), "inte alla fick yrket ur arbetskommunen"
    par = res.groupby(["municipal_code", "arbetskommun"]).size().to_dict()
    assert par == {("2031", "2062"): 80, ("2031", "2034"): 20, ("2080", "2034"): 10}
    start = res[res.extern_start].groupby(["municipal_code", "arbetskommun"]).size().to_dict()
    assert start == {("2031", "2062"): 40, ("2031", "2034"): 10, ("2080", "2034"): 5}
    assert (res["status"] == "extern").all() and res["extern"].all()
    assert res["w_neg"].isna().all()


def test_inpendlaren_soker_bara_i_sin_arbetskommun_och_utan_avstand():
    """Arbetskommunen är dragen ur matrisen, som bär avståndet: ingen
    avståndsdämpning och ingen pendlingskostnad, men bara vakanser där."""
    from core.matching_core import apply_once
    w = _varld(n_employers=4, size=2, application_window_days=40,
               commute_cost_per_km=1.0, commute_decay_km=0.001)
    w.jobs["municipal_code"] = ["2062"] * 4 + ["2034"] * 4
    w.jobs["x"] = 50000.0                       # 50 km bort
    w.individuals = _personer(["extern"], [True], arbetskommun="2034")
    w.prepare()
    np.random.seed(2)
    sokta = {apply_once(w, 0, float(t))[0] for t in range(1, 30)} - {None}
    assert sokta, "inpendlaren sökte inget: avståndet räknades"
    kommun = w.jobs.set_index("job_id").loc[list(sokta), "municipal_code"]
    assert set(kommun) == {"2034"}


# ---------------------------------------------------------------------------
# O4: utpendlingen
# ---------------------------------------------------------------------------

def _utvarld(andel=1.0, **sim):
    """Värld med omgivningens underlag: invånare i Mora (2062) utpendlar till
    Falun (2080) och Rättvik (2031) enligt _db, där Falun har ett enda yrke,
    B, och Rättvik ett, C."""
    w = _varld(utpendling_erbjudande_andel=andel, commute_cost_per_km=0.0, **sim)
    conn = _db()
    pd.DataFrame([("2080", "911", "N", "1", 2024, 50), ("2031", "912", "N", "1", 2024, 50)],
                 columns=["municipal_code", "ssyk_code", "sni_code", "sex", "year",
                          "employed"]).to_sql("employment_workplace_occupation_sni", conn,
                                              index=False)
    pd.DataFrame([("911", "B", 1.0), ("912", "C", 1.0)],
                 columns=["occupation_code", "onet_code", "share"]).to_sql(
        "ssyk3_onet_crosswalk", conn, index=False)
    pd.DataFrame({"onet_code": ["B", "C"], "chi": 0.3, "xi": 0.3, "x_occ": [0.3, 0.3],
                  "y_occ": [0.1, 0.1], "r_o": 0.27, "w_rel": 2.0, "r_req": 0.0,
                  "geom_source": "occupation"}).to_sql("onet_occupation_space", conn,
                                                       index=False)
    w.conn = conn
    w.cfg_reader.config["municipalities"] = ["2062", "2034"]
    return w


def test_invanaren_far_ett_erbjudande_utifran_langt_bort():
    """Destinationen ur matrisen och ingen avståndsdämpning i mötet: Falun
    ligger här 10 km bort i x, men med commute_decay_km = 1 hade mötet dämpats
    till noll."""
    from core.matching_core import externt_erbjudande
    w = _utvarld(commute_decay_km=1.0)
    w.individuals = _personer(["unemployed"], [False], municipal_code="2062")
    w.prepare()
    rng = np.random.default_rng(0)
    erbj = [externt_erbjudande(w, 0, 1.0, rng) for _ in range(400)]
    kommuner = pd.Series([e["kommun"] for e in erbj if e is not None])
    assert len(kommuner) > 300
    assert set(kommuner) == {"2080", "2031"}
    assert kommuner.value_counts(normalize=True)["2080"] == pytest.approx(0.75, abs=0.07)


def test_bara_invanare_utan_lofte_far_erbjudanden_och_takten_styr():
    from core.matching_core import externt_erbjudande
    w = _utvarld()
    # en anställd inpendlare, en invånare, en invånare med löfte
    w.individuals = _personer(["unemployed", "unemployed", "unemployed"], [True, False, False],
                              municipal_code="2062", pi_o=1.0)
    w.prepare()
    _anstall(w, 0, 0)
    w.individuals.at[2, "accepted_job_id"] = "J1"
    rng = np.random.default_rng(0)
    assert all(externt_erbjudande(w, 0, 1.0, rng) is None for _ in range(50)), \
        "en inpendlare fick ett utpendlingserbjudande"
    assert any(externt_erbjudande(w, 1, 1.0, rng) is not None for _ in range(50))
    assert externt_erbjudande(w, 2, 1.0, rng) is None
    w0 = _utvarld(andel=0.0)
    w0.individuals = _personer(["unemployed"], [False], municipal_code="2062")
    w0.prepare()
    assert all(externt_erbjudande(w0, 0, 1.0, rng) is None for _ in range(50))


def test_det_externa_jobbet_ar_ingen_vakans_och_upphor_nar_det_lamnas():
    from core.matching_core import externt_erbjudande, anta_externt
    from core.event_handlers import _become_unemployed
    from core.statistics.basic_stats import analyze_world
    w = _utvarld()
    w.individuals = _personer(["unemployed"], [False], municipal_code="2062")
    w.prepare()
    fore = analyze_world(w)
    rng = np.random.default_rng(1)
    erbj = next(e for e in (externt_erbjudande(w, 0, 1.0, rng) for _ in range(50)) if e)
    jid = anta_externt(w, 0, 1.0, erbj, omedelbart=True)
    pos = w.job_index()[jid]
    assert bool(w.jobs.at[pos, "extern"]) and not w.vacant_mask()[pos]
    assert w.individuals.at[0, "status"] == "employed"
    s = analyze_world(w)
    assert (s["out_commuters"], s["employed_individuals"]) == (1, 1)
    assert (s["total_jobs"], s["unmatched_jobs"]) == (fore["total_jobs"], fore["unmatched_jobs"])
    _become_unemployed(w, 0, 20.0)
    assert not bool(w.jobs.at[pos, "active"]), "det externa jobbet lever kvar"
    assert not w.vacant_mask()[pos], "det externa jobbet blev en vakans"


def test_utpendlaren_tilltrader_efter_fordrojning_under_korningen():
    from core.matching_core import externt_erbjudande, anta_externt
    w = _utvarld()
    w.individuals = _personer(["unemployed"], [False], municipal_code="2062")
    w.prepare()
    w._pushed = []
    orig = w._push_event
    w._push_event = lambda ev, _o=orig: (w._pushed.append(ev), _o(ev))[1]
    rng = np.random.default_rng(1)
    erbj = next(e for e in (externt_erbjudande(w, 0, 1.0, rng) for _ in range(50)) if e)
    jid = anta_externt(w, 0, 1.0, erbj)
    start = [e for e in w._pushed if e["event_type"] == "start_job"]
    assert len(start) == 1 and start[0]["params"]["job_id"] == jid
    assert start[0]["time"] > 1.0
    assert w.individuals.at[0, "accepted_job_id"] == jid


def test_uppstarten_ger_utpendlare_och_slutar_inte_for_tidigt():
    """Regionens enda vakans betalar inget, så ingen omgång tillsätter något i
    regionen. Omgångar med bara externa tillsättningar är inte tomma: alla fem
    ska bli utpendlare, två och två per omgång."""
    from core.matching_core import bootstrap_matching
    w = _utvarld(application_window_days=40)
    w.individuals = _personer(["unemployed"] * 5, [False] * 5, municipal_code="2062")
    w.jobs["active"] = [True] + [False] * (len(w.jobs) - 1)
    w.jobs["wage"] = 0.0
    w._vm_n = None
    bootstrap_matching(w, 0.0, log=None)
    held = w.jobs.set_index("job_id").loc[w.individuals["job_id"].dropna()]
    assert len(held) == 5 and held["extern"].all()


def test_ett_externt_jobb_ar_aldrig_en_vakans():
    """Skyddet i vakansmasken: även ett aktivt, obesatt och inte utlovat
    externt jobb är ingen vakans i regionen."""
    w = _varld()
    w.individuals = _personer(["unemployed"], [False])
    w.prepare()
    w.jobs.loc[0, "extern"] = True
    w._vm_n = None
    assert not w.vacant_mask()[0] and w.vacant_mask()[1]


def test_extern_ar_alltid_boolesk():
    """Invånarna fick NaN när de slogs ihop med reservoaren, och bool(NaN) är
    sant: ingen invånare fick något erbjudande."""
    w = _varld()
    w.individuals = _personer(["unemployed", "extern"], [np.nan, True])
    w.prepare()
    assert w.individuals["extern"].tolist() == [False, True]


def test_externt_erbjudande_betalar_ingen_pendlingskostnad():
    """Matrisen bär avståndet. Med kostnaden 0,1 per km och Falun 10 km bort
    hade överskottet varit negativt för varje erbjudande."""
    from core.matching_core import externt_erbjudande
    w = _utvarld()
    w.cfg_reader.config["simulation"]["commute_cost_per_km"] = 0.1
    w.individuals = _personer(["unemployed"], [False], municipal_code="2062",
                              x=0.0, y=-20000.0)
    w.prepare()
    rng = np.random.default_rng(3)
    erbj = [e for e in (externt_erbjudande(w, 0, 1.0, rng) for _ in range(200)) if e]
    assert len(erbj) > 150
    assert min(e["km"] for e in erbj) > 20


def test_inpendlarens_yrke_kommer_ur_arbetskommunens_jobb():
    """TAB4436 räknar dagbefolkningen, som innehåller inpendlarna. Mora har
    här bara yrket B, Orsa bara C; ursprunget spelar ingen roll."""
    from core.scenariobuilder import ScenarioBuilder
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from conftest import FakeConfig
    conn = _db()
    pd.DataFrame([("2062", "911", "N", "1", 2024, 50), ("2034", "912", "N", "1", 2024, 50)],
                 columns=["municipal_code", "ssyk_code", "sni_code", "sex", "year",
                          "employed"]).to_sql("employment_workplace_occupation_sni", conn,
                                              index=False)
    pd.DataFrame([("911", "B", 1.0), ("912", "C", 1.0)],
                 columns=["occupation_code", "onet_code", "share"]).to_sql(
        "ssyk3_onet_crosswalk", conn, index=False)
    geo = pd.DataFrame({"onet_code": ["B", "C"], "x_occ": [0.3, -0.4], "y_occ": [0.1, 0.2],
                        "r_o": 0.27, "chi": 0.3, "xi": 0.3, "geom_source": "occupation",
                        "w_rel": 1.0, "pi_rel": 1.0})
    geo.to_sql("onet_occupation_space", conn, index=False)
    sb = ScenarioBuilder.__new__(ScenarioBuilder)
    sb.conn = conn
    sb.rng = np.random.default_rng(0)
    sb.cfg_reader = FakeConfig({})
    sb.onet_space_df = geo.set_index("onet_code")
    sb._price_field = lambda: None
    d = pd.DataFrame({"municipal_code": ["2031"] * 4, "onet_code": ["X"] * 4,
                      "arbetskommun": ["2062", "2062", "2034", "2034"]})
    sb._yrke_ur_arbetskommunen(d)
    assert d["onet_code"].tolist() == ["B", "B", "C", "C"]
    assert d["last_onet_code"].tolist() == ["B", "B", "C", "C"]
    assert np.allclose(d["x_occ"].to_numpy()[:2], 0.3, atol=0.2)
    assert np.allclose(d["x_occ"].to_numpy()[2:], -0.4, atol=0.2)


def test_inpendlarens_erbjudande_provas_utan_pendlingskostnad_vid_stangningen():
    """Vid stängningen prövas överskottet igen, mot hennes läge nu. Med
    pendlingskostnaden avböjde inpendlarna nästan varje erbjudande."""
    from core.matching_core import current_surplus
    w = _varld(commute_cost_per_km=0.01)
    w.individuals = _personer(["extern", "unemployed"], [True, False])
    w.prepare()
    # w_res 0.3, erbjudandet 0.8, 60 km: 0.8 - 0.6 - 0.3 < 0 med kostnad
    assert current_surplus(w, 0, 0.8, 60.0) == pytest.approx(0.5)
    assert current_surplus(w, 1, 0.8, 60.0) == pytest.approx(-0.1)
