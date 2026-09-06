"""Jobbflöden: förstörelse, återfyllnad, och de två buggar som fanns."""
import numpy as np
import pandas as pd
import pytest

from conftest import make_world, run_months, FakeConfig


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


def _world_with_string_ids(n=3):
    """Som den riktiga byggaren: individual_id är en sträng, indexet ett heltal."""
    w = make_world(n_employers=n, size=1)
    w.individuals = pd.DataFrame({
        "individual_id": [f"2062_i{i:06d}" for i in range(n)],
        "status": "employed",
        "job_id": w.jobs["job_id"].tolist(),
        "w_res": 1.0, "chi": 0.4, "xi": 0.3, "r_i": 0.0,
        "x_occ": 0.3, "y_occ": 0.1,
    })
    w.jobs["individual_id"] = w.individuals["individual_id"].tolist()
    return w


def test_destroy_job_does_not_create_phantom_individuals():
    """REGRESSION: jobs['individual_id'] innehåller strängen ur kolumnen, inte
    radindexet. .at[] på ett okänt värde SKAPAR en ny rad i pandas i stället
    för att höja fel, så populationen växte med hundratals NaN-individer per
    simulerat år och sluttillståndets histogram kraschade."""
    from core.event_handlers import handle_destroy_job
    w = _world_with_string_ids(3)
    n_before = len(w.individuals)
    for job_id in w.jobs["job_id"]:
        handle_destroy_job({"time": 10.0, "agent_id": None, "event_type": "destroy_job",
                            "params": {"job_id": job_id}}, w)
    assert len(w.individuals) == n_before, "spökrader skapades"
    assert w.individuals["chi"].notna().all(), "NaN i chi"
    assert (w.individuals["status"] == "unemployed").all(), "innehavare inte förskjutna"


def test_population_is_invariant_over_a_year():
    """Summan sysselsatta + arbetslösa + utanför arbetskraften ska vara konstant."""
    from core.event_handlers import handle_destroy_job
    w = _world_with_string_ids(40)
    w._schedule_destruction(w.jobs["job_id"].tolist(), 0.0)
    n = len(w.individuals)
    for m in range(1, 13):
        t = m * 30.44
        while not w.event_queue.is_empty() and w.event_queue.peek()["time"] <= t:
            ev = w.event_queue.pop()
            if ev["event_type"] == "destroy_job":
                handle_destroy_job(ev, w)
        w.post_vacancies_batch(t)
    assert len(w.individuals) == n


def test_job_ids_unique_across_municipalities():
    """REGRESSION: generate_jobs_from_employers anropas en gång per kommun och
    nollställde sin lokala räknare, så sex kommuner fick sex jobb med id
    J00000. update_after_matching föll då med InvalidIndexError."""
    import geopandas as gpd
    from shapely.geometry import Point
    import core.scenariobuilder as sbmod
    from core.scenariobuilder import ScenarioBuilder

    sb = ScenarioBuilder.__new__(ScenarioBuilder)
    sb.conn = None
    sb.cfg_reader = FakeConfig({})
    sb.onet_space_df = pd.DataFrame(
        {"chi": [0.3], "xi": [0.3], "x_occ": [0.29], "y_occ": [0.09],
         "r_o": [0.27], "geom_source": ["occupation"], "w_rel": [1.0],
         "pi_rel": [1.0]}, index=pd.Index(["11-1011.00"], name="onet_code"))
    sb.get_onet_codes_with_freq_for_sni = lambda sni: [("11-1011.00", 1.0)]

    orig = sbmod.assign_deso_code
    sbmod.assign_deso_code = lambda df, zones, x_col, y_col: "Z"

    class _GW:
        deso_zones = None
    sb.geoworld = _GW()

    ids = []
    try:
        for kommun in ("2080", "2081", "2026"):
            emp = gpd.GeoDataFrame({
                "employer_id": [f"{kommun}_e0", f"{kommun}_e1"],
                "municipal_code": kommun, "size": [3, 2], "sni_code": "A",
                "layer": "deso", "zone_code": f"{kommun}A",
                "geometry": [Point(0, 0), Point(1, 1)],
            })
            jobs, _ = sb.generate_jobs_from_employers(emp)
            ids.extend(jobs["job_id"].tolist())
    finally:
        sbmod.assign_deso_code = orig

    assert len(ids) == len(set(ids)), f"dubbletter: {len(ids) - len(set(ids))}"


def test_vacancy_mask_stays_in_sync():
    """Vakansmasken cachas och uppdateras punktvis i stället för att räknas om
    ur individual_id, eftersom isna på en strängkolumn kostade 392
    mikrosekunder per sökning (6.7 av 33 sekunder i en Mora-körning). Den får
    då inte glida ur synk med tabellen."""
    from core.event_handlers import handle_destroy_job

    def truth(w):
        filled = w.jobs["individual_id"].notna().to_numpy()
        return (~filled) & w.jobs["active"].to_numpy(dtype=bool)

    w = make_world(n_employers=20, size=5)
    w.individuals = pd.DataFrame({"individual_id": [], "status": [], "job_id": [], "w_res": []})
    assert np.array_equal(w.vacant_mask(), truth(w))

    w._schedule_destruction(w.jobs["job_id"].tolist(), 0.0)
    for m in range(1, 13):
        t = m * 30.44
        while not w.event_queue.is_empty() and w.event_queue.peek()["time"] <= t:
            ev = w.event_queue.pop()
            if ev["event_type"] == "destroy_job":
                handle_destroy_job(ev, w)
        w.post_vacancies_batch(t)
        assert np.array_equal(w.vacant_mask(), truth(w)), f"ur synk vid månad {m}"


def test_job_index_maps_ids_to_positions():
    w = make_world(n_employers=5, size=3)
    ji = w.job_index()
    for pos, jid in enumerate(w.jobs["job_id"]):
        assert ji[jid] == pos


def test_individual_id_column_is_object_dtype():
    """REGRESSION: är jobs['individual_id'] float64 (enbart NaN) höjer
    pandas 2.x TypeError när ett sträng-id skrivs in vid anställning."""
    w = make_world(n_employers=3, size=2)
    assert w.jobs["individual_id"].dtype == object
    w.jobs.loc[w.jobs.index[0], "individual_id"] = "2062_i000001"
    assert w.jobs.at[0, "individual_id"] == "2062_i000001"


def test_start_job_fills_the_right_position():
    """REGRESSION: raden som ANVÄNDE pos pushades utan raden som definierar
    den, så simuleringen föll med NameError vid första anställningen."""
    from core.event_handlers import handle_start_job

    w = make_world(n_employers=4, size=3)
    w.individuals = pd.DataFrame([{
        "individual_id": "i0", "status": "unemployed", "job_id": None,
        "w_res": 0.5, "chi": 0.3, "xi": 0.3, "r_i": 0.0,
        "x_occ": 0.3, "y_occ": 0.1}]).astype({"job_id": object})
    target = w.jobs.at[7, "job_id"]
    before = int(w.vacant_mask().sum())
    try:
        handle_start_job({"time": 1.0, "agent_id": 0, "event_type": "start_job",
                          "params": {"job_id": target}}, w)
    except KeyError:
        pass          # senare steg kräver full scenariokonfiguration
    assert w.jobs.at[7, "individual_id"] == "i0"
    assert int(w.vacant_mask().sum()) == before - 1
    filled = w.jobs["individual_id"].notna().to_numpy()
    assert np.array_equal(w.vacant_mask(),
                          (~filled) & w.jobs["active"].to_numpy(dtype=bool))
