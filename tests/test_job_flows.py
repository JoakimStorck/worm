"""Jobbflöden: förstörelse, återfyllnad, och de två buggar som fanns."""
import numpy as np
import pandas as pd
import pytest

from conftest import make_world, run_months


def theoretical_stock(target, delta, fill):
    """Jämvikt vid partiell anpassning: fill*(T-J) = (delta/12)*J."""
    return target / (1.0 + (delta / 12.0) / fill)


def test_disabled_flows_keep_stock_constant():
    w = make_world(simulation={"job_flows": False})
    n0 = int(w.jobs["active"].sum())
    w._schedule_destruction(w.jobs["job_id"].tolist(), 0.0)
    assert len(w.event_queue) == 0          # inga förstörelsehändelser
    assert run_months(w, 12)[-1] == n0


def test_destruction_schedules_events():
    w = make_world()
    w._schedule_destruction(w.jobs["job_id"].tolist(), 0.0)
    assert len(w.event_queue) > 0


def test_stock_converges_near_theory():
    w = make_world(n_employers=40, size=25)          # 1000 jobb
    w._schedule_destruction(w.jobs["job_id"].tolist(), 0.0)
    stock = run_months(w, 48)
    expected = theoretical_stock(1000, 0.20, 0.25)
    assert np.mean(stock[-12:]) == pytest.approx(expected, rel=0.06)


@pytest.mark.parametrize("size,n_emp", [(1, 1000), (3, 334), (25, 40)])
def test_stock_independent_of_employer_size(size, n_emp):
    """REGRESSION. Två fel gjorde detta storleksberoende:
    floor() nollade underskott under 1/fill_rate, och mallen för nya jobb
    byggdes ur aktiva jobb så en arbetsgivare utan aktiva jobb dog permanent.
    Med enmansföretag kollapsade stocken till under halva målet."""
    target = size * n_emp
    w = make_world(n_employers=n_emp, size=size)
    w._schedule_destruction(w.jobs["job_id"].tolist(), 0.0)
    stock = run_months(w, 48)
    expected = theoretical_stock(target, 0.20, 0.25)
    assert np.mean(stock[-12:]) == pytest.approx(expected, rel=0.10)


def test_employer_with_no_active_jobs_can_repost():
    """REGRESSION: mallen byggdes ur aktiva jobb."""
    w = make_world(n_employers=1, size=4, simulation={"vacancy_fill_rate": 1.0})
    w.jobs["active"] = False                      # allt förstört
    w.jobs["individual_id"] = np.nan
    assert w.post_vacancies_batch(30.0) == 4


def test_small_deficits_are_not_rounded_away():
    """REGRESSION: floor(0.25*3)=0 gav noll nya jobb varje månad."""
    w = make_world(n_employers=200, size=4)
    w.jobs.loc[w.jobs.index[::4], "active"] = False    # underskott 1 hos alla 200
    # floor(1 * 0.25) = 0 -> gamla koden postade aldrig något
    posted = sum(w.post_vacancies_batch(30.0 * m) for m in range(1, 7))
    assert posted > 100


def test_destroyed_job_displaces_holder():
    from core.event_handlers import handle_destroy_job
    w = make_world(n_employers=1, size=1)
    w.individuals = pd.DataFrame([{"individual_id": 0, "status": "employed",
                                   "job_id": w.jobs.at[0, "job_id"], "w_res": 1.0}])
    w.jobs.at[0, "individual_id"] = 0
    handle_destroy_job({"time": 10.0, "agent_id": None, "event_type": "destroy_job",
                        "params": {"job_id": w.jobs.at[0, "job_id"]}}, w)
    assert not bool(w.jobs.at[0, "active"])
    assert w.individuals.at[0, "status"] == "unemployed"
    assert w.individuals.at[0, "w_res"] == pytest.approx(0.7)     # rho * senaste lön
    assert len(w.event_queue) == 1                                # ny jobbsökning


def test_destroying_twice_is_harmless():
    from core.event_handlers import handle_destroy_job
    w = make_world(n_employers=1, size=1)
    ev = {"time": 10.0, "agent_id": None, "event_type": "destroy_job",
          "params": {"job_id": w.jobs.at[0, "job_id"]}}
    handle_destroy_job(ev, w)
    handle_destroy_job(ev, w)                    # ska inte krascha
    assert int(w.jobs["active"].sum()) == 0


def test_growth_raises_target():
    w = make_world(n_employers=20, size=10, simulation={"employer_growth_rate": 0.12,
                                                        "job_destruction_rate": 0.0})
    t0 = w.employers["target_size"].sum()
    for m in range(1, 13):
        w.post_vacancies_batch(m * 30.44)
    assert w.employers["target_size"].sum() > t0


def test_only_active_jobs_are_counted():
    from core.statistics.basic_stats import analyze_world
    w = make_world(n_employers=10, size=10)
    w.individuals = pd.DataFrame({"individual_id": [], "status": [], "job_id": []})
    w.jobs.loc[w.jobs.index[:30], "active"] = False
    stats = analyze_world(w)
    assert stats["total_jobs"] == 70
    assert stats["unmatched_jobs"] == 70


def test_system_handlers_run(monkeypatch):
    """REGRESSION: handle_new_year refererade n_jobs/n_posted som bara fanns i
    handle_new_month, vilket kraschade vid första årsskiftet."""
    from core.event_handlers import handle_new_month, handle_new_year
    w = make_world(n_employers=5, size=4)
    w.individuals = pd.DataFrame({"individual_id": [], "status": [], "job_id": []})
    for handler, params in ((handle_new_month, {"month": 1, "year": 2024}),
                            (handle_new_year, {"year": 2024})):
        handler({"time": 30.0, "agent_id": None,
                 "event_type": handler.__name__.replace("handle_", ""),
                 "params": params}, w)
    logged = dict(w.event_logger.events[-1][1])
    assert "active_jobs" in logged
