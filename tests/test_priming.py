"""Primingen av startpopulationen, steg 6a-i (core/priming.py)."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import make_world
from core.occupations.competence import Circles, EMPTY


def test_en_borttagen_cirkel_lamnar_en_lucka_som_inte_ateranvands():
    """En högre plats ska fortfarande vara en senare händelse (latest)."""
    c = Circles(1, 4)
    a = c.add(0, "A", 0, 0, 0.1, 1.0)
    b = c.add(0, "B", 0, 0, 0.1, 1.0)
    c.remove(0, a)
    ny = c.add(0, "A", 0, 0, 0.1, 1.0)
    assert ny > b and c.latest(0, "A") == ny
    assert c.counts()[0] == 2 and c.key[0, a] == EMPTY and c.mass[0, a] == 0.0


def _varld(statusar, tenure, **sim):
    w = make_world(n_employers=4, size=2, simulation=sim)
    w.jobs.loc[w.jobs.index[0], ["onet_code", "x_occ", "y_occ", "r_o"]] = ["JOBB", -0.5, 0.2, 0.3]
    n = len(statusar)
    w.individuals = pd.DataFrame({
        "individual_id": [f"i{k}" for k in range(n)], "status": ["unemployed"] * n,
        "job_id": pd.Series([None] * n, dtype="object"), "w_res": 0.5, "chi": 0.3,
        "xi": 0.3, "r_i": 0.0, "x_occ": 0.3, "y_occ": 0.1, "x": 0.0, "y": 0.0,
        "onet_code": "START", "last_onet_code": "START", "r_o_home": 0.27,
        "tenure_years": tenure, "education_level": 3, "municipal_code": "2062",
        "unemployed_since": 0.0, "w_last": 0.5,
        "propensity_start_education": 0.0, "propensity_internal_training": 0.0,
        "propensity_quit_job": 0.0, "propensity_career_break": 0.0,
        "propensity_internal_job_change": 0.0})
    w.prepare()
    for i, st in enumerate(statusar):
        if st == "employed":
            from core.event_handlers import handle_start_job
            try:
                handle_start_job({"time": 0.0, "agent_id": i, "event_type": "start_job",
                                  "params": {"job_id": w.jobs.at[0, "job_id"],
                                             "bootstrap": True}}, w)
            except KeyError:
                pass
    return w


def test_den_anstallda_far_erfarenheten_dar_hon_arbetar():
    from core.priming import prima_startpopulationen
    w = _varld(["employed"], [8.0])
    c, p = w.circles, w.competence_params()
    j = int(w._active_slot[0])
    assert c.key_names[c.key[0, j]] == "JOBB" and c.mass[0, j] == 0.0
    prima_startpopulationen(w, 0.0, np.random.default_rng(0))
    assert c.mass[0, j] == pytest.approx(p.a / p.lam * (1 - np.exp(-p.lam * 8.0)))
    assert c.rho2[0, j] == pytest.approx(c.rho2_home[0, j])
    namn = {c.key_names[k] for k in c.key[0] if k != EMPTY}
    assert "START" not in namn, "startyrkets cirkel ligger kvar"
    assert "EDU:0" in namn and "EDU:3" in namn, "utbildningen ska ligga kvar"
    assert int(w._active_slot[0]) == j


def test_den_arbetslosa_har_sitt_senaste_yrke_suddat_och_klockan_bakat():
    from core.priming import prima_startpopulationen
    w = _varld(["unemployed"] * 400, [8.0] * 400, start_arbetsloshet_medel_dagar=115.0)
    c, p = w.circles, w.competence_params()
    j = c.latest(0, "START")
    m0, r0 = c.mass[0, j], c.rho2[0, j]
    prima_startpopulationen(w, 0.0, np.random.default_rng(1))
    d = -w.individuals["unemployed_since"].to_numpy()
    assert (d > 0).all() and d.mean() == pytest.approx(115.0, rel=0.15)
    ar = d[0] / 365.25
    assert c.mass[0, j] == pytest.approx(m0 * np.exp(-p.lam * ar))
    assert c.rho2[0, j] == pytest.approx(min(r0 + 2 * p.D * ar, p.diffusion_max_ratio * c.rho2_home[0, j]))
    assert c.latest(0, "START") == j, "det senaste yrket ska ligga kvar"
    assert (w._active_slot == EMPTY).all()


def test_uppstarten_primar():
    """bootstrap_matching anropar primingen: efter uppstarten har de anställda
    massa i jobbets cirkel och ingen startyrkescirkel."""
    from core.matching_core import bootstrap_matching
    w = _varld(["unemployed"] * 6, [5.0] * 6, application_window_days=40)
    w.jobs["r_req"] = 0.0
    st = bootstrap_matching(w, 0.0, log=None)
    anst = np.flatnonzero(w.individuals["status"].to_numpy() == "employed")
    assert len(anst) > 0 and st["priming_flyttade"] == len(anst)
    c = w.circles
    for i in anst:
        j = int(w._active_slot[i])
        assert c.mass[i, j] > 0
        assert "START" not in {c.key_names[k] for k in c.key[i] if k != EMPTY} \
            or w.jobs.set_index("job_id").at[w.individuals.at[i, "job_id"], "onet_code"] == "START"


def _uppstartsvarld(n=10):
    """Tio arbetslösa i samma startyrke, med stigande tjänstetid och därmed
    stigande konkurrenskraft i yrket: 0 och 1 är den svagaste femtedelen, 8
    och 9 den starkaste."""
    w = _varld(["unemployed"] * n, list(np.linspace(0.05, 6.0, n)),
               application_window_days=40)
    return w


def test_uppstarten_soker_i_ordningen_svag_stark_mitten(monkeypatch):
    import core.matching_core as mc
    w = _uppstartsvarld()
    omg = {"n": 0}
    sokte = []
    monkeypatch.setattr(mc, "apply_once", lambda world, i, t: sokte.append((omg["n"], i)))
    monkeypatch.setattr(mc, "externt_erbjudande", lambda *a, **k: None)

    def stang(world, t, immediate=False):
        omg["n"] += 1
        return 0
    monkeypatch.setattr(mc, "close_all_windows", stang)
    mc.bootstrap_matching(w, 0.0, log=None)
    per = {}
    for r, i in sokte:
        per.setdefault(r, set()).add(i)
    assert per[0] == per[2] == {0, 1}, "den svagaste femtedelen ska söka ensam först"
    assert per[3] == {0, 1, 8, 9}, "sedan den starkaste"
    assert per[6] == set(range(10)), "sist mitten"


def test_uppstarten_ger_hogst_tre_erbjudanden_utifran_per_person(monkeypatch):
    import core.matching_core as mc
    w = _uppstartsvarld()
    erbj = {}

    def rakna(world, i, t, rng):
        erbj[i] = erbj.get(i, 0) + 1
        return None
    monkeypatch.setattr(mc, "externt_erbjudande", rakna)
    monkeypatch.setattr(mc, "apply_once", lambda world, i, t: None)
    monkeypatch.setattr(mc, "close_all_windows", lambda world, t, immediate=False: 0)
    mc.bootstrap_matching(w, 0.0, log=None)
    assert erbj and max(erbj.values()) == 3
