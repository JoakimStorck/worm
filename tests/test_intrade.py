"""Inträdet, 6b-2 (core/intrade.py, docs/intradet.md)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import make_world  # noqa: E402
from test_priming_utbildning import _db as _utb_db  # noqa: E402

from core.intrade import Intradesplan, avslutningsaldrar  # noqa: E402

JOINT = {("222", "6", "7"): 100, ("522", "4", "0"): 100, ("911", "2", "0"): 100}
CW = {"222": "SJUK", "522": "BUTIK", "911": "STAD"}


def _studie(storlek=lambda a: 100 + 100 * (a % 2)):
    """TAB3731 i litet format. Andelen icke-studerande med nivå 4 går från 0
    till 0,6 vid 19; nivå 6 från 0 till 0,1 vid 23 och 0,3 vid 24; nivå 2
    till 0,05 vid 17 och till 0,10 vid 25 (vuxna, ska inte räknas). Årskullarna
    är olika stora, så antalen stiger och faller utan att andelarna gör det."""
    rader = []
    for a in list(range(16, 30)) + [31]:
        n = storlek(a)
        s4 = 0.6 if a >= 19 else 0.0
        s6 = 0.3 if a >= 24 else (0.1 if a == 23 else 0.0)
        s2 = 0.10 if a >= 25 else (0.05 if a >= 17 else 0.0)
        alder = "30-34" if a == 31 else str(a)
        for l, s in (("4", s4), ("6", s6), ("2", s2)):
            rader.append((alder, "0", l, n * s))
        rader.append((alder, "H", "4", n * (1 - s4 - s6 - s2)))
    return pd.DataFrame(rader, columns=["age", "study", "level", "population"])


def test_avslutningsaldern_ur_andelarna_och_skolnivaerna_i_skolaldern():
    d = avslutningsaldrar(_studie())
    a4, p4 = d["4"]
    assert dict(zip(a4[p4 > 0], p4[p4 > 0])) == {19: pytest.approx(1.0)}
    a6, p6 = d["6"]
    assert dict(zip(a6[p6 > 0], p6[p6 > 0])) == {23: pytest.approx(1 / 3), 24: pytest.approx(2 / 3)}
    # förgymnasial: bara ökningen i skolåldern, inte de vuxnas vid 25
    a2, p2 = d["2"]
    assert dict(zip(a2[p2 > 0], p2[p2 > 0])) == {17: pytest.approx(1.0)}
    assert set(d["7"][0]) == {30, 31, 32, 33}


def _db():
    conn = _utb_db(JOINT, CW, syss={"61": 1, "4": 1, "21": 1}, arbl={"4": 1})
    fl = pd.DataFrame([("2062", g, ak, "population_2", n, "2023-2024")
                       for g, n in (("03", 60), ("05", 40)) for ak in ("25-29", "30-34")],
                      columns=["municipal_code", "edu_group", "age_class", "measure", "value", "period"])
    fl.to_sql("education_flows_municipality", conn, index=False)
    _studie().assign(sex="1", employment="FÖRV", year=2024).to_sql(
        "population_study_education", conn, index=False)
    return conn


# Platån varierar mellan åldrarna och toppar vid q: andelen som aldrig går in
# är 1 - toppen, inte 1 - medlet.
PLATA = lambda q: {"2062": pd.Series({a: (q - 0.002 * abs(a - 45) if 30 <= a <= 54 else 0.5)
                                      for a in range(16, 75)})}


def test_planen_tar_kommunens_niva_och_villkoras_pa_aldern():
    """TAB6928 har gymnasial och lång eftergymnasial som grupper; inom
    grupperna har riket bara nivå 4 och 6 här. Kommunen: 60 och 40."""
    p = Intradesplan(_db(), PLATA(0.9))
    np.testing.assert_allclose(p.nivafordelning("2062"), [0, 0, 0, 0.6, 0, 0.4, 0])
    assert p.aldrig_in("2062") == pytest.approx(0.1)
    rng = np.random.default_rng(0)
    # den som redan är 21 och studerar kan inte ha gymnasiet som slutmål
    assert {p.dra("2062", rng, efter_alder=21)[0] for _ in range(50)} == {"6"}
    with pytest.raises(ValueError, match="2034"):
        p.nivafordelning("2034")


STUDIE_PARAM = {"intrade_ansprak_percentil": 0.5, "studerande_krav_kvantil": 0.25,
                "studerande_max_km": 20, "studerande_ansprak_percentil": 0.1,
                "studerande_sokfaktor": 6.0}


def _varld(statusar, aldrar, q=1.0, sim=None, **extra):
    sim = sim or {}
    w = make_world(n_employers=10, size=1, simulation=dict(STUDIE_PARAM, **sim))
    w.jobs["wage"] = np.linspace(0.6, 1.4, len(w.jobs))
    n = len(statusar)
    w.individuals = pd.DataFrame({
        "individual_id": [f"i{k}" for k in range(n)], "status": statusar,
        "job_id": pd.Series([None] * n, dtype="object"), "age": aldrar,
        "municipal_code": "2062", "extern": False, "w_res": 0.9, "w_last": np.nan,
        "chi": 0.3, "xi": 0.3, "r_i": 0.0, "x_occ": 0.3, "y_occ": 0.1, "x": 0.0, "y": 0.0,
        "onet_code": "START", "last_onet_code": "START", "r_o_home": 0.27,
        "tenure_years": 0.0, "education_level": np.nan, "unemployed_since": np.nan,
        "w_rel_med": np.nan, "w_rel_sd": np.nan, "p_claim0": np.nan,
        "propensity_start_education": 0.0, "propensity_internal_training": 0.0,
        "propensity_quit_job": 0.0, "propensity_career_break": 0.0,
        "propensity_internal_job_change": 0.0, **extra})
    w.prepare()
    w.conn = _db()
    w.__dict__.pop("_geom_df", None)
    w.participation = PLATA(q)
    w._pushed = []
    orig = w._push_event
    w._push_event = lambda ev, _o=orig: (w._pushed.append(ev), _o(ev))[1]
    return w


def test_planen_gor_henne_till_student_och_schemalagger_intradet():
    from core.intrade import tilldela_plan
    w = _varld(["not_in_labor_force"], [16.0])
    l, f, a, in_ = tilldela_plan(w, 0, 100.0, np.random.default_rng(1))
    assert w.individuals.at[0, "status"] == "student"
    ev = [e for e in w._pushed if e["event_type"] == "intrade"]
    assert len(ev) == 1
    assert 100.0 + (a - 16) * 365.25 <= ev[0]["time"] < 100.0 + (a - 15) * 365.25


def _in(w, idx, t):
    from core.event_handlers import handle_intrade
    handle_intrade({"time": t, "agent_id": idx, "event_type": "intrade", "params": {}}, w)


def test_intradet_lagger_utbildningen_och_anspraket_vid_medianen():
    """Sjuksköterskeutbildningen läggs på utbildningens yrke; genereringens
    slumpade yrke rensas; anspråket är medianen i relevansfördelningen, och
    hon söker."""
    from core.occupations.competence import EDU_RADIUS2
    w = _varld(["student"], [24.0], plan_level="6", plan_field="7", plan_entry_age=24,
               plan_enters=True)
    _in(w, 0, 500.0)
    ind, c = w.individuals, w.circles
    assert ind.at[0, "status"] == "unemployed"
    assert ind.at[0, "education_level"] == 6 and ind.at[0, "education_ssyk"] == "222"
    assert pd.isna(ind.at[0, "onet_code"]) and pd.isna(ind.at[0, "w_last"])
    k = c.latest(0, "EDU:6")
    assert (c.x[0, k], c.y[0, k], c.rho2[0, k]) == pytest.approx((0.6, 0.2, EDU_RADIUS2[6]))
    assert ind.at[0, "p_claim0"] == pytest.approx(0.5)
    assert ind.at[0, "w_res"] == pytest.approx(ind.at[0, "w_rel_med"])
    assert ind.at[0, "unemployed_since"] == pytest.approx(500.0)
    assert any(e["event_type"] == "start_job_search" and e["agent_id"] == 0 for e in w._pushed)


def test_anspraket_sjunker_ocksa_utan_tidigare_lon():
    """Anspråkets uppdatering återvände när senaste lön saknades; inträdaren
    hade då behållit sitt startanspråk för alltid."""
    from core.event_handlers import _uppdatera_reservation
    w = _varld(["student"], [24.0], plan_level="6", plan_field="7", plan_entry_age=24,
               plan_enters=True)
    _in(w, 0, 500.0)
    fore = float(w.individuals.at[0, "w_res"])
    _uppdatera_reservation(w, 0, t_now=500.0 + 400)
    assert float(w.individuals.at[0, "w_res"]) < fore - 1e-6


def test_den_som_aldrig_gar_in_hamnar_utanfor():
    w = _varld(["student"], [19.0], plan_level="4", plan_field="0", plan_entry_age=19,
               plan_enters=False)
    _in(w, 0, 500.0)
    assert w.individuals.at[0, "status"] == "not_in_labor_force"
    assert w.individuals.at[0, "education_level"] == 4
    assert not any(e["event_type"] == "start_job_search" for e in w._pushed)


def test_arsskiftet_ger_de_nya_sextonaringarna_en_plan():
    from core.intrade import nya_sextonaringar
    w = _varld(["not_in_labor_force", "not_in_labor_force", "employed", "not_in_labor_force"],
               [16.0, 15.0, 16.0, 16.0], extern=[False, False, False, True])
    assert nya_sextonaringar(w, 365.25) == 1
    assert list(w.individuals.status) == ["student", "not_in_labor_force", "employed",
                                          "not_in_labor_force"]
    assert nya_sextonaringar(w, 365.25) == 0, "en plan till, fast hon redan har en"
    # den som hoppat av vid 16 och aldrig går in står utanför, med sin plan
    w.individuals.at[0, "status"] = "not_in_labor_force"
    assert nya_sextonaringar(w, 365.25) == 0


def test_arsskiftet_med_demografi_gor_femtonaringen_till_student():
    """Kopplingen i _aldras_och_pensioneras: åldrandet först, sedan planen."""
    from core.event_handlers import _aldras_och_pensioneras
    w = _varld(["not_in_labor_force"], [15.0])
    ut = _aldras_och_pensioneras(w, {"time": 365.25, "agent_id": None, "event_type": "new_year",
                                     "params": {"year": 2025}})
    assert w.individuals.at[0, "status"] == "student" and ut["new_students"] == 1


def test_startens_unga_blir_studerande_med_en_plan_efter_sin_alder():
    """Bland dem som inte förvärvsarbetar studerar alla vid 20 och ingen vid
    25 (raderna byggs här). _studie har också förvärvsarbetande, som vid 20
    till en tredjedel studerar; räknades de med blev andelen 0,68. Den
    20-åriga studenten kan inte ha gymnasiet som slutmål: nivå 4 avslutas
    vid 19."""
    from core.intrade import andel_studerande, prima_unga
    w = _varld(["not_in_labor_force", "not_in_labor_force", "employed", "not_in_labor_force"],
               [20.0, 25.0, 20.0, 40.0])
    rader = []
    for a in range(16, 30):
        # nivå 5 finns inte i planen här, så raderna rör bara andelen studerande
        # och de skalas med årskullen, som resten av _studie
        rader += [(str(a), "H" if a < 22 else "0", "5", "EJFÖRV", 100 + 100 * (a % 2))]
    rader += [("30-34", "0", "5", "EJFÖRV", 200)]      # också klassen 30-34, som i _studie
    pd.DataFrame(rader, columns=["age", "study", "level", "employment", "population"]).assign(
        sex="1", year=2024).to_sql("population_study_education", w.conn, index=False,
                                   if_exists="append")
    assert andel_studerande(w.conn)[20] == pytest.approx(1.0)
    ut = prima_unga(w, 0.0, np.random.default_rng(0))
    assert list(w.individuals.status) == ["student", "not_in_labor_force", "employed",
                                          "not_in_labor_force"]
    assert (ut["unga_studerande"], ut["unga_utanfor"]) == (1, 1)
    assert w.individuals.at[0, "plan_level"] == "6" and int(w.individuals.at[0, "plan_entry_age"]) > 20


def test_primingen_gor_de_unga_till_studerande():
    """Kopplingen i prima_startpopulationen."""
    from core.priming import prima_startpopulationen
    w = _varld(["not_in_labor_force"], [17.0])
    pd.DataFrame([("17", "H", "4", "EJFÖRV", 100)] + [(str(a), "0", "4", "EJFÖRV", 100)
                                                      for a in range(16, 30) if a != 17],
                 columns=["age", "study", "level", "employment", "population"]).assign(
        sex="1", year=2024).to_sql("population_study_education", w.conn, index=False,
                                   if_exists="append")
    prima_startpopulationen(w, 0.0, np.random.default_rng(0))
    assert w.individuals.at[0, "status"] == "student"



# ---------------------------------------------------------------------------
# 6c: studerande med extrajobb
# ---------------------------------------------------------------------------

def _studievarld(statusar, aldrar, **extra):
    """Jobben: fyra nära med låga krav, två nära med höga, två långt bort med
    låga. Studenten bor i origo."""
    w = _varld(statusar, aldrar, **extra)
    n = len(w.jobs)
    w.jobs["r_req"] = [0.0] * 4 + [0.9] * 2 + [0.0] * (n - 6)
    w.jobs["x"] = [0.0] * 6 + [50_000.0] * (n - 6)
    w.jobs["y"] = 0.0
    w._ja_n = None
    return w


def test_studenten_soker_bara_extrajobb_nara_med_laga_krav():
    """Kvantilen 0,25 av kraven ger gränsen 0; 20 km utesluter de bortre."""
    w = _studievarld(["student"], [17.0], studerande=True)
    tillat = np.flatnonzero(w.studentjobb(0))
    assert list(tillat) == [0, 1, 2, 3]


def test_studentens_anspråk_ar_lagt_och_hon_soker():
    from core.intrade import tilldela_plan
    w = _varld(["not_in_labor_force"], [16.0], w_res=5.0)
    tilldela_plan(w, 0, 0.0, np.random.default_rng(1))
    from core.matching_core import relevansfordelning
    med, sd, _ = relevansfordelning(w, 0)
    assert w.individuals.at[0, "studerande"] and w.individuals.at[0, "w_res"] < med
    assert any(e["event_type"] == "start_job_search" for e in w._pushed)


def test_studenten_soker_med_egen_takt():
    w = _varld(["student", "unemployed"], [17.0, 30.0], sim={"studerande_sokfaktor": 6.0})
    np.random.seed(0)
    st = np.mean([w.search_interval(0, 0.0) for _ in range(3000)])
    ar = np.mean([w.search_interval(1, 0.0) for _ in range(3000)])
    assert st / ar == pytest.approx(6.0, rel=0.1)


def test_den_studerande_som_mister_extrajobbet_blir_student_inte_arbetslos():
    """Utan jobb är hon i BAS studerande, utanför arbetskraften."""
    from core.event_handlers import _become_unemployed, handle_destroy_job
    w = _varld(["employed", "employed"], [18.0, 18.0], studerande=True)
    for i in (0, 1):
        jid = w.jobs.at[i, "job_id"]
        w.individuals.at[i, "job_id"] = jid
        w.jobs.at[i, "individual_id"] = w.individuals.at[i, "individual_id"]
        w.set_job_filled(jid, True)
    _become_unemployed(w, 0, 10.0)
    handle_destroy_job({"time": 11.0, "agent_id": None, "event_type": "destroy_job",
                        "params": {"job_id": w.jobs.at[1, "job_id"]}}, w)
    assert list(w.individuals.status) == ["student", "student"]
    assert w.individuals.job_id.isna().all()


def test_utpendlingens_erbjudanden_gar_inte_till_studerande():
    from core.matching_core import externt_erbjudande
    w = _varld(["employed"], [18.0], studerande=True, sim={"utpendling_erbjudande_andel": 1.0})
    assert externt_erbjudande(w, 0, 1.0, np.random.default_rng(0)) is None


def test_intradet_for_den_som_har_extrajobb():
    """Den som går in behåller jobbet som vanlig anställning; den som aldrig
    går in slutar."""
    w = _varld(["employed", "employed"], [19.0, 19.0], studerande=True, plan_level="4",
               plan_field="0", plan_entry_age=19, plan_enters=[True, False])
    for i in (0, 1):
        jid = w.jobs.at[i, "job_id"]
        w.individuals.at[i, "job_id"] = jid
        w.jobs.at[i, "individual_id"] = w.individuals.at[i, "individual_id"]
        w.set_job_filled(jid, True)
    _in(w, 0, 500.0)
    _in(w, 1, 500.0)
    ind = w.individuals
    assert ind.at[0, "status"] == "employed" and not ind.at[0, "studerande"]
    assert pd.notna(ind.at[0, "job_id"]) and ind.at[0, "education_level"] == 4
    assert ind.at[1, "status"] == "not_in_labor_force" and pd.isna(ind.at[1, "job_id"])


def test_startens_anstallda_unga_blir_studerande_med_extrajobb():
    """Vid 17 studerar alla som förvärvsarbetar (raderna byggs här)."""
    from core.intrade import prima_unga
    w = _varld(["employed", "unemployed", "unemployed"], [17.0, 17.0, 25.0])
    jid = w.jobs.at[0, "job_id"]
    w.individuals.at[0, "job_id"] = jid
    w.jobs.at[0, "individual_id"] = w.individuals.at[0, "individual_id"]
    w.set_job_filled(jid, True)
    w.conn.execute("DELETE FROM population_study_education")
    rader = []
    for a in range(16, 30):
        n = 100 + 100 * (a % 2)
        rader += [(str(a), "1" if a < 20 else "0", "4", "FÖRV", n),
                  (str(a), "1" if a < 20 else "0", "4", "EJFÖRV", n)]
    rader += [("30-34", "0", "4", "FÖRV", 200), ("30-34", "0", "4", "EJFÖRV", 200)]
    pd.DataFrame(rader, columns=["age", "study", "level", "employment", "population"]).assign(
        sex="1", year=2024).to_sql("population_study_education", w.conn, index=False,
                                   if_exists="append")
    w.__dict__.pop("_intradesplan", None)
    ut = prima_unga(w, 0.0, np.random.default_rng(0))
    ind = w.individuals
    assert ind.at[0, "status"] == "employed" and ind.at[0, "studerande"]
    assert ind.at[1, "status"] == "student", "den arbetslösa 17-åringen studerar"
    assert ind.at[2, "status"] == "unemployed", "25-åringen är kvar i arbetskraften"
    assert ut["unga_studerande_med_jobb"] == 1 and ut["unga_arbetslosa_till_studier"] == 1



def test_studenten_ansoker_bara_till_extrajobb():
    """De bortre jobben betalar mest; utan masken hade hon sökt dit."""
    from core.matching_core import apply_once
    w = _studievarld(["student"], [17.0], studerande=True, w_res=0.1)
    w.jobs.loc[w.jobs.index[6:], "wage"] = 5.0
    w._ja_n = None
    np.random.seed(0)
    valda = {apply_once(w, 0, 1.0)[0] for _ in range(30)} - {None}
    assert valda and valda <= set(w.jobs.job_id[:4])


def test_studenten_ar_behorig_i_urvalet():
    from core.event_handlers import handle_close_vacancy
    w = _varld(["student"], [17.0], studerande=True, w_res=0.1,
               sim={"application_window_days": 20})
    jid = w.jobs.at[0, "job_id"]
    w.file_application(jid, 0, 0.0, q=0.9, w_neg=0.8, surplus=0.1, commute_km=1.0)
    handle_close_vacancy({"time": 20.0, "agent_id": 0, "event_type": "close_vacancy",
                          "params": {"job_id": jid}}, w)
    assert [e["agent_id"] for e in w._pushed if e["event_type"] == "start_job"] == [0]


def test_manadsraden_bar_studerande_med_och_utan_jobb():
    """Utan fälten syntes studenterna inte i tidsserien: en körning med 788
    studerande vid start visade noll hela vägen."""
    from core.event_handlers import handle_new_month
    w = _varld(["student", "student", "employed", "employed"], [17.0, 17.0, 18.0, 40.0],
               studerande=[True, True, True, False])
    handle_new_month({"time": 0.0, "agent_id": None, "event_type": "new_month",
                      "params": {"year": 2024, "month": 1}}, w)
    rad = [x for typ, x in w.event_logger.events if typ == "new_month"][-1]
    assert (rad["students"], rad["students_employed"]) == (2, 1)
