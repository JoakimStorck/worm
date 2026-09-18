"""Arbetslösheten med SCB:s definition (BAS), docs/stockarna.md
"Arbetslöshetsmåttet".

Jämförelsetalet i labour_market_status är BAS: sysselsatt är den som haft
betalt arbete någon gång under referensmånaden (november), arbetslös den som
inte haft det och är inskriven på Arbetsförmedlingen, 20-65 år. Modellens
unemployed_individuals är en ögonblicksbild där varje kort glapp och varje
väntan på tillträde räknas; mot BAS låg den 0,8-0,9 procentenheter för högt."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import make_world  # noqa: E402

from core.statistics.basic_stats import arbetsloshet_bas  # noqa: E402

T0, T1 = 100.0, 130.4


def _varld(rader):
    w = make_world(n_employers=2, size=1)
    w.individuals = pd.DataFrame(rader, columns=["status", "age", "unemployed_since", "extern"])
    return w


def test_arbetslos_hela_manaden_och_i_aldern():
    rader = [
        ("employed", 40.0, np.nan, False),
        ("unemployed", 40.0, T0 - 50, False),    # hela månaden: räknas
        ("unemployed", 40.0, T0, False),         # från månadens början: räknas
        ("unemployed", 40.0, T0 + 10, False),    # arbetade i månaden: sysselsatt
        ("unemployed", 19.0, T0 - 50, False),    # för ung
        ("unemployed", 65.0, T0 - 50, False),    # 65 år ingår
        ("unemployed", 66.0, T0 - 50, False),    # för gammal
        ("employed", 66.0, np.nan, False),
        ("unemployed", 40.0, T0 - 50, True),     # inpendlare: inte invånare
        ("not_in_labor_force", 40.0, np.nan, False),
    ]
    r = arbetsloshet_bas(_varld(rader), T0, T1)
    assert r == {"unemployed_bas": 3, "labour_force_bas": 5}


def test_arbetslos_utan_borjan_ar_ett_fel():
    """Hon hade tyst räknats åt ena eller andra hållet."""
    rader = [("unemployed", 40.0, np.nan, False), ("employed", 40.0, np.nan, False)]
    with pytest.raises(ValueError, match="unemployed_since"):
        arbetsloshet_bas(_varld(rader), T0, T1)


def test_manadsraden_matter_mot_forra_manadsskiftet():
    """Referensmånaden är tiden sedan förra månadsskiftet. Den som blev
    arbetslös dag 20 räknas inte vid skiftet dag 30,4 men vid nästa."""
    from core.event_handlers import handle_new_month
    w = make_world(n_employers=2, size=1)
    w.individuals = pd.DataFrame({
        "individual_id": ["a", "b"], "status": ["unemployed", "employed"],
        "age": [40.0, 40.0], "unemployed_since": [20.0, np.nan], "extern": [False, False],
        "job_id": [None, None], "municipal_code": "2062"})
    w.prepare()
    rader = []
    for t, m in ((0.0, 1), (30.4, 2), (60.9, 3)):
        handle_new_month({"time": t, "agent_id": None, "event_type": "new_month",
                          "params": {"year": 2024, "month": m}}, w)
        rader.append([x for typ, x in w.event_logger.events if typ == "new_month"][-1])
    assert "unemployed_bas" not in rader[0], "första månadsskiftet har ingen referensmånad"
    assert rader[1]["unemployed_bas"] == 0
    assert rader[2]["unemployed_bas"] == 1


def test_analysens_tabell_per_kommun_anvander_samma_definition(tmp_path):
    """Rapporten ställer kommunernas tal mot SCB; där gällde ögonblicksbilden
    och alla åldrar. Slutet är år 1, alltså dag 365,25; sista månaden börjar
    dag 334,8."""
    from scripts.analysis import arbetsloshet_per_kommun
    d = tmp_path / "run"
    d.mkdir()
    (d / "run_meta.json").write_text('{"n_years": 1}')
    pd.DataFrame([
        ("2062", "employed", 40.0, np.nan, False),
        ("2062", "employed", 40.0, np.nan, False),
        ("2062", "unemployed", 40.0, 100.0, False),   # hela månaden
        ("2062", "unemployed", 40.0, 350.0, False),   # arbetade i månaden
        ("2062", "unemployed", 70.0, 100.0, False),   # utanför åldern
        ("2031", "employed", 40.0, np.nan, True),     # inpendlare
    ], columns=["municipal_code", "status", "age", "unemployed_since", "extern"]).to_csv(
        d / "final_state_individuals.csv", index=False)
    t = arbetsloshet_per_kommun(str(d))
    assert list(t.index) == ["2062"]
    assert t.loc["2062", "u_rate"] == pytest.approx(100 * 1 / 4)


def test_sammanfattningen_bar_de_utlovades_andel(tmp_path):
    """C4c: körningens andel utlovade positioner, medel över sista året, ställs
    mot parametern utlovad_andel. Andelen är v - v_open."""
    from core.analysis.eventlog import summary_row
    ts = pd.DataFrame({"time": np.arange(24) * 30.4, "year": np.arange(24) * 30.4 / 365.25,
                       "employed": 900.0, "unemployed": 100.0, "vacancies": 30.0,
                       "active_jobs": 1000.0, "labour_force": 1000.0, "u": 10.0,
                       "v": [5.0] * 12 + [3.0] * 12, "v_open": [4.0] * 12 + [1.0] * 12,
                       "tightness": 0.3, "identity_residual": 0.0, "u_bas": 8.0})
    row = summary_row(str(tmp_path), events=[], tr=pd.DataFrame(), ts=ts)
    assert row["pending_pct"] == pytest.approx(2.0)
