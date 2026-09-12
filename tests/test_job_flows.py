"""Jobbflöden: förstörelse, återfyllnad, och de två buggar som fanns."""
import os
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
    floor() nollade underskott under 1/fill_rate, och mallen för new_events jobb
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
    """REGRESSION: floor(0.25*3)=0 gav noll new_events jobb varje månad."""
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


def test_pending_job_is_reserved_but_still_a_vacancy():
    """Rekryteringstid: en matchad position är utlovad men inte tillträdd.

    Den får inte sökas av någon annan, men den ska räknas som en öppen vakans
    i statistiken -- det är så vakansstatistik definieras, och det är det som
    ger realistisk vakansvaraktighet. Utan fördröjning fylls en vakans i samma
    ögonblick den matchas, vilket gav omkring 13 dagars varaktighet mot
    faktiska 30-60 och en vakansgrad under 1.3 procent.
    """
    from core.statistics.basic_stats import analyze_world

    w = make_world(n_employers=4, size=3)
    w.individuals = pd.DataFrame({"individual_id": [], "status": [], "job_id": []})
    jid = w.jobs.at[5, "job_id"]
    n_vac_before = int(w.vacant_mask().sum())

    w.set_job_pending(jid)

    assert int(w.vacant_mask().sum()) == n_vac_before - 1, "utlovad position kan sökas"
    assert bool(w.jobs.at[5, "pending"])
    assert pd.isna(w.jobs.at[5, "individual_id"]), "positionen är inte tillträdd"
    # räknas fortfarande som öppen vakans i statistiken
    assert analyze_world(w)["unmatched_jobs"] == n_vac_before


def test_pending_clears_when_job_is_filled_or_freed():
    w = make_world(n_employers=2, size=2)
    jid = w.jobs.at[0, "job_id"]
    w.set_job_pending(jid)
    assert bool(w.jobs.at[0, "pending"])
    w.set_job_filled(jid, False, 10.0)    # rekryteringen avbryts
    assert not bool(w.jobs.at[0, "pending"])
    assert bool(w.vacant_mask()[0]), "positionen ska vara sökbar igen"


def test_posted_jobs_are_searchable():
    """REGRESSION: mallen för new_events jobb kopierar ALLA kolumner. Utan att
    pending nollställs föds ett nyskapat jobb osökbart -- det räknas som
    vakans men kan aldrig tillsättas. Över fem år gav det 3 688 döda vakanser
    i Mora medan sysselsättningen föll från 9 900 till 6 505."""
    w = make_world(n_employers=6, size=4)
    w.individuals = pd.DataFrame({"individual_id": [], "status": [], "job_id": []})

    # Gör mallpositionerna utlovade, så att en naiv kopia ärver flaggan
    for jid in w.jobs["job_id"]:
        w.set_job_pending(jid)
    w.jobs.loc[:, "active"] = True
    w.jobs.loc[:, "individual_id"] = np.nan
    w.employers["target_size"] = 8.0

    n_before = len(w.jobs)
    posted = w.post_vacancies_batch(30.0)
    assert posted > 0
    new = w.jobs.iloc[n_before:]
    assert not new["pending"].any(), "nyskapade positioner ärvde pending"
    # och de syns i vakansmasken efter ombyggnad
    assert w.vacant_mask()[n_before:].all(), "nyskapade positioner är osökbara"


def test_market_does_not_leak_positions_over_time():
    """Invariant över en längre körning: varje aktiv position är antingen
    tillsatt, utlovad eller sökbar. Läcker någon kategori kollapsar marknaden
    långsamt utan att något enskilt steg ser fel ut."""
    from core.event_handlers import handle_destroy_job

    w = make_world(n_employers=30, size=6, simulation={"job_destruction_rate": 0.15})
    w.individuals = pd.DataFrame({"individual_id": [], "status": [], "job_id": []})
    w._schedule_destruction(w.jobs["job_id"].tolist(), 0.0)

    for m in range(1, 61):
        t = m * 30.44
        while not w.event_queue.is_empty() and w.event_queue.peek()["time"] <= t:
            ev = w.event_queue.pop()
            if ev["event_type"] == "destroy_job":
                handle_destroy_job(ev, w)
        w.post_vacancies_batch(t)

        act = w.jobs["active"].to_numpy(dtype=bool)
        filled = w.jobs["individual_id"].notna().to_numpy()
        pend = w.jobs["pending"].to_numpy(dtype=bool)
        searchable = w.vacant_mask()
        # Varje aktiv position hör till exakt en kategori
        assert np.array_equal(act, filled | pend | searchable) or \
               np.all(act <= (filled | pend | searchable)), f"position utan kategori, månad {m}"
        assert searchable.sum() > 0, f"inga sökbara positioner kvar, månad {m}"


def _worker(iid="i0"):
    return pd.DataFrame([{
        "individual_id": iid, "status": "unemployed", "job_id": None,
        "w_res": 0.5, "chi": 0.3, "xi": 0.3, "r_i": 0.0,
        "x_occ": 0.3, "y_occ": 0.1, "x": 0.0, "y": 0.0,
        "municipal_code": "2062", "propensity_internal_training": 0.0,
        "propensity_quit_job": 0.0, "propensity_start_education": 0.0,
        "propensity_internal_job_change": 0.0,
        "x": 0.0, "y": 0.0, "municipal_code": "2062",
    }]).astype({"job_id": object})


def test_worker_released_when_promised_job_disappears():
    """REGRESSION: en UTLOVAD position har individual_id NaN, så
    handle_destroy_job hittade ingen innehavare att meddela. Arbetaren
    tillträdde trettio dagar senare ett jobb som inte längre fanns och blev
    bokförd som sysselsatt utan aktiv position. Det gav en residual i
    identiteten U = L - J + V på ett par hundra individer per femårskörning."""
    from core.event_handlers import handle_destroy_job, handle_start_job

    w = make_world(n_employers=3, size=2)
    w.individuals = _worker()
    jid = w.jobs.at[2, "job_id"]
    w.set_job_pending(jid)

    handle_destroy_job({"time": 10.0, "agent_id": None, "event_type": "destroy_job",
                        "params": {"job_id": jid}}, w)
    handle_start_job({"time": 40.0, "agent_id": 0, "event_type": "start_job",
                      "params": {"job_id": jid}}, w)

    assert w.individuals.at[0, "status"] == "unemployed"
    assert pd.isna(w.individuals.at[0, "job_id"])
    assert len(w.event_queue) > 0, "ingen ny sökning schemalagd"
    assert not bool(w.jobs.at[2, "pending"])


def test_worker_released_when_job_taken_by_someone_else():
    """Samma kontroll fångar också att positionen hunnit tillsättas av annan."""
    from core.event_handlers import handle_start_job

    w = make_world(n_employers=3, size=2)
    w.individuals = _worker()
    jid = w.jobs.at[1, "job_id"]
    w.jobs.loc[w.jobs.index[1], "individual_id"] = "nagon_annan"

    handle_start_job({"time": 40.0, "agent_id": 0, "event_type": "start_job",
                      "params": {"job_id": jid}}, w)
    assert w.individuals.at[0, "status"] == "unemployed"
    assert w.jobs.at[1, "individual_id"] == "nagon_annan"


def test_accounting_identity_holds():
    """Bokföringen ska gå ihop exakt: antalet sysselsatta måste vara lika med
    antalet tillsatta aktiva positioner. En modell vars aggregat inte stämmer
    går inte att dra slutsatser ur."""
    from core.event_handlers import handle_destroy_job, handle_start_job

    w = make_world(n_employers=10, size=4)
    w.individuals = pd.concat([_worker(f"i{i}") for i in range(20)], ignore_index=True)
    w._schedule_destruction(w.jobs["job_id"].tolist(), 0.0)

    rng = np.random.default_rng(0)
    for m in range(1, 37):
        t = m * 30.44
        while not w.event_queue.is_empty() and w.event_queue.peek()["time"] <= t:
            ev = w.event_queue.pop()
            if ev["event_type"] == "destroy_job":
                handle_destroy_job(ev, w)
            elif ev["event_type"] == "start_job":
                handle_start_job(ev, w)
        # lova ut och tillträd några positioner
        free = np.flatnonzero(w.vacant_mask())
        for pos in rng.choice(free, size=min(3, free.size), replace=False):
            jid = w.jobs.at[pos, "job_id"]
            w.set_job_pending(jid)
            w._push_event({"time": t + 20.0, "agent_id": int(rng.integers(0, 20)),
                           "event_type": "start_job", "params": {"job_id": jid}})
        w.post_vacancies_batch(t)

        emp = int((w.individuals["status"] == "employed").sum())
        filled_active = int((w.jobs["individual_id"].notna()
                             & w.jobs["active"].astype(bool)).sum())
        assert emp == filled_active, (
            f"månad {m}: {emp} sysselsatta men {filled_active} tillsatta aktiva positioner")


def test_leaving_employment_always_frees_the_position():
    """REGRESSION: start_education satte status till in_education men lät
    positionen stå kvar som tillsatt med arbetarens id. Den var då låst för
    andra sökande och räknades som tillsatt utan sysselsatt innehavare, vilket
    bröt identiteten U = L - J + V. career_break frigjorde redan korrekt.

    Invarianten: ingen individ som lämnat sysselsättning får ha job_id kvar,
    och ingen aktiv position får bära id:t på någon som inte är sysselsatt.
    """
    from core.event_handlers import handle_start_education, handle_career_break

    for handler, params, vantad in (
            (handle_start_education, {"education_type": "specialist",
                                      "duration": 365.25}, "in_education"),
            (handle_career_break, {"duration": 180.0}, "career_break")):
        w = make_world(n_employers=3, size=2)
        w.individuals = _worker()
        jid = w.jobs.at[1, "job_id"]
        w.individuals.at[0, "status"] = "employed"
        w.individuals.at[0, "job_id"] = jid
        w.jobs.loc[w.jobs.index[1], "individual_id"] = "i0"
        w.set_job_filled(jid, True)

        handler({"time": 10.0, "agent_id": 0, "event_type": "x", "params": params}, w)

        assert w.individuals.at[0, "status"] == vantad
        assert pd.isna(w.individuals.at[0, "job_id"]), f"{vantad}: job_id kvar"
        assert pd.isna(w.jobs.at[1, "individual_id"]), f"{vantad}: positionen låst"
        assert bool(w.vacant_mask()[1]), f"{vantad}: positionen inte sökbar igen"

        emp = int((w.individuals["status"] == "employed").sum())
        filled_active = int((w.jobs["individual_id"].notna()
                             & w.jobs["active"].astype(bool)).sum())
        assert emp == filled_active


def test_lost_promise_does_not_orphan_current_job():
    """REGRESSION: föll den utlovade positionen bort sattes arbetaren
    ovillkorligen till arbetslös med job_id nollat. Höll hon redan en position
    blev den kvar tillsatt med hennes id men utan sysselsatt innehavare --
    28 sådana fall i en femårskörning, kategori E i check_invariants."""
    from core.event_handlers import handle_start_job

    w = make_world(n_employers=4, size=3)
    w.individuals = _worker()
    nuvarande = w.jobs.at[0, "job_id"]
    utlovad = w.jobs.at[5, "job_id"]

    w.individuals.at[0, "status"] = "employed"
    w.individuals.at[0, "job_id"] = nuvarande
    w.jobs.loc[w.jobs.index[0], "individual_id"] = "i0"
    w.set_job_filled(nuvarande, True)

    # den utlovade positionen förstörs innan tillträdet
    w.jobs.loc[w.jobs.index[5], "active"] = False
    handle_start_job({"time": 40.0, "agent_id": 0, "event_type": "start_job",
                      "params": {"job_id": utlovad}}, w)

    assert w.individuals.at[0, "status"] == "employed", "förlorade sitt jobb i onödan"
    assert w.individuals.at[0, "job_id"] == nuvarande
    assert w.jobs.at[0, "individual_id"] == "i0"

    emp = int((w.individuals["status"] == "employed").sum())
    filled_active = int((w.jobs["individual_id"].notna()
                         & w.jobs["active"].astype(bool)).sum())
    assert emp == filled_active


def test_education_ending_does_not_orphan_a_job_taken_meanwhile():
    """REGRESSION: sekvensen som gav kategori E. En arbetslös matchar ett jobb
    (utlovat, tillträde om 30 dagar), börjar sedan studera, och tillträder
    jobbet under studietiden. handle_end_education satte då ovillkorligen
    arbetslös, varpå positionen blev kvar tillsatt med hennes id utan
    sysselsatt innehavare -- 21 sådana fall i en femårskörning."""
    from core.event_handlers import handle_end_education

    w = make_world(n_employers=3, size=2)
    w.individuals = _worker()
    jid = w.jobs.at[1, "job_id"]
    w.individuals.at[0, "status"] = "employed"
    w.individuals.at[0, "job_id"] = jid
    w.jobs.loc[w.jobs.index[1], "individual_id"] = "i0"
    w.set_job_filled(jid, True)

    handle_end_education({"time": 400.0, "agent_id": 0,
                          "event_type": "end_education",
                          "params": {"education_type": "specialist"}}, w)

    assert w.individuals.at[0, "status"] == "employed"
    assert w.jobs.at[1, "individual_id"] == "i0"
    emp = int((w.individuals["status"] == "employed").sum())
    fa = int((w.jobs["individual_id"].notna() & w.jobs["active"].astype(bool)).sum())
    assert emp == fa


def test_become_unemployed_always_frees_the_job():
    """Den gemensamma vägen ur sysselsättning ska alltid frigöra positionen."""
    from core.event_handlers import _become_unemployed

    w = make_world(n_employers=2, size=2)
    w.individuals = _worker()
    jid = w.jobs.at[0, "job_id"]
    w.individuals.at[0, "status"] = "employed"
    w.individuals.at[0, "job_id"] = jid
    w.jobs.loc[w.jobs.index[0], "individual_id"] = "i0"
    w.set_job_filled(jid, True)

    _become_unemployed(w, 0, 100.0)

    assert w.individuals.at[0, "status"] == "unemployed"
    assert pd.isna(w.individuals.at[0, "job_id"])
    assert pd.isna(w.jobs.at[0, "individual_id"])
    assert bool(w.vacant_mask()[0])


# ---------------------------------------------------------------------------
# Kravintensiteten hos nypostade jobb (0051)
# ---------------------------------------------------------------------------

def _world_with_geometry():
    """Värld med en liten yrkestabell i minnet.

    Mallyrket A är krävande (r = 0.84), det yrke new_events jobb faktiskt får är B
    och kravlöst (r = 0.00). Ärvs kravet från mallen blir varje nypostat
    diskjobb ett kirurgjobb.
    """
    import sqlite3
    w = make_world(n_employers=1, size=4, simulation={
        "vacancy_fill_rate": 1.0, "occupation_source": "register"})
    w.jobs["onet_code"] = "A"
    w.jobs["r_req"] = 0.84
    w.conn = sqlite3.connect(":memory:")
    pd.DataFrame({
        "onet_code": ["A", "B"],
        "chi": [0.30, 0.55], "xi": [0.3, 2.1],
        "x_occ": [0.30, -0.20], "y_occ": [0.10, 0.40],
        "r_o": [0.27, 0.31], "w_rel": [1.80, 0.49],
        "r_req": [0.84, 0.00], "geom_source": ["occupation", "occupation"],
    }).to_sql("onet_occupation_space", w.conn, index=False)
    pd.DataFrame({"municipal_code": ["2062"], "onet_code": ["B"],
                  "weight": [1.0]}).to_sql(
        "occupation_weights_by_municipality", w.conn, index=False)
    return w


def test_new_job_gets_requirement_from_its_own_occupation():
    """REGRESSION: _geom_lookup hämtade inte r_req, så ett nypostat jobb fick
    position och lön ur sitt eget yrke men KRAVET ur mallen."""
    w = _world_with_geometry()
    w.jobs["active"] = False                      # underskott 4 hos arbetsgivaren
    assert w.post_vacancies_batch(30.0) == 4

    new = w.jobs[w.jobs["job_id"].str.startswith("N")]
    assert len(new) == 4
    assert (new["onet_code"] == "B").all()
    assert (new["r_req"] == 0.00).all(), "kravet ärvdes från mallens yrke"
    assert (new["wage"] == 0.49).all()            # lönen följde redan yrket


def test_requirement_does_not_drift_across_generations():
    """Mallen är den sist tillagda raden per arbetsgivare, så ett ärvt fel
    ärvs vidare och växer under körningen."""
    w = _world_with_geometry()
    for m in range(1, 6):
        w.jobs["active"] = False
        w.post_vacancies_batch(30.0 * m)
    born = w.jobs[w.jobs["job_id"].str.startswith("N")]
    assert len(born) >= 8
    assert (born["r_req"] == 0.00).all()


def test_missing_requirement_is_not_treated_as_maximum(jobs):
    """REGRESSION: fallbacken var r = 1, det strängaste kravet, vilket gör
    varje jobb otillsättbart under q = 0.837 utan att synas i utfallet."""
    from core.occupations.utils import build_job_arrays

    A = build_job_arrays(jobs)                    # ramen saknar r_req helt
    assert (A["r_req"] == 0.0).all()

    partial = jobs.copy()
    partial["r_req"] = 0.3
    partial.loc[partial.index[:3], "r_req"] = np.nan
    with pytest.raises(ValueError, match="r_req saknas för 3"):
        build_job_arrays(partial)


# ---------------------------------------------------------------------------
# Pendlingsavstånd och smutsflagga (0052)
# ---------------------------------------------------------------------------

def test_search_once_returns_commute_distance():
    """REGRESSION: km beräknades i search_once och kastades, så ingen kunde
    efteråt se hur långt någon pendlar."""
    import numpy as np
    from core.occupations.utils import search_once, build_job_arrays

    jobs = pd.DataFrame({
        "job_id": ["A"], "x_occ": [0.3], "y_occ": [0.1], "r_o": [0.27],
        "wage": [1.0], "r_req": [0.0],
        "x": [30_000.0], "y": [40_000.0],          # 50 km från origo
        "individual_id": [np.nan], "active": [True],
    })
    ind = pd.Series({"x_occ": 0.3, "y_occ": 0.1, "r_i": 0.0,
                     "x": 0.0, "y": 0.0, "w_res": 0.0})
    A = build_job_arrays(jobs)

    out = search_once(ind, jobs, np.arange(1), sigma_gamma=0.875,
                      commute_cost_per_km=0.0, rng=np.random.default_rng(0),
                      arrays=A, competitiveness=lambda jx, jy, jro: np.array([1.0]))
    assert len(out) == 5
    assert out[0] == 0
    assert out[4] == pytest.approx(50.0)

    # Tom kandidatmängd ska ha samma aritet, annars fallerar uppackningen
    assert search_once(ind, jobs, np.array([], dtype=int), arrays=A) == (None,) * 5


def test_dirty_flag_ignores_untracked_files(tmp_path):
    """REGRESSION: git_dirty räknade otrackade filer, så en skrapfil i trädet
    gjorde varje körning omöjlig att återskapa enligt rapporten."""
    import subprocess
    from core import scenario_runner as sr

    repo = tmp_path / "r"
    repo.mkdir()
    run = lambda *a: subprocess.run(a, cwd=repo, check=True,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    (repo / "sparad.py").write_text("x = 1\n")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "init")

    assert sr._git_dirty(repo) is False
    assert sr._git_untracked(repo) == 0

    (repo / "kor.sh").write_text("echo hej\n")          # skrapfil, otrackad
    assert sr._git_dirty(repo) is False, "otrackad fil ska inte räknas som smuts"
    assert sr._git_untracked(repo) == 1

    (repo / "sparad.py").write_text("x = 2\n")          # riktig ändring
    assert sr._git_dirty(repo) is True


# ---------------------------------------------------------------------------
# Yrkesdragningen för nypostade jobb (0053)
# ---------------------------------------------------------------------------

def _world_with_sni_source(source="sni"):
    """Värld med SNI-struktur och SNI→O*NET-koppling i minnet.

    Kommunen har två SNI-sektioner, Q (75 % av sysselsättningen) och F (25 %).
    Q leder till två yrken med frekvens 3 och 1, F till ett. Väntad
    yrkesfördelning: Q1 0.5625, Q2 0.1875, F1 0.25.
    """
    import sqlite3
    w = make_world(n_employers=1, size=4, simulation={
        "vacancy_fill_rate": 1.0, "occupation_source": source})
    w.jobs["onet_code"] = "MALL"
    w.jobs["r_req"] = 0.5
    w.conn = sqlite3.connect(":memory:")
    pd.DataFrame({
        "municipal_code": ["2062"] * 2, "year": [2020, 2020],
        "sni_code": ["Q", "F"], "employed": [750, 250], "workplaces": [10, 5],
    }).to_sql("employment_municipality_sni", w.conn, index=False)
    pd.DataFrame({
        "sni_code": ["Q", "Q", "F"],
        "onet_code": ["Q1", "Q2", "F1"], "freq": [3.0, 1.0, 9.0],
    }).to_sql("sni_onet_link", w.conn, index=False)
    pd.DataFrame({
        "onet_code": ["Q1", "Q2", "F1", "MALL"],
        "chi": [0.3, 0.4, 0.5, 0.2], "xi": [0.1, 1.0, 2.0, 3.0],
        "x_occ": [0.3, -0.2, 0.1, 0.0], "y_occ": [0.1, 0.4, -0.3, 0.0],
        "r_o": [0.27, 0.31, 0.22, 0.30], "w_rel": [1.5, 0.9, 0.7, 1.0],
        "r_req": [0.84, 0.40, 0.15, 0.50],
        "geom_source": ["occupation"] * 4,
    }).to_sql("onet_occupation_space", w.conn, index=False)
    return w


def test_new_jobs_draw_occupations_from_the_sni_source():
    """REGRESSION: _draw_occupation_for_employer frågade alltid registret,
    oavsett occupation_source. Med förvalet 'sni' saknas den tabellen, felet
    svaldes av except Exception, och varje nytt jobb ärvde mallens yrke."""
    w = _world_with_sni_source("sni")
    codes, p = w._occupation_profile("2062")
    got = dict(zip(codes, p))
    assert got["Q1"] == pytest.approx(0.5625)
    assert got["Q2"] == pytest.approx(0.1875)
    assert got["F1"] == pytest.approx(0.2500)
    assert "MALL" not in got, "mallens yrke ska inte komma ur fördelningen"

    np.random.seed(0)
    w.jobs["active"] = False
    assert w.post_vacancies_batch(30.0) == 4
    new = w.jobs[w.jobs["job_id"].str.startswith("N")]
    assert set(new["onet_code"]) <= {"Q1", "Q2", "F1"}
    assert (new["onet_code"] != "MALL").all()


def test_employer_does_not_drift_to_monoculture():
    """Mallen är sist tillagda raden, så en ärvd yrkeskod ärvs vidare och
    arbetsgivaren driver mot ett enda yrke."""
    w = _world_with_sni_source("sni")
    np.random.seed(3)
    for m in range(1, 16):
        w.jobs["active"] = False
        w.post_vacancies_batch(30.0 * m)
    born = w.jobs[w.jobs["job_id"].str.startswith("N")]
    assert len(born) >= 40
    assert born["onet_code"].nunique() >= 2, "alla new_events jobb fick samma yrke"


def test_missing_occupation_source_is_a_hard_error():
    """En tom yrkeskälla gav tyst mallens yrke. Nu stannar den."""
    w = _world_with_sni_source("register")      # registertabellen finns inte
    with pytest.raises(ValueError, match="occupation_source='register'"):
        w._occupation_profile("2062")


# ---------------------------------------------------------------------------
# Rapportens pendlings- och vakansmått (0054)
# ---------------------------------------------------------------------------

def test_summary_reports_commute_and_vacancy_duration(tmp_path):
    """Vakansstocken är det enda som kan flytta u, eftersom U = L - J + V ger
    u = u_min + V/L exakt. Utan varaktigheten gick det inte att se vilken av
    u och v som var för hög."""
    import numpy as np
    from core.analysis.eventlog import summary_row

    rd = tmp_path / "run_x"
    (rd / "tables").mkdir(parents=True)
    # 12 månader, 100 vakanser i snitt; 600 anställningar på ett år
    pd.DataFrame({"month": range(1, 13), "year": np.linspace(1/12, 1.0, 12),
                  "employed": [900]*12, "unemployed": [100]*12,
                  "vacancies": [100]*12, "active_jobs": [1000]*12,
                  "labour_force": [1000]*12, "posted": [0]*12,
                  "not_in_labour_force": [0]*12,
                  "u": [10.0]*12, "v": [10.0]*12, "tightness": [1.0]*12,
                  "identity_residual": [0]*12,
                  }).to_csv(rd / "tables" / "timeseries.csv", index=False)
    n = 600
    pd.DataFrame({
        "time": np.linspace(1, 365, n), "year": np.linspace(0.01, 1.0, n),
        "agent_id": range(n), "job_id": [f"J{i}" for i in range(n)],
        "u_R": 1.0, "u_R_occ": 1.0, "commute_km": np.r_[np.zeros(n//2),
                                                        np.full(n//2, 20.0)],
        "w_field": 1.0, "w_neg": 0.85, "q_hire": 0.8, "r_req": 0.3,
        "occ_change": True, "is_mgmt": False, "in_cps_sample": True,
        "wage_ratio": 0.85,
    }).to_csv(rd / "tables" / "transitions.csv", index=False)
    pd.DataFrame({"time": [], "event": []}).to_csv(rd / "tables" / "flows.csv",
                                                   index=False)

    row = summary_row(str(rd), events=[],
                      tr=pd.read_csv(rd / "tables" / "transitions.csv"),
                      ts=pd.read_csv(rd / "tables" / "timeseries.csv"))

    assert row["median_commute_km"] == pytest.approx(10.0)
    assert row["p90_commute_km"] == pytest.approx(20.0)
    # Little: 100 vakanser / 600 per år = 0.1667 år = 60.9 dagar
    assert row["vacancy_days"] == pytest.approx(60.9, abs=0.5)


# ---------------------------------------------------------------------------
# Annonsering, konkurrens och urval (0055)
# ---------------------------------------------------------------------------

def _world_with_applicants(qs, window=40.0):
    """Värld där tre arbetslösa har ansökt om samma jobb med olika q."""
    w = make_world(n_employers=1, size=4, simulation={
        "application_window_days": window,
        "event_timings": {"recruitment_lag": {"dist": "fixed", "mean": 30.0},
                          "start_job_search": {"dist": "fixed", "mean": 28.0}}})
    # Fångar schemalagda händelser: kön exponerar ingen läsvy.
    w._pushed = []
    orig = w._push_event
    def spy(ev, _o=orig, _w=w):
        _w._pushed.append(ev)
        return _o(ev)
    w._push_event = spy

    n = len(qs)
    w.individuals = pd.DataFrame({
        "individual_id": np.arange(n, dtype=float),
        "status": ["unemployed"] * n, "job_id": [np.nan] * n,
        "w_res": [0.5] * n, "chi": 0.3, "xi": 0.3, "r_i": 0.0,
        "x_occ": 0.1, "y_occ": 0.1,
    }, index=range(n))

    jid = w.jobs.iloc[0]["job_id"]
    for i, q in enumerate(qs):
        w.file_application(jid, i, 0.0, q=q, w_neg=0.8, surplus=0.1,
                           commute_km=5.0)
    return w, jid


def test_employer_picks_the_most_qualified_applicant():
    """REGRESSION: först till kvarn. Utan urval doseras q en enda gång, som
    mötessannolikhet, och avståndsfördelningen blir en ren Rayleigh med
    kärnans median."""
    from core.event_handlers import handle_close_vacancy

    w, jid = _world_with_applicants([0.31, 0.92, 0.55])
    assert len(w.applications[jid]) == 3

    handle_close_vacancy({"time": 40.0, "agent_id": 0, "event_type": "close_vacancy",
                          "params": {"job_id": jid}}, w)

    # Vinnaren är den med högst q, och bara hon
    pushed = [e for e in w._pushed if e["event_type"] == "start_job"]
    assert len(pushed) == 1
    assert pushed[0]["agent_id"] == 1
    assert pushed[0]["params"]["q_hire"] == pytest.approx(0.92)
    assert pushed[0]["params"]["n_applicants"] == 3
    # Förlorarna får INGEN ny sökkedja: den de fick vid ansökan lever redan.
    # Två kedjor per ansökan gav 2**5 sökhändelser per person och stannade
    # körningen.
    assert [e for e in w._pushed if e["event_type"] == "start_job_search"] == []
    assert jid not in w.applications


def test_application_window_leaves_the_identity_untouched():
    """Under fönstret är arbetaren arbetslös och positionen ledig. Byter något
    tillstånd där går U = L - J + V sönder."""
    w, jid = _world_with_applicants([0.4, 0.6])
    pos = w.job_index()[jid]
    assert bool(w.vacant_mask()[pos]), "annonserad position ska vara ledig"
    assert pd.isna(w.jobs.at[pos, "individual_id"])
    assert (w.individuals.loc[[0, 1], "status"] == "unemployed").all()
    assert w.n_open_applications() == 2


def test_window_opens_once_per_vacancy():
    """En close_vacancy per annons, schemalagd vid första ansökan."""
    w, jid = _world_with_applicants([0.4, 0.6, 0.5])
    closes = [e for e in w._pushed if e["event_type"] == "close_vacancy"]
    assert len(closes) == 1
    assert closes[0]["time"] == pytest.approx(40.0)
    assert closes[0]["params"]["job_id"] == jid


def test_vacancy_with_no_eligible_applicants_stays_open():
    """Hann någon annan bli anställd under fönstret får ingen jobbet, och de
    sökande går tillbaka till marknaden i stället för att fastna."""
    from core.event_handlers import handle_close_vacancy

    w, jid = _world_with_applicants([0.4, 0.9])
    w.individuals["status"] = "employed"                  # båda hann få annat
    w.individuals["notice_job_id"] = "J09999"             # och sagt upp sig
    handle_close_vacancy({"time": 40.0, "agent_id": 0, "event_type": "close_vacancy",
                          "params": {"job_id": jid}}, w)
    assert not [e for e in w._pushed if e["event_type"] == "start_job"]
    pos = w.job_index()[jid]
    assert pd.isna(w.jobs.at[pos, "individual_id"])


def test_applicant_count_reaches_the_transitions_table():
    """REGRESSION: n_applicants lades i händelsen och i loggen men glömdes i
    transitions_table, så måttet fanns i eventlog.csv och nådde aldrig
    analysen. Utan det går "ingen sökte" inte att skilja från "urvalet var
    svagt", och de två kräver motsatta åtgärder."""
    from core.analysis.eventlog import transitions_table

    ev = [{"event": "start_job", "time": 100.0, "agent_id": 7, "job_id": "J1",
           "from_onet": "11-1011.00", "to_onet": "35-9021.00",
           "u_R": 0.8, "u_R_occ": 0.8, "w_field": 1.0, "w_neg": 0.85,
           "q_hire": 0.9, "r_req": 0.3, "commute_km": 12.0,
           "n_applicants": 3, "occ_change": 1},
          {"event": "start_job", "time": 200.0, "agent_id": 8, "job_id": "J2",
           "from_onet": "11-1011.00", "to_onet": "35-9021.00",
           "u_R": 1.9, "u_R_occ": 1.9, "w_field": 0.6, "w_neg": 0.51,
           "q_hire": 0.2, "r_req": 0.0, "commute_km": 4.0,
           "n_applicants": 1, "occ_change": 1}]
    tr = transitions_table(ev)

    assert "n_applicants" in tr.columns
    assert tr["n_applicants"].tolist() == [3.0, 1.0]
    # Den obestridda vakansen är den med lågt krav: där söker ingen, så
    # urvalet uteblir och avståndet blir långt.
    assert tr.loc[tr["n_applicants"] == 1, "r_req"].iloc[0] == 0.0


# ---------------------------------------------------------------------------
# Kön i överskottet (0057)
# ---------------------------------------------------------------------------

def test_queue_makes_a_crowded_vacancy_less_attractive():
    """REGRESSION: logiten valde på ANNONSERAD lön. Med choice_scale 0.05 mot
    ett lönespann 0.49-1.81 blev valet nästan deterministiskt: 806 ansökningar
    på ETT jobb, tio procent av jobben tog 73 procent av ansökningarna, och
    9 099 av 15 554 positioner sågs aldrig av någon under fem år."""
    from core.occupations.utils import search_once, build_job_arrays

    # Två jobb på samma plats i uppgiftsrummet. Det trängda betalar MER.
    jobs = pd.DataFrame({
        "job_id": ["TRANGT", "TOMT"],
        "x_occ": [0.3, 0.3], "y_occ": [0.1, 0.1], "r_o": [0.27, 0.27],
        "wage": [1.60, 1.00], "r_req": [0.0, 0.0],
        "x": [0.0, 0.0], "y": [0.0, 0.0],
        "individual_id": [np.nan, np.nan], "active": [True, True],
    })
    ind = pd.Series({"x_occ": 0.3, "y_occ": 0.1, "r_i": 0.0,
                     "x": 0.0, "y": 0.0, "w_res": 0.0})
    A = build_job_arrays(jobs)
    kw = dict(sigma_gamma=0.875, commute_cost_per_km=0.0, choice_scale=0.05,
              arrays=A, competitiveness=lambda jx, jy, jro: np.ones(len(jx)))

    def valt(queue, n=200):
        rng = np.random.default_rng(4)
        picks = [search_once(ind, jobs, np.arange(2), queue=queue, rng=rng, **kw)[0]
                 for _ in range(n)]
        return sum(1 for p in picks if p == 0) / n     # andel som valde TRANGT

    # Utan kö vinner den högre lönen nästan alltid
    assert valt(None) > 0.95
    assert valt(np.array([0.0, 0.0])) > 0.95
    # Med tjugo liggande ansökningar är förväntat utfall 1.60/21 << 1.00
    assert valt(np.array([20.0, 0.0])) < 0.05


def test_queue_counts_come_from_the_application_lists():
    w, jid = _world_with_applicants([0.4, 0.6, 0.5])
    n = w.applicant_counts()
    pos = w.job_index()[jid]
    assert n[pos] == 3.0
    assert n.sum() == 3.0
    w.close_application_window(jid)
    assert w.applicant_counts().sum() == 0.0


# ---------------------------------------------------------------------------
# Parallella ansökningar och de tre tiderna (0058)
# ---------------------------------------------------------------------------

def test_no_duplicate_application_to_the_same_job():
    """Med parallella ansökningar kan hon annars hamna två gånger i kön."""
    w, jid = _world_with_applicants([0.5])
    assert w.file_application(jid, 0, 5.0, q=0.5, w_neg=0.8, surplus=0.1,
                              commute_km=3.0) is False
    assert len(w.applications[jid]) == 1
    assert w.applicant_counts()[w.job_index()[jid]] == 1.0


def test_worker_under_notice_does_not_apply():
    """Den som redan sagt upp sig för ett annat jobb söker inte vidare. Efter
    0079 söker anställda i övrigt precis som arbetslösa -- statusvakten var
    skriven för att hindra det, eftersom sökning från anställning inte fanns."""
    from core.matching_core import apply_once

    w, jid = _world_with_applicants([0.5])
    w.individuals["notice_job_id"] = pd.Series([None] * len(w.individuals),
                                               index=w.individuals.index,
                                               dtype="object")
    w.individuals.at[0, "status"] = "employed"
    w.individuals.at[0, "notice_job_id"] = "J09999"
    assert apply_once(w, 0, 50.0) == (None,) * 5
    assert w.n_open_applications() == 1


def test_unemployed_hire_has_no_notice_period():
    """De tre tiderna: annonstiden är avverkad vid stängning, kvar är beslut
    (alla) plus uppsägningstid (bara för den som lämnar en anställning).
    Utlovade positioner ingår i unmatched_jobs och därmed i V, så
    uppsägningstiden låg tidigare i vakansvaraktigheten för ALLA."""
    from core.event_handlers import handle_close_vacancy

    w, jid = _world_with_applicants([0.9])
    w._pushed.clear()
    handle_close_vacancy({"time": 40.0, "agent_id": 0, "event_type": "close_vacancy",
                          "params": {"job_id": jid}}, w)
    start = [e for e in w._pushed if e["event_type"] == "start_job"][0]
    assert start["time"] == pytest.approx(50.0)      # 40 + 10, ingen uppsägning


def test_notice_period_applies_only_to_someone_leaving_a_job():
    """Uppsägningsgrenen är oåtkomlig i dag -- urvalet släpper bara fram
    arbetslösa -- men den ska ärvas färdig av steg 2, så den prövas här."""
    from core.event_handlers import start_delay_days

    w, _ = _world_with_applicants([0.9])
    assert start_delay_days(w, 0) == pytest.approx(10.0)
    w.individuals.at[0, "status"] = "employed"
    assert start_delay_days(w, 0) == pytest.approx(40.0)


def test_rejection_does_not_start_a_second_search_chain():
    """REGRESSION: 0058 schemalade en sökning vid ANSÖKAN, och
    handle_close_vacancy schemalade en till vid AVSLAG. Varje ansökan gav
    därmed två levande sökkedjor; med fem ansökningar före en anställning
    2**5 sökhändelser per person, och körningen stannade av."""
    from core.event_handlers import handle_close_vacancy

    w, jid = _world_with_applicants([0.2, 0.9, 0.5])
    # 0.7 och inte 1.0: sedan 0095 avslår hon ett erbjudande som inte ger
    # överskott mot hennes läge nu, och budet här är w_neg 0.8 med 5 km. Med
    # w_res 1.0 skulle alla tre avslå och provets "en anställning" utebli av
    # ett annat skäl än det provet handlar om.
    for i in range(3):
        w.individuals.at[i, "w_res"] = 0.7
    w._pushed.clear()
    handle_close_vacancy({"time": 40.0, "agent_id": 0, "event_type": "close_vacancy",
                          "params": {"job_id": jid}}, w)

    assert [e for e in w._pushed if e["event_type"] == "start_job_search"] == []
    assert len([e for e in w._pushed if e["event_type"] == "start_job"]) == 1
    # men reservationen ska ha fallit för förlorarna, inte för vinnaren
    decay = w.cfg_reader.config["simulation"].get("reservation_decay_per_search", 1.0)
    if decay < 1.0:
        assert w.individuals.at[0, "w_res"] < 0.7
        assert w.individuals.at[2, "w_res"] < 0.7
        assert w.individuals.at[1, "w_res"] == 0.7


def test_applicant_counts_are_maintained_incrementally():
    """En array över femtontusen jobb byggd om vid varje sökning är ren
    allokeringsvärme; den underhålls punktvis som vacant_mask."""
    w, jid = _world_with_applicants([0.4, 0.6])
    pos = w.job_index()[jid]
    assert w.applicant_counts()[pos] == 2.0
    assert w.applicant_counts() is w.applicant_counts()      # samma array
    w.file_application(jid, 5, 1.0, q=0.3, w_neg=0.8, surplus=0.1, commute_km=1.0)
    assert w.applicant_counts()[pos] == 3.0
    w.close_application_window(jid)
    assert w.applicant_counts()[pos] == 0.0


def test_employer_effect_varies_pay_where_productivity_cannot():
    """REGRESSION: i jobb med r_j ~ 0 är p = q**0 = 1 för ALLA, så utan en
    arbetsgivarkanal får hela kvartilen identisk lön -- 34.8 procent av
    anställningarna där låg på exakt samma punkt. Med theta flyttar atomen
    bara från 0.85 till 1.00; eta är det enda som varierar där."""
    from core.occupations.utils import negotiated_wage

    ny = dict(theta=0.5, labour_share=0.65, wage_floor_share=0.70)
    # Två diskjobb, samma yrke, olika arbetsgivare
    Pi_o, eta = 0.60, np.array([-0.15, 0.0, 0.20])
    Pi_j = Pi_o * np.exp(eta)
    w = negotiated_wage(np.ones(3), Pi_j, 0.0, **ny)
    assert len(set(np.round(w, 6))) == 3, "identisk lön trots olika arbetsgivare"
    assert w[2] / w[0] == pytest.approx(np.exp(0.35), rel=1e-6)


def test_new_jobs_inherit_the_employer_wage_effect():
    """eta är en egenskap hos arbetsgivaren och följer med mallen. Utan det
    tappar nypostade jobb sin arbetsgivareffekt och betalar yrkets
    normallön oavsett var de sitter."""
    w = _world_with_geometry()
    w.jobs["wage_eta"] = 0.25
    w.jobs["active"] = False
    assert w.post_vacancies_batch(30.0) == 4
    new = w.jobs[w.jobs["job_id"].str.startswith("N")]
    assert (new["wage_eta"] == 0.25).all()
    assert new["wage"].iloc[0] == pytest.approx(0.49 * np.exp(0.25))


def test_bootstrap_actually_hires_and_leaves_no_pending_leak():
    """REGRESSION: första försöket läste tillträdena UR kön efter att
    annonserna stängts. _push_event kastar tyst allt bortom
    simulation_end_time, så 172 positioner sattes till pending medan
    tillträdena försvann: noll anställda och en läcka i bokföringen.
    Tillträdena fångas nu vid källan."""
    from core.matching_core import bootstrap_matching

    w = make_world(n_employers=30, size=6,
                   simulation={"application_window_days": 40})
    n = 200
    w.individuals = pd.DataFrame({
        "individual_id": np.arange(n, dtype=float),
        "status": ["unemployed"] * n,
        "job_id": pd.Series([None] * n, dtype="object"),
        "w_res": 0.3, "x_occ": np.linspace(-0.4, 0.4, n),
        "y_occ": np.linspace(0.4, -0.4, n), "r_i": 0.0, "x": 0.0, "y": 0.0,
        "propensity_start_education": 0.1,
        "propensity_internal_training": 0.1, "propensity_quit_job": 0.1,
        "propensity_career_break": 0.05,
        "propensity_internal_job_change": 0.1,
        "w_neg": np.nan, "q_last": np.nan}, index=range(n))
    w.jobs["r_req"] = 0.0
    w.jobs["wage"] = 1.0

    st = bootstrap_matching(w, 0.0, log=None)

    anställda = int((w.individuals["status"] == "employed").sum())
    assert anställda > 0, "uppstarten anställde ingen"
    assert st["bootstrap_hired"] == anställda
    assert st["bootstrap_rounds"] >= 1
    # Inga positioner får bli kvar utlovade: pending utan tillträde är en
    # läcka i U = L - J + V
    if "pending" in w.jobs.columns:
        assert int(w.jobs["pending"].fillna(False).sum()) == 0
    # Var och en som fick jobb bär sin förhandlade lön
    lön = w.individuals.loc[w.individuals["status"] == "employed", "w_neg"]
    assert lön.notna().all() and (lön > 0).all()


def test_bootstrap_prepares_the_world_first():
    """REGRESSION: active, pending och kompetenscirklarna skapades i
    _init_events, som körs FÖRST I simulate() -- alltså efter uppstarten. Den
    gamla batch-matchningen behövde inget av det, så ordningen fungerade av en
    slump. Uppstarten i 0069 är samma kod som körningen och föll på
    KeyError: 'active' vid första tillträdet."""
    import inspect
    from core.matching_core import bootstrap_matching
    from core.world import World

    assert hasattr(World, "prepare")
    assert "prepare" in inspect.getsource(bootstrap_matching)

    w = make_world(n_employers=3, size=4)
    for kol in ("active", "pending", "created_time", "destroyed_time"):
        if kol in w.jobs.columns:
            w.jobs = w.jobs.drop(columns=[kol])
    w.prepare()
    assert {"active", "pending"} <= set(w.jobs.columns)
    n_aktiva = int(w.jobs["active"].sum())
    w.prepare()                                  # idempotent
    assert int(w.jobs["active"].sum()) == n_aktiva


def test_bootstrap_returns_its_matchings_for_the_statistics():
    """scenario_runner räknar pendlings- och matchningsstatistik på paren från
    uppstarten. Den gamla batchen returnerade dem; utan att bootstrap gör det
    faller körningen på NameError efter att uppstarten lyckats."""
    from core.matching_core import bootstrap_matching

    w = make_world(n_employers=20, size=5,
                   simulation={"application_window_days": 40})
    n = 120
    w.individuals = pd.DataFrame({
        "individual_id": np.arange(n, dtype=float),
        "status": ["unemployed"] * n,
        "job_id": pd.Series([None] * n, dtype="object"),
        "w_res": 0.3, "x_occ": np.linspace(-0.4, 0.4, n),
        "y_occ": np.linspace(0.4, -0.4, n), "r_i": 0.0, "x": 0.0, "y": 0.0,
        "propensity_start_education": 0.1,
        "propensity_internal_training": 0.1, "propensity_quit_job": 0.1,
        "propensity_career_break": 0.05,
        "propensity_internal_job_change": 0.1,
        "w_neg": np.nan, "q_last": np.nan}, index=range(n))
    w.jobs["r_req"] = 0.0
    w.jobs["wage"] = 1.0

    st = bootstrap_matching(w, 0.0, log=None)
    m = st["matchings"]
    assert list(m.columns) == ["individual_id", "job_id", "utility"]
    assert len(m) == int((w.individuals["status"] == "employed").sum())
    assert len(m) == st["bootstrap_hired"]
    assert m["job_id"].is_unique, "samma position tilldelad två gånger"


def test_wage_columns_belong_to_the_individual_schema():
    """REGRESSION, andra gången. w_neg och q_last skapades i
    _seed_wages_for_matched, som utgick med 0069 -- och då fanns ingen
    producent kvar. Vakten "if 'w_neg' in ind.columns" i apply_once blev falsk
    vid varje anställning, exakt som i 0068, och körningen föll först vid
    första årsskiftet med 'har anställda men saknar kolumnen w_neg'.

    Kolumnerna hör till individens schema, inte till en enskild funktion, och
    skrivningen sker utan vakt."""
    import inspect
    from core import matching_core as mc
    from core import event_handlers as eh

    w = make_world(n_employers=3, size=4)
    w.individuals = pd.DataFrame({
        "individual_id": [0.0], "status": ["unemployed"],
        "job_id": pd.Series([None], dtype="object"), "w_res": [0.4]})
    w.prepare()
    assert {"w_neg", "q_last", "notice_job_id"} <= set(w.individuals.columns)

    # Ingen tyst vakt kvar runt skrivningen
    for fn in (mc.apply_once, eh.handle_start_job):
        kod = [ln for ln in inspect.getsource(fn).splitlines()
               if not ln.lstrip().startswith("#")]
        text = "".join("\n".join(kod).split('"""')[::2])
        assert "'w_neg' in ind.columns" not in text, f"tyst vakt kvar i {fn.__name__}"


def test_bootstrap_rebuilds_the_queue_every_round():
    """REGRESSION: kön delades upp EN gång och den som inte fick jobb lades
    aldrig tillbaka. Med 11 502 arbetslösa och 10 754 lediga jobb rymdes hela
    kön i första omgången (2.4 x 10 754), loopen avslutades efter en omgång,
    och 4 500 stod kvar arbetslösa bredvid 3 800 lediga positioner: 60.6
    procent matchade mot en jämvikt kring 86.

    Följden var att hela femårskörningen blev en transient -- anställningarna
    fördubblades till 21 200 och n_cps_sample till 17 700, alltså var halva
    valideringsunderlaget uppstartsdynamik och inte mobilitet.

    I körningen får den som misslyckas en ny sökning var 28:e dag. I
    uppstarten får hon en ny omgång."""
    from core.matching_core import bootstrap_matching

    rng = np.random.default_rng(1)
    w = make_world(n_employers=60, size=8,
                   simulation={"application_window_days": 40})
    n = 300
    th = rng.uniform(0, 2 * np.pi, n)
    rr = np.sqrt(rng.uniform(0, 1, n)) * 0.9
    w.individuals = pd.DataFrame({
        "individual_id": np.arange(n, dtype=float),
        "status": ["unemployed"] * n,
        "job_id": pd.Series([None] * n, dtype="object"),
        "w_res": 0.55, "x_occ": rr * np.cos(th), "y_occ": rr * np.sin(th),
        "r_i": 0.0, "x": 0.0, "y": 0.0,
        "propensity_start_education": 0.1,
        "propensity_internal_training": 0.1, "propensity_quit_job": 0.1,
        "propensity_career_break": 0.05,
        "propensity_internal_job_change": 0.1}, index=range(n))
    m = len(w.jobs)
    th2 = rng.uniform(0, 2 * np.pi, m)
    r2 = np.sqrt(rng.uniform(0, 1, m)) * 0.9
    w.jobs["x_occ"] = r2 * np.cos(th2)
    w.jobs["y_occ"] = r2 * np.sin(th2)
    w.jobs["r_o"] = 0.15
    w.jobs["r_req"] = 0.0
    w.jobs["wage"] = 1.0

    st = bootstrap_matching(w, 0.0, log=None)

    assert st["bootstrap_rounds"] >= 2, "kön byggdes inte om"
    assert len(st["bootstrap_per_round"]) == st["bootstrap_rounds"]
    # Marknaden ska vara uttömd: inte både arbetslösa OCH lediga kvar
    kvar_arbetslösa = int((w.individuals["status"] == "unemployed").sum())
    kvar_lediga = int(w.vacant_mask().sum())
    assert kvar_arbetslösa == 0 or kvar_lediga == 0, (
        f"{kvar_arbetslösa} arbetslösa bredvid {kvar_lediga} lediga positioner")


def test_run_length_is_read_in_one_place():
    """REGRESSION: slutdatumet läste config['n_years'] med toppnivån först,
    medan kalendern bara läste config['simulation']['n_years'] och föll
    tillbaka på sin egen default fem. Med n_years: 10 på toppnivån -- där det
    står i scenariofilerna -- körde simuleringen tio år med fem års kalender:
    sista new_month på dag 1796, sedan simulation_completed vid 3652.50. Under
    år sex till tio fanns inga månadsskiften, inga årliga tvärsnitt och ingen
    lönerevision."""
    from core.world import World

    class R:
        def __init__(self, cfg):
            self.config = cfg

    w = make_world(n_employers=2, size=4)
    for cfg, väntat in (({"n_years": 10}, 10),
                        ({"simulation": {"n_years": 7}}, 7),
                        ({"n_years": 10, "simulation": {"n_years": 5}}, 10)):
        w.cfg_reader = R(cfg)
        assert w.n_years() == väntat
        assert w._get_simulation_end_time() == pytest.approx(365.25 * väntat)

    # Saknas den är det ett fel, inte ett värde att gissa
    w.cfg_reader = R({"simulation": {}})
    with pytest.raises(KeyError, match="n_years"):
        w.n_years()


# ---------------------------------------------------------------------------
# Sökning från anställning (0079)
# ---------------------------------------------------------------------------

def _byte_world():
    """En anställd med ett jobb, och ett ledigt jobb att byta till."""
    w = make_world(n_employers=2, size=4, simulation={
        "application_window_days": 40, "hiring_decision_days": 10,
        "notice_period_days": 30})
    w.prepare()
    gammalt, nytt = w.jobs["job_id"].iloc[0], w.jobs["job_id"].iloc[1]
    w.individuals = pd.DataFrame({
        "individual_id": [0.0], "status": ["employed"], "job_id": [gammalt],
        "w_res": [0.5], "w_neg": [0.6], "q_last": [np.nan],
        "x_occ": [0.3], "y_occ": [0.1], "r_i": [0.0], "x": [0.0], "y": [0.0],
        "propensity_start_education": [0.1],
        "propensity_internal_training": [0.1], "propensity_quit_job": [0.1],
        "propensity_career_break": [0.05],
        "propensity_internal_job_change": [0.1]}, index=[0])
    w.jobs.loc[w.jobs.index[0], "individual_id"] = 0.0
    w.set_job_filled(gammalt, True)
    w._pushed = []
    orig = w._push_event
    w._push_event = lambda ev, _o=orig, _w=w: (_w._pushed.append(ev), _o(ev))[1]
    return w, gammalt, nytt


def _bokforing(w):
    """(L, J, V) -- arbetskraft, fyllda positioner, lediga."""
    ind, jobs = w.individuals, w.jobs
    L = int(ind["status"].isin(["employed", "unemployed"]).sum())
    aktiva = jobs["active"] if "active" in jobs else pd.Series(True, index=jobs.index)
    J = int((jobs["individual_id"].notna() & aktiva).sum())
    V = int((jobs["individual_id"].isna() & aktiva).sum())
    return L, J, V


def test_identity_holds_through_a_job_change():
    """INVARIANTEN FÖRST. Mellan erbjudande och tillträde håller hon sitt
    GAMLA jobb medan det new_events är utlovat. Frigörs den gamla positionen för
    tidigt hamnar den i V utan att någon blivit arbetslös; sätts hon som
    innehavare av det new_events innan uppsägningstiden gått ut innehar hon två
    positioner. Båda bryter U = L - J + V."""
    from core.event_handlers import handle_close_vacancy, handle_start_job

    w, gammalt, nytt = _byte_world()
    L0, J0, V0 = _bokforing(w)
    U0 = int((w.individuals["status"] == "unemployed").sum())
    assert U0 == L0 - J0 + V0 - V0 + (L0 - J0)  # trivialt sant vid start: U = L - J
    assert U0 == L0 - J0

    # Hon ansöker om det new_events jobbet medan hon är anställd
    w.file_application(nytt, 0, 0.0, q=1.0, w_neg=0.9, surplus=0.3, commute_km=2.0)
    L, J, V = _bokforing(w)
    assert (L, J, V) == (L0, J0, V0), "ansökan får inte röra bokföringen"

    # Annonsen stänger: hon vinner, säger upp sig, uppsägningstid börjar
    handle_close_vacancy({"time": 40.0, "agent_id": None,
                          "event_type": "close_vacancy",
                          "params": {"job_id": nytt}}, w)
    L, J, V = _bokforing(w)
    assert w.individuals.at[0, "status"] == "employed", "hon jobbar kvar under uppsägningen"
    assert w.individuals.at[0, "job_id"] == gammalt
    assert (L, J) == (L0, J0), "hon får inte bli arbetslös vid erbjudandet"
    assert int((w.individuals["status"] == "unemployed").sum()) == L - J + V - V + (L - J)

    # Tillträdet sker efter beslut + uppsägningstid
    start = [e for e in w._pushed if e["event_type"] == "start_job"]
    assert len(start) == 1
    assert start[0]["time"] == pytest.approx(40.0 + 10.0 + 30.0)

    handle_start_job(start[0], w)
    L, J, V = _bokforing(w)
    assert w.individuals.at[0, "job_id"] == nytt
    assert (L, J) == (L0, J0), "hon innehar exakt en position"
    # Den gamla positionen är nu ledig, utan att någon blivit arbetslös
    pos_gammalt = w.job_index()[gammalt]
    assert pd.isna(w.jobs.at[pos_gammalt, "individual_id"])
    assert V == V0, "vakansantalet ska vara oförändrat: en frigjord, en fylld"


def test_employed_reservation_is_the_current_job_plus_friction():
    """Den anställdes alternativ är att STANNA: lönen hon har minus dess
    pendling, plus en bytesfriktion. Utan friktionen byter hon för en krona.
    Den arbetslösas reservation är w_res som förut."""
    from core.matching_core import apply_once

    w, gammalt, nytt = _byte_world()
    w.individuals.at[0, "w_neg"] = 1.0
    # Bara två jobb i spel: hennes eget och ett ledigt som betalar mer
    w.jobs["active"] = False
    for jid, lon in ((gammalt, 1.0), (nytt, 1.02)):
        pos = w.job_index()[jid]
        w.jobs.iat[pos, w.jobs.columns.get_loc("active")] = True
        w.jobs.iat[pos, w.jobs.columns.get_loc("wage")] = lon
    w.jobs["r_req"] = 0.0
    w.prepare()

    # Med fem procents friktion är två procent inte nog
    assert apply_once(w, 0, 0.0)[0] is None
    # Med en procents friktion är det det
    w.cfg_reader.config["simulation"]["switching_cost_share"] = 0.01
    assert apply_once(w, 0, 0.0)[0] == nytt


def test_quit_job_is_not_scheduled_as_an_exogenous_event():
    """REGRESSION, andra gången. 0079 tog bort den exogena quit_job ur
    _init_events och testet inspekterade bara _init_events. Men uppstarten
    går sedan 0069 genom handle_start_job, som fortfarande schemalade en
    quit_job normalfördelad kring sju år vid VARJE tillträde. 84 procent av
    startbeståndet lämnade därför sina jobb utan orsak inom tio år, med
    topp kring 1 300 per år vid år sju, medan commit-meddelandet sade att
    avgången var borta. Provet är nu det som faktiskt händer: ett tillträde
    får inte lägga någon quit_job i kön, och händelsetypen har ingen
    hanterare."""
    from core.event_handlers import RULE_SWITCH, handle_close_vacancy, handle_start_job

    assert "quit_job" not in RULE_SWITCH, "exogen quit_job har en hanterare igen"

    w, gammalt, nytt = _byte_world()
    w.file_application(nytt, 0, 0.0, q=1.0, w_neg=0.9, surplus=0.3, commute_km=2.0)
    handle_close_vacancy({"time": 40.0, "agent_id": None,
                          "event_type": "close_vacancy",
                          "params": {"job_id": nytt}}, w)
    start = [e for e in w._pushed if e["event_type"] == "start_job"][0]
    handle_start_job(start, w)
    typer = {e["event_type"] for e in w._pushed}
    assert "quit_job" not in typer, "tillträdet schemalade en exogen avgång"

    # Men sökimpulsen gäller fortfarande hela arbetskraften vid start
    import inspect
    from core.world import World
    text = inspect.getsource(World._init_events)
    assert "'employed'" in text and "on_the_job_search_factor" in text


def test_job_to_job_is_recorded_at_the_change():
    """REGRESSION: kontrollen låg efter `individuals.at[idx, "job_id"] = job_id`
    och jämförde alltså det new_events jobbet med sig självt. _job_to_job var alltid
    falsk: inga byten registrerades trots att de skedde, job_to_job_rate blev
    noll, kolumnen job_to_job_wage_gain skapades aldrig, och rapporten
    kraschade på den. Ett mått som alltid säger noll ser ut som ett resultat."""
    from core.event_handlers import handle_close_vacancy, handle_start_job

    w, gammalt, nytt = _byte_world()
    w.individuals.at[0, "w_neg"] = 1.00
    w.file_application(nytt, 0, 0.0, q=1.0, w_neg=1.20, surplus=0.3, commute_km=2.0)
    handle_close_vacancy({"time": 40.0, "agent_id": None,
                          "event_type": "close_vacancy",
                          "params": {"job_id": nytt}}, w)
    start = [e for e in w._pushed if e["event_type"] == "start_job"][0]
    handle_start_job(start, w)

    loggat = [dict(e[1]) for e in w.event_logger.events
              if dict(e[1]).get("job_to_job")]
    assert loggat, "bytet registrerades inte"
    assert loggat[-1]["w_prev"] == pytest.approx(1.00)
    assert w.individuals.at[0, "w_neg"] == pytest.approx(1.20)
    assert w.individuals.at[0, "job_id"] == nytt

    # En nyanställd arbetslös är inget byte
    w2, g2, n2 = _byte_world()
    w2.individuals.at[0, "status"] = "unemployed"
    w2.individuals.at[0, "job_id"] = None
    w2.file_application(n2, 0, 0.0, q=1.0, w_neg=0.9, surplus=0.3, commute_km=1.0)
    handle_close_vacancy({"time": 40.0, "agent_id": None,
                          "event_type": "close_vacancy",
                          "params": {"job_id": n2}}, w2)
    s2 = [e for e in w2._pushed if e["event_type"] == "start_job"][0]
    handle_start_job(s2, w2)
    assert not [dict(e[1]) for e in w2.event_logger.events
                if dict(e[1]).get("job_to_job")]


def test_applying_does_not_overwrite_the_current_wage():
    """REGRESSION: apply_once skrev ind['w_neg'] = det sökta jobbets lön VID
    ANSÖKAN. För en arbetslös var det skadligt men osynligt -- hon har ingen
    lön att förstöra. Med sökning från anställning (0079) blev det förödande:
    reservationen läser w_neg som "nuvarande lön", så snart hon sökt ETT jobb
    var hennes jämförelsepunkt det jobbets erbjudna lön i stället för hennes
    egen.

    Spärrhaken i stegen försvann. Utfallet över tio år: 46.6 procent jobbyten
    per år mot svenska tio, medianlönevinst per byte exakt noll -- hon bytte
    till det hon nyss jämfört sig med -- och 100 procent av tillsättningarna
    gick till redan anställda."""
    from core.matching_core import apply_once

    w, gammalt, nytt = _byte_world()
    w.individuals.at[0, "w_neg"] = 1.00
    w.jobs["active"] = False
    for jid, lon in ((gammalt, 1.00), (nytt, 3.00)):
        pos = w.job_index()[jid]
        w.jobs.iat[pos, w.jobs.columns.get_loc("active")] = True
        w.jobs.iat[pos, w.jobs.columns.get_loc("wage")] = lon
    w.jobs["r_req"] = 0.0
    w.prepare()

    jid, w_ny, q, S, km = apply_once(w, 0, 0.0)
    assert jid == nytt, "hon ska söka det bättre jobbet"
    assert w_ny > 1.5, "ansökan bär den erbjudna lönen"
    # ... men hennes egen lön är oförändrad tills hon tillträder
    assert w.individuals.at[0, "w_neg"] == pytest.approx(1.00), \
        "ansökan skrev över den faktiska lönen"

    # Och därför är hennes reservation nästa gång fortfarande den gamla lönen
    assert w.n_open_applications() == 1


def test_posted_vacancy_is_born_now_not_with_the_templates_age():
    """REGRESSION: mallen kopierar alla kolumner, och vacant_since följde
    med. Nypostade jobb föddes med den gamla positionens tidsstämpel --
    oftast 0.0 från starten -- så vakansernas medianålder vid tillsättning
    blev 1 956 dagar: inte samma positioner som stod öppna, utan new_events jobb
    som var fem år gamla vid födseln."""
    w = make_world(n_employers=1, size=4, simulation={"vacancy_fill_rate": 1.0})
    w.jobs["active"] = False
    w.jobs["individual_id"] = np.nan
    w.jobs["vacant_since"] = 0.0
    assert w.post_vacancies_batch(900.0) == 4
    new_events = w.jobs[w.jobs["created_time"] == 900.0]
    assert len(new_events) == 4
    assert (new_events["vacant_since"] == 900.0).all()


def test_freed_position_is_stamped_with_the_event_time():
    """REGRESSION, tredje försöket på samma mått. set_job_filled stämplade
    vacant_since med world.current_time, som sattes till 0 i __init__ och
    aldrig flyttades -- den hörde till den döda tick()-slingan. Varje frigjord
    position fick ålder lika med klockan vid nästa tillsättning: median 1 134
    dagar efter 0086. Tiden är händelsens och ska skickas in; utan den kastas."""
    w = make_world(n_employers=2, size=2)
    jid = w.jobs.at[0, "job_id"]
    w.set_job_filled(jid, True)
    w.set_job_filled(jid, False, 731.5)
    assert float(w.jobs.at[0, "vacant_since"]) == 731.5
    with pytest.raises(TypeError):
        w.set_job_filled(jid, False)


def _search_events(w):
    return [e for e in w._pushed if e["event_type"] == "start_job_search"]


def test_employed_dry_search_continues_the_search():
    """REGRESSION: den anställdes sökkedja dog vid första torra sökning.
    handle_start_job_search lade en ny sökning bara om ansökan lämnats eller
    om hon var arbetslös. En anställd som inte fann något över sin reservation
    sökte aldrig igen förrän hon förlorade jobbet, och den effektiva
    sökintensiteten var en följd av historien, inte av parametern."""
    from core.event_handlers import handle_start_job_search
    w, gammalt, nytt = _byte_world()
    w.prepare()
    w.jobs["active"] = False                      # inget att söka
    w.jobs.loc[w.jobs["job_id"] == gammalt, "active"] = True
    w.schedule_search(0, 100.0)
    w._pushed.clear()
    handle_start_job_search({"time": 100.0, "agent_id": 0, "event_type": "start_job_search",
                             "params": {"due": 100.0}}, w)
    new_events = _search_events(w)
    assert len(new_events) == 1, "torr sökning från anställning ska ge nästa sökning"
    assert new_events[0]["time"] > 100.0
    assert new_events[0]["params"]["due"] == float(w.individuals.at[0, "next_search_time"])


def test_start_job_supersedes_the_old_search_and_applies_the_ramp():
    """REGRESSION: rampen gällde bara uppstarten, och den nyanställdes nästa
    sökning kom ur kedjan hon hade som sökande -- ofta före tillträdet. Nu
    skriver tillträdet next_search_time = t + ramp + intervall, och den gamla
    händelsen kastas när den fyrar."""
    from core.event_handlers import (handle_close_vacancy, handle_start_job,
                                     handle_start_job_search)
    w, gammalt, nytt = _byte_world()
    w.prepare()
    ramp = float(w.cfg_reader.config["simulation"].get("on_the_job_search_ramp_days", 180.0))
    w.schedule_search(0, 50.0)                    # den gamla, som sökande
    w.file_application(nytt, 0, 0.0, q=1.0, w_neg=0.9, surplus=0.3, commute_km=2.0)
    handle_close_vacancy({"time": 40.0, "agent_id": None, "event_type": "close_vacancy",
                          "params": {"job_id": nytt}}, w)
    start = [e for e in w._pushed if e["event_type"] == "start_job"][0]
    handle_start_job(start, w)
    t_start = float(start["time"])
    nst = float(w.individuals.at[0, "next_search_time"])
    assert nst >= t_start + ramp, "rampen ska gälla vid varje tillträde"

    # Den gamla händelsen (due=50) fyrar nu -- och ska kastas
    w._pushed.clear()
    handle_start_job_search({"time": 50.0 + t_start, "agent_id": 0,
                             "event_type": "start_job_search", "params": {"due": 50.0}}, w)
    assert not _search_events(w), "en ersatt sökhändelse får inte schemalägga något"

    # Utan 'due' är händelsen inte skapad av schedule_search: fel, inte tyst
    with pytest.raises(KeyError):
        handle_start_job_search({"time": nst, "agent_id": 0,
                                 "event_type": "start_job_search", "params": {}}, w)


def test_destroyed_job_logs_who_lost_it():
    """REGRESSION: förstörelsen är en JOBBhändelse, så händelsens agent_id är
    None, och raden job_destroyed_holder_displaced bar ingen person. Den som
    mister jobbet gick inte att följa i loggen: --displaced i
    individual_history.py hittade noll individer av ~990 per år."""
    from core.event_handlers import handle_destroy_job
    w = make_world(n_employers=1, size=2)
    w.individuals = pd.DataFrame([{
        "individual_id": "2062_i000000", "status": "employed", "job_id": None,
        "w_res": 1.0, "chi": 0.3, "xi": 0.2, "r_i": 0.1, "x_occ": 0.1, "y_occ": 0.1,
        "next_search_time": np.nan, "propensity_start_education": 0.0,
    }])
    w.prepare()
    jid = w.jobs.at[0, "job_id"]
    w.jobs.at[0, "individual_id"] = "2062_i000000"
    w.individuals.at[0, "job_id"] = jid
    w.set_job_filled(jid, True)
    w.event_logger.events = []
    handle_destroy_job({"time": 500.0, "agent_id": None, "event_type": "destroy_job",
                        "params": {"job_id": jid}}, w)
    rader = [extra for _, extra in w.event_logger.events
             if extra.get("event_detail") == "job_destroyed_holder_displaced"]
    assert len(rader) == 1
    assert rader[0].get("agent_id") == 0


def test_a_stale_offer_is_declined_and_the_runner_up_gets_the_job():
    """REGRESSION: buden utvärderades vid ansökan och band i 40 dagar plus
    uppsägningstid. Den arbetslösa som vann två vakanser tillträdde båda --
    _behörig fångar bara den som sagt upp sig, och uppsägning skrivs bara när
    hon är anställd. 23 procent av bytena var beslut fattade i ett annat
    tillstånd, 14 procent sänkte lönen (0094). Nu avslår hon, och
    arbetsgivaren går vidare till näste i q-ordning."""
    from core.event_handlers import handle_close_vacancy

    w, jid = _world_with_applicants([0.2, 0.9, 0.5])
    for i in range(3):
        w.individuals.at[i, "w_res"] = 0.7
    # Den med högst q (1) har hunnit ta ett bättre jobb: lön 1.2 slår budet 0.8
    w.individuals["w_neg"] = [np.nan, 1.2, np.nan]
    w.individuals["x"] = 0.0
    w.individuals["y"] = 0.0
    w.individuals["job_id"] = w.individuals["job_id"].astype(object)
    w.individuals.at[1, "status"] = "employed"
    w.individuals.at[1, "job_id"] = w.jobs.iloc[1]["job_id"]
    w._pushed.clear()
    w.event_logger.events = []
    handle_close_vacancy({"time": 40.0, "agent_id": None, "event_type": "close_vacancy",
                          "params": {"job_id": jid}}, w)

    avslag = [e for _, e in w.event_logger.events if e.get("event_detail") == "offer_declined"]
    assert len(avslag) == 1 and avslag[0]["agent_id"] == 1
    starter = [e for e in w._pushed if e["event_type"] == "start_job"]
    assert len(starter) == 1
    assert starter[0]["agent_id"] == 2, "näste i q-ordning ska få jobbet"


def test_when_everyone_declines_the_vacancy_stays_unfilled():
    """Ingen tvingas, och positionen tillsätts inte: raden säger all_declined
    så att kanalen går att räkna i analysen."""
    from core.event_handlers import handle_close_vacancy

    w, jid = _world_with_applicants([0.2, 0.9, 0.5])
    for i in range(3):
        w.individuals.at[i, "w_res"] = 1.0        # budet 0.8 räcker inte för någon
    w._pushed.clear()
    w.event_logger.events = []
    handle_close_vacancy({"time": 40.0, "agent_id": None, "event_type": "close_vacancy",
                          "params": {"job_id": jid}}, w)

    assert len([e for _, e in w.event_logger.events
                if e.get("event_detail") == "offer_declined"]) == 3
    ofylld = [e for _, e in w.event_logger.events
              if e.get("event_detail") == "vacancy_closed_unfilled"]
    assert len(ofylld) == 1 and ofylld[0].get("all_declined") is True
    assert [e for e in w._pushed if e["event_type"] == "start_job"] == []
