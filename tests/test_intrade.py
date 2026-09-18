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


def _varld(statusar, aldrar, q=1.0, **extra):
    w = make_world(n_employers=10, size=1, simulation={"intrade_ansprak_percentil": 0.5})
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
