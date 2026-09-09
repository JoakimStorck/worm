"""Matchning som överskott, samt att parametrar når kärnan."""
import numpy as np
import pandas as pd
import pytest

import core.matching as M
import core.occupations.utils as U
from core.occupations.utils import (
    compute_surplus_matrix, global_greedy_matching, effective_wage,
)


def test_all_matches_have_positive_surplus(individuals, jobs):
    res = global_greedy_matching(individuals, jobs, sigma_gamma=0.6,
                                 commute_cost_per_km=0.005, min_surplus=0.0)
    assert len(res) > 0
    assert (res["surplus"] > 0).all()


def test_no_double_assignment(individuals, jobs):
    res = global_greedy_matching(individuals, jobs, sigma_gamma=0.6)
    assert res["individual_id"].is_unique
    assert res["job_id"].is_unique


def test_higher_reservation_wage_reduces_matches(individuals, jobs):
    low = individuals.assign(w_res=0.1)
    high = individuals.assign(w_res=0.9)
    assert len(global_greedy_matching(low, jobs, sigma_gamma=0.6)) > \
           len(global_greedy_matching(high, jobs, sigma_gamma=0.6))


def test_commute_cost_reduces_matches(individuals, jobs):
    cheap = global_greedy_matching(individuals, jobs, sigma_gamma=0.6,
                                   commute_cost_per_km=0.001)
    dear = global_greedy_matching(individuals, jobs, sigma_gamma=0.6,
                                  commute_cost_per_km=0.05)
    assert len(cheap) > len(dear)


def test_surplus_formula(individuals, jobs):
    """S = w_j - c*km - w_res. Lönen är jobbets, oberoende av passform."""
    i = individuals.iloc[[0]]
    j = jobs.iloc[[0]]
    S = compute_surplus_matrix(i, j, commute_cost_per_km=0.01)[0, 0]
    km = np.hypot(i["x"].iloc[0] - j["x"].iloc[0], i["y"].iloc[0] - j["y"].iloc[0]) / 1000.0
    assert S == pytest.approx(j["wage"].iloc[0] - 0.01 * km - i["w_res"].iloc[0])


def test_surplus_independent_of_task_distance(individuals, jobs):
    """Passformen får inte påverka LÖNEN, bara sannolikheten att bli anställd."""
    from core.occupations.utils import hire_probability
    near = individuals.iloc[[0]].assign(x_occ=jobs["x_occ"].iloc[0],
                                        y_occ=jobs["y_occ"].iloc[0])
    far = individuals.iloc[[0]].assign(x_occ=jobs["x_occ"].iloc[0] + 0.6,
                                       y_occ=jobs["y_occ"].iloc[0])
    j = jobs.iloc[[0]]
    assert compute_surplus_matrix(near, j)[0, 0] == pytest.approx(
        compute_surplus_matrix(far, j)[0, 0])
    assert hire_probability(near, j)[0, 0] > hire_probability(far, j)[0, 0]


def test_transition_distances_match_empirical_distribution():
    """Modellens mobilitetsfördelning ska motsvara den observerade:
    median 1.03 task-radier, ~50 % inom en radie, svans bortom två.
    Referens: Two scales of occupational mobility, CPS 2020-2024."""
    rng = np.random.default_rng(7)

    def disc(n):
        r = np.sqrt(rng.uniform(0, 1, n)); t = rng.uniform(0, 2 * np.pi, n)
        return r * np.cos(t), r * np.sin(t)

    N, M = 3000, 9000
    ix, iy = disc(N); jx, jy = disc(M)
    inds = pd.DataFrame({"individual_id": np.arange(N), "x_occ": ix, "y_occ": iy,
                         "r_i": 0.0, "w_res": 0.30, "x": 0.0, "y": 0.0})
    jbs = pd.DataFrame({"job_id": np.arange(M), "x_occ": jx, "y_occ": jy,
                        "r_o": 0.272, "wage": rng.uniform(0.45, 0.85, M),
                        "x": 0.0, "y": 0.0})
    res = global_greedy_matching(inds, jbs, sigma_gamma=0.875,
                                 commute_cost_per_km=0.005, rng=rng)
    im = inds.set_index("individual_id").loc[res["individual_id"]]
    jm = jbs.set_index("job_id").loc[res["job_id"]]
    uR = np.hypot(im["x_occ"].values - jm["x_occ"].values,
                  im["y_occ"].values - jm["y_occ"].values) / jm["r_o"].values

    assert np.median(uR) == pytest.approx(1.03, abs=0.20)
    assert 0.40 < (uR <= 1.0).mean() < 0.62
    assert (uR > 2.0).mean() > 0.02, "svansen saknas: långa övergångar uteslutna"


def test_works_without_prices(individuals, jobs):
    """Saknas wage/w_res ska S = p - c*km (bakåtkompatibelt)."""
    res = global_greedy_matching(individuals.drop(columns=["w_res"]),
                                 jobs.drop(columns=["wage"]), sigma_gamma=0.6)
    assert len(res) > 0


def test_effective_wage_at_centre_equals_job_wage():
    ind = pd.Series({"x_occ": 0.3, "y_occ": 0.2, "r_i": 0.0})
    job = pd.Series({"x_occ": 0.3, "y_occ": 0.2, "r_o": 0.25, "wage": 1.4})
    assert effective_wage(ind, job) == pytest.approx(1.4)


@pytest.mark.parametrize("fn_name", ["multilevel_exhaustive_matching",
                                     "interleaved_multilevel_batch_matching"])
def test_parameters_reach_the_kernel(monkeypatch, individuals, jobs, fn_name):
    """Regressionstest: sigma_gamma/commute_cost/min_surplus försvann tidigare
    i **kwargs och den händelsedrivna matchningen körde på defaultvärden."""
    seen = []
    orig = U.global_greedy_matching

    def spy(i, j, alpha_chi=5.0, alpha_xi=5.0, alpha_geo=1.0, sigma_gamma=1.0,
            utility_min=None, commute_cost_per_km=0.005, min_surplus=0.0):
        seen.append((sigma_gamma, commute_cost_per_km, min_surplus))
        return orig(i, j, sigma_gamma=sigma_gamma,
                    commute_cost_per_km=commute_cost_per_km, min_surplus=min_surplus)

    monkeypatch.setattr(M, "global_greedy_matching", spy)
    getattr(M, fn_name)(individuals, jobs, sigma_gamma=0.61,
                        commute_cost_per_km=0.0077, min_surplus=0.013)
    assert seen, "kärnan anropades aldrig"
    assert seen[0] == (0.61, 0.0077, 0.013)


def test_missing_prices_is_detectable(individuals, jobs):
    """REGRESSION: prisfältet kunde saknas helt utan att någon märkte det.
    Jobben fick lön 1.0, ingen fick reservationslön, och överskottet blev
    S = p - c*km -- vilket gav 98 % fyllnadsgrad och median 0.955."""
    flat = jobs.assign(wage=1.0)
    no_res = individuals.assign(w_res=0.0)
    res_flat = global_greedy_matching(no_res, flat, sigma_gamma=0.6)
    res_real = global_greedy_matching(individuals, jobs, sigma_gamma=0.6)
    assert len(res_flat) > len(res_real)
    assert res_flat["surplus"].median() > res_real["surplus"].median()


def test_reservation_wage_decays_on_failed_search():
    """Utan avtagande reservationslön ligger kravet kvar på 0.7 av senaste lön
    hur länge arbetslösheten än varar, och marknaden klarerar aldrig: i en
    körning var 97 % av de arbetslösa blockerade och träffkvoten 5.4 %."""
    from conftest import FakeConfig, FakeQueue, FakeLogger
    from core.event_handlers import handle_start_job_search

    class W:
        pass
    w = W()
    w.cfg_reader = FakeConfig({"reservation_decay_per_search": 0.9,
                               "reservation_floor": 0.2, "min_surplus": 0.0})
    w.event_queue = FakeQueue()
    w.event_logger = FakeLogger()
    w.n_matched_in_month = 0
    w._push_event = lambda e: w.event_queue.push(e)
    w.individuals = pd.DataFrame([{"individual_id": "i0", "status": "unemployed",
                                   "w_res": 1.0, "propensity_start_education": 0.0,
                                   "x_occ": 0.3, "y_occ": 0.1, "r_i": 0.0,
                                   "x": 0.0, "y": 0.0}])
    # Inga lediga positioner: varje sökning misslyckas
    w.jobs = pd.DataFrame({"job_id": ["J0"], "individual_id": ["i1"], "active": [True],
                           "x_occ": [0.3], "y_occ": [0.1], "r_o": [0.27],
                           "wage": [1.0], "x": [0.0], "y": [0.0]})
    from core.occupations.utils import build_job_arrays
    w.job_arrays = lambda: build_job_arrays(w.jobs)
    w.vacant_mask = lambda: np.zeros(len(w.jobs), dtype=bool)   # inga lediga

    for _ in range(3):
        handle_start_job_search({"time": 1.0, "agent_id": 0,
                                 "event_type": "start_job_search", "params": {}}, w)
    assert w.individuals.at[0, "w_res"] == pytest.approx(0.729)     # 0.9^3

    for _ in range(30):
        handle_start_job_search({"time": 1.0, "agent_id": 0,
                                 "event_type": "start_job_search", "params": {}}, w)
    assert w.individuals.at[0, "w_res"] == pytest.approx(0.2)       # golvet håller


def test_missing_event_timings_get_defaults():
    """REGRESSION: falun_baseline.yml saknar event_timings helt, vilket gav
    KeyError: 'dist' i _init_events. Varje händelsetyp ska få ett giltigt
    default, och scenariots egna värden ska gå före."""
    from core.configreader import ConfigReader

    cfg = ConfigReader({"simulation": {}}, None)
    for ev in ("quit_job", "start_job_search", "start_education",
               "end_education", "start_internal_training",
               "internal_job_change", "career_break"):
        assert "dist" in cfg.get_event_timing(ev), ev

    own = ConfigReader({"simulation": {"event_timings": {
        "quit_job": {"dist": "normal", "mean": "2y", "std": "1y"}}}}, None)
    t = own.get_event_timing("quit_job")
    assert t["mean"] == pytest.approx(730.5)

    assert ConfigReader({"simulation": {}}, None).get_event_timing("okänd") == {}


def test_extends_merges_shared_simulation_config(tmp_path):
    """Scenarier delar simulation-block via 'extends', så att en jämförelse
    mellan kommuner mäter kommunskillnader och inte parameterskillnader.
    falun_baseline och kluster_fbr saknade tidigare event_timings respektive
    hela simulation-blocket, vilket gav KeyError mitt i en körning."""
    import yaml
    from core.configreader import ConfigReader

    (tmp_path / "base.yml").write_text(yaml.safe_dump({
        "simulation": {"sigma_gamma": 0.875, "job_flows": True,
                       "event_timings": {"quit_job": {"dist": "normal"}}}}),
        encoding="utf-8")
    (tmp_path / "kommun.yml").write_text(yaml.safe_dump({
        "extends": "base.yml", "scenario_name": "X",
        "simulation": {"sigma_gamma": 0.7}}), encoding="utf-8")

    d = ConfigReader.resolve_extends(
        yaml.safe_load((tmp_path / "kommun.yml").read_text(encoding="utf-8")), str(tmp_path))
    sim = d["simulation"]
    assert sim["sigma_gamma"] == 0.7          # egen nyckel vinner
    assert sim["job_flows"] is True           # ärvd
    assert sim["event_timings"]["quit_job"]["dist"] == "normal"   # djup merge
    assert "extends" not in d


def test_real_scenarios_are_complete():
    """Alla scenarier i repot ska ha fullständig simulation-konfiguration."""
    import glob
    import os
    import yaml
    from core.configreader import ConfigReader

    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scenarios")
    for path in glob.glob(os.path.join(root, "*.yml")):
        if os.path.basename(path).startswith("_"):
            continue
        d = ConfigReader.resolve_extends(
            yaml.safe_load(open(path, encoding="utf-8")), root)
        sim = d.get("simulation", {})
        name = os.path.basename(path)
        assert sim.get("event_timings"), f"{name} saknar event_timings"
        assert sim.get("event_effects"), f"{name} saknar event_effects"
        assert sim.get("sigma_gamma"), f"{name} saknar sigma_gamma"


def test_vacant_job_indices_excludes_filled_and_destroyed():
    from core.occupations.utils import vacant_job_indices
    jbs = pd.DataFrame({"individual_id": [np.nan, "i1", np.nan, np.nan],
                        "active": [True, True, False, True]})
    assert list(vacant_job_indices(jbs)) == [0, 3]


def _search_market(n_jobs, seed=0, **kw):
    """Syntetisk marknad; returnerar (träffkvot, u_R-lista, km-lista)."""
    from core.occupations.utils import search_once, vacant_job_indices, build_job_arrays
    rng = np.random.default_rng(seed)
    jbs = pd.DataFrame({
        "job_id": np.arange(n_jobs),
        "x_occ": rng.uniform(-0.9, 0.9, n_jobs), "y_occ": rng.uniform(-0.9, 0.9, n_jobs),
        "r_o": 0.272, "wage": rng.uniform(0.45, 0.85, n_jobs),
        "x": rng.uniform(0, 3e4, n_jobs), "y": rng.uniform(0, 3e4, n_jobs),
        "individual_id": np.nan, "active": True})
    A = build_job_arrays(jbs)
    cand = vacant_job_indices(jbs)
    ind = pd.Series({"x_occ": 0.3, "y_occ": 0.1, "r_i": 0.0,
                     "x": 15000.0, "y": 15000.0, "w_res": kw.pop("w_res", 0.40)})
    uR, km, hits, N = [], [], 0, 600
    for _ in range(N):
        jp, _, _, _, _ = search_once(ind, jbs, cand, sigma_gamma=0.875,
                            commute_cost_per_km=0.005, rng=rng, arrays=A, **kw)
        if jp is not None:
            hits += 1
            uR.append(np.hypot(A["x_occ"][jp] - 0.3, A["y_occ"][jp] - 0.1) / A["r_o"][jp])
            km.append(np.hypot(A["x"][jp] - 15000.0, A["y"][jp] - 15000.0) / 1000.0)
    return hits / N, np.array(uR), np.array(km)


def test_search_reproduces_empirical_transition_distances():
    """Relevansmängden får inte bryta kalibreringen: bara p beror på avståndet
    i planet, så realiserade övergångar ska förbli Rayleigh-fördelade med
    median nära 1.03 task-radier."""
    _, uR, _ = _search_market(4000, choice_scale=0.05)
    assert np.median(uR) == pytest.approx(1.03, abs=0.20)
    assert (uR > 2.0).mean() > 0.02, "svansen saknas"


def test_choice_scale_governs_commuting():
    """Låg skala: bara verkligt likvärdiga jobb uppfattas som utbytbara, så
    den sökande tar det nära. Hög skala: mer uppfattas som likvärdigt och
    pendlingen ökar."""
    _, _, km_tight = _search_market(4000, choice_scale=0.01)
    _, _, km_loose = _search_market(4000, choice_scale=0.30)
    assert np.median(km_tight) < np.median(km_loose)


def test_thicker_market_gives_more_options():
    """Relevansmängden är inte begränsad till ett fast antal, så en tunn
    marknad ska ge lägre träffkvot än en tät.

    Effekten syns bara när acceptanskravet binder. Med låg reservationslön
    matchar alla oavsett marknadsstorlek, eftersom det alltid finns
    tillräckligt många godtagbara alternativ. w_res 0.78 mot löner i
    intervallet 0.45-0.85 ger en snäv marginal, vilket är det läge där
    tunnhet gör skillnad.
    """
    hit_thin, _, _ = _search_market(100, seed=5, choice_scale=0.05, w_res=0.78)
    hit_thick, _, _ = _search_market(1000, seed=5, choice_scale=0.05, w_res=0.78)
    assert hit_thin < hit_thick, f"{hit_thin:.2f} mot {hit_thick:.2f}"


def _edu_world(job_positions, wages=None):
    """Liten värld där vakanserna ligger på angivna punkter i planet."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from conftest import make_world

    n = len(job_positions)
    w = make_world(n_employers=n, size=1)
    for i, (x, y) in enumerate(job_positions):
        w.jobs.loc[w.jobs.index[i], ["x_occ", "y_occ"]] = [x, y]
        if wages is not None:
            w.jobs.loc[w.jobs.index[i], "wage"] = wages[i]
    w.jobs["individual_id"] = np.nan
    w._vm_n = None                       # tvinga ombyggnad av masken
    w._ja_n = None
    return w


def _edu_individual():
    return pd.DataFrame([{
        "individual_id": "i0", "status": "unemployed", "job_id": None,
        "w_res": 0.2, "chi": 0.5, "xi": np.pi, "r_i": 0.0,
        "x_occ": -0.5, "y_occ": 0.0, "x": 0.0, "y": 0.0,
        "onet_code": "11-1011.00", "r_o_home": 0.27, "tenure_years": 5.0,
        "education_level": 3, "municipal_code": "2062",
        "propensity_start_education": 0.0,
        "propensity_internal_training": 0.0, "propensity_quit_job": 0.0,
        "propensity_internal_job_change": 0.0}]).astype({"job_id": object})


def test_retraining_target_points_at_the_jobs():
    """Riktningen ska bestämmas av var arbete finns, inte av ett fast delta."""
    from core.occupations.utils import retraining_target, build_job_arrays, vacant_job_indices

    w = _edu_world([(0.6, 0.0), (0.62, 0.05), (0.58, -0.03)])
    ind = pd.Series({"x_occ": -0.5, "y_occ": 0.0, "x": 0.0, "y": 0.0})
    tx, ty = retraining_target(ind, w.jobs, vacant_job_indices(w.jobs),
                               arrays=build_job_arrays(w.jobs))
    assert tx == pytest.approx(0.60, abs=0.05)
    assert abs(ty) < 0.05


def test_retraining_target_is_none_without_viable_jobs():
    """Finns inget som lönar sig sker ingen omskolning. Det är det väntade
    utfallet i en tunn marknad och ska inte tvinga fram en slumpvandring."""
    from core.occupations.utils import retraining_target, build_job_arrays, vacant_job_indices

    w = _edu_world([(0.6, 0.0)], wages=[0.0])
    ind = pd.Series({"x_occ": -0.5, "y_occ": 0.0, "x": 0.0, "y": 0.0})
    assert retraining_target(ind, w.jobs, vacant_job_indices(w.jobs),
                             arrays=build_job_arrays(w.jobs),
                             min_surplus=0.1) is None


def test_education_updates_capability_at_the_end_not_the_start():
    """Effekten ska komma av att fullfölja, inte av att skriva in sig."""
    from core.event_handlers import handle_start_education, handle_end_education

    w = _edu_world([(0.6, 0.0), (0.62, 0.05)])
    w.individuals = _edu_individual()
    w.init_competence()
    x0 = float(w.individuals.at[0, "x_occ"])       # sammanfattningen efter init

    handle_start_education({"time": 0.0, "agent_id": 0,
                            "event_type": "start_education", "params": {}}, w)
    assert w.individuals.at[0, "status"] == "in_education"
    assert w.individuals.at[0, "x_occ"] == pytest.approx(x0), "flyttades vid inskrivning"

    ev = w.event_queue.pop()
    assert ev["event_type"] == "end_education"
    handle_end_education(ev, w)

    assert w.individuals.at[0, "status"] == "unemployed"
    assert w.individuals.at[0, "x_occ"] > x0, "flyttades inte vid slutet"
    names = {w.circles.key_names[k] for k in w.circles.key[0] if k >= 0}
    assert any(n.startswith("RETRAIN") for n in names), "ingen omskolningscirkel"


def test_thin_market_gives_longer_retraining():
    """Varaktigheten följer förflyttningen, så omskolning tar längre tid när
    målet ligger långt bort. Det är tunnhetsmekanismen: i en gles kommun finns
    inget nära att rikta sig mot."""
    from core.event_handlers import handle_start_education

    def duration(job_x):
        w = _edu_world([(job_x, 0.0), (job_x, 0.05)])
        w.individuals = _edu_individual()
        w.init_competence()
        handle_start_education({"time": 0.0, "agent_id": 0,
                                "event_type": "start_education", "params": {}}, w)
        return w.event_queue.pop()["time"]

    assert duration(0.7) > duration(-0.2), "avlägset mål gav inte längre omskolning"


def test_start_job_uses_negotiated_wage_as_reservation():
    """REGRESSION: förhandlingen påverkade valet men inte lönen efter
    anställning -- reservationslönen sattes till effective_wage, alltså
    fältlönen. Följden var att w_field och w_neg aldrig loggades och att
    lönespridningen inte gick att mäta."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from conftest import make_world
    from core.event_handlers import handle_start_job

    w = make_world(n_employers=3, size=2)
    w.individuals = pd.DataFrame([{
        "individual_id": "i0", "status": "unemployed", "job_id": None,
        "w_res": 0.30, "w_neg": np.nan, "chi": 0.3, "xi": 0.3, "r_i": 0.0,
        "x_occ": 0.3, "y_occ": 0.1, "x": 0.0, "y": 0.0,
        "onet_code": "A", "last_onet_code": "A", "r_o_home": 0.27,
        "tenure_years": 3.0, "education_level": 3, "municipal_code": "2062",
        "propensity_start_education": 0.0, "propensity_internal_training": 0.0,
        "propensity_quit_job": 0.0, "propensity_internal_job_change": 0.0,
    }]).astype({"job_id": object})
    w.init_competence()
    w.jobs.loc[w.jobs.index[2], "wage"] = 1.20
    jid = w.jobs.at[2, "job_id"]

    try:
        handle_start_job({"time": 1.0, "agent_id": 0, "event_type": "start_job",
                          "params": {"job_id": jid, "w_neg": 0.72, "q_hire": 0.9}}, w)
    except KeyError:
        pass
    logged = [e[1] for e in w.event_logger.events if e[0] == "start_job"][-1]
    assert logged["w_field"] == pytest.approx(1.20)
    assert logged["w_neg"] == pytest.approx(0.72)
    assert w.individuals.at[0, "w_res"] == pytest.approx(0.72), "fältlön i stället för förhandlad"



# ---------------------------------------------------------------------------
# Förhandlad lön: förankrad i fältet, golv som fallback
# ---------------------------------------------------------------------------
def test_reference_worker_earns_exactly_the_field_wage():
    """ANKARET. Prisfältet är den observerade genomsnittslönen. Referens-
    arbetaren -- fullt produktiv, med reservationslön lika med yrkets egen
    lön -- måste få exakt Pi, annars är Pi inte vad vi säger att det är."""
    from core.occupations.utils import negotiated_wage
    for Pi in (0.5, 1.0, 1.8):
        w = float(negotiated_wage(1.0, Pi, Pi, beta=0.5, wage_floor_share=0.7))
        assert w == pytest.approx(Pi)


def test_wage_converges_to_productivity_times_field():
    """I jämvikt, när reservationslönen är den egna lönen, konvergerar w mot
    p*Pi. Full produktivitet ger fältlönen; sämre ger proportionellt mindre."""
    from core.occupations.utils import negotiated_wage
    Pi = 1.0
    for p in (0.75, 0.9, 1.0):
        w = 0.72                       # startvärde över golvet
        for _ in range(60):
            w = float(negotiated_wage(p, Pi, w, beta=0.5, wage_floor_share=0.7))
        assert w == pytest.approx(p * Pi, abs=1e-3)


def test_floor_is_a_fallback_not_a_clip():
    """REGRESSION: ett klipp lade 23 procent av yrkenas median exakt på golvet
    och tog bort all spridning i 19 procent. Golvet ska vara arbetarens
    fallback: utfallet ligger ÖVER det och varierar med produktiviteten."""
    from core.occupations.utils import negotiated_wage
    Pi, phi = 1.0, 0.7
    ws = [float(negotiated_wage(p, Pi, 0.30, beta=0.5, wage_floor_share=phi))
          for p in (0.72, 0.80, 0.90, 1.00)]
    assert all(w > phi * Pi for w in ws), "utfall på eller under golvet"
    assert ws == sorted(ws) and len(set(round(w, 6) for w in ws)) == 4, "ingen spridning"
    # Reservationen under golvet spelar ingen roll: fallbacken är golvet
    assert float(negotiated_wage(0.9, Pi, 0.30, beta=0.5, wage_floor_share=phi)) == \
        pytest.approx(float(negotiated_wage(0.9, Pi, 0.60, beta=0.5, wage_floor_share=phi)))


def test_wages_never_exceed_the_field_at_full_productivity():
    """REGRESSION: 37 procent av yrkena låg ÖVER fältlönen, lagerarbetare på
    1.28 gånger, eftersom en global produktionsskala inte respekterade att Pi
    är ett genomsnitt. Med p <= 1 kan lönen aldrig överstiga Pi."""
    from core.occupations.utils import negotiated_wage
    Pi = 0.6
    for p in (0.8, 1.0):
        for wres in (0.3, 0.55, 0.6):
            w = negotiated_wage(p, Pi, wres, beta=0.5, wage_floor_share=0.7)
            if not np.isnan(w):
                assert float(w) <= Pi + 1e-9


def test_employer_participation_is_the_productivity_threshold():
    """Arbetsgivaren deltar om p*Pi >= max(w_res, phi*Pi). Kombinerat med
    p = q ** (k*r) ger det en kompetenströskel som är strängare ju mer
    jobbet kräver -- utan att någon regel skrivits för det."""
    from core.occupations.utils import negotiated_wage
    from core.occupations.requirement import productivity
    Pi, phi = 1.8, 0.7
    # Kirurg, r = 0.84: grundskolegolvet q = 0.05 ger p ~ 0.007 -> ingen affär
    assert np.isnan(negotiated_wage(float(productivity(0.05, 0.84)), Pi, 0.10,
                                    wage_floor_share=phi))
    # ... och q = 0.85 räcker
    assert not np.isnan(negotiated_wage(float(productivity(0.85, 0.84)), Pi, 0.10,
                                        wage_floor_share=phi))
    # Diskare, r = 0: samma q = 0.05 ger p = 1 -> affär till fullt värde
    assert float(negotiated_wage(float(productivity(0.05, 0.0)), 0.49, 0.30,
                                 wage_floor_share=phi)) == pytest.approx(0.49 * 0.85, abs=0.01)


def test_lawyer_can_wash_dishes_but_only_if_she_wants_to(individuals, jobs):
    """Advokaten kan diska: kravet är noll, så produktiviteten är full oavsett
    hur långt bort juridiken ligger. Det enda som håller henne borta är
    reservationslönen -- trögheten -- och mötet, som q styr."""
    from core.occupations.utils import search_once, vacant_job_indices, build_job_arrays
    rng = np.random.default_rng(2)
    dish = pd.DataFrame({"job_id": [0], "x_occ": [-0.45], "y_occ": [-0.30], "r_o": [0.27],
                         "wage": [0.49], "r_req": [0.0], "x": [0.0], "y": [0.0],
                         "individual_id": [np.nan], "active": [True]})
    A = build_job_arrays(dish); cand = vacant_job_indices(dish)
    q_far = lambda jx, jy, jro: np.array([0.30])
    picky = pd.Series({"x_occ": 0.39, "y_occ": 0.03, "r_i": 0.0, "x": 0.0, "y": 0.0, "w_res": 1.1})
    willing = picky.copy(); willing["w_res"] = 0.30
    def hired(ind):
        return sum(1 for _ in range(300)
                   if search_once(ind, dish, cand, sigma_gamma=0.875, rng=rng, arrays=A,
                                  competitiveness=q_far, requirement_k=2.0,
                                  bargaining={"beta": 0.5, "wage_floor_share": 0.7})[0]
                   is not None)
    assert hired(picky) == 0
    n = hired(willing)
    assert 40 < n < 140, f"möten med q = 0.3 bör lyckas i ~30 % av fallen, fick {n}/300"


def test_unqualified_never_becomes_surgeon():
    from core.occupations.utils import search_once, vacant_job_indices, build_job_arrays
    rng = np.random.default_rng(3)
    surg = pd.DataFrame({"job_id": [0], "x_occ": [0.42], "y_occ": [0.03], "r_o": [0.27],
                         "wage": [1.8], "r_req": [0.84], "x": [0.0], "y": [0.0],
                         "individual_id": [np.nan], "active": [True]})
    A = build_job_arrays(surg); cand = vacant_job_indices(surg)
    ind = pd.Series({"x_occ": -0.4, "y_occ": -0.3, "r_i": 0.0, "x": 0.0, "y": 0.0, "w_res": 0.10})
    n = sum(1 for _ in range(300)
            if search_once(ind, surg, cand, sigma_gamma=0.875, rng=rng, arrays=A,
                           competitiveness=lambda jx, jy, jro: np.array([0.30]),
                           requirement_k=2.0,
                           bargaining={"beta": 0.5, "wage_floor_share": 0.7})[0] is not None)
    assert n == 0


def test_meeting_is_governed_by_fit_not_productivity(individuals, jobs):
    """REGRESSION: att låta produktiviteten styra mötet tog bort lokaliteten
    för alla jobb med lågt krav -- halva marknaden -- och gav median u_R 1.20
    mot 0.70. q styr mötet, p styr värdet."""
    from core.occupations.utils import search_once, vacant_job_indices, build_job_arrays
    rng = np.random.default_rng(4)
    n = 400
    x = rng.uniform(-0.9, 0.9, n); y = rng.uniform(-0.9, 0.9, n)
    jbs = pd.DataFrame({"job_id": np.arange(n), "x_occ": x, "y_occ": y, "r_o": 0.272,
                        "wage": 0.7, "r_req": 0.0,                   # inga krav alls
                        "x": 0.0, "y": 0.0, "individual_id": np.nan, "active": True})
    A = build_job_arrays(jbs); cand = vacant_job_indices(jbs)
    ind = pd.Series({"x_occ": 0.3, "y_occ": 0.1, "r_i": 0.0, "x": 0.0, "y": 0.0, "w_res": 0.30})
    d_hits = []
    for _ in range(400):
        pos, *_ = search_once(ind, jbs, cand, sigma_gamma=0.875, rng=rng, arrays=A,
                              requirement_k=2.0,
                              bargaining={"beta": 0.5, "wage_floor_share": 0.7})
        if pos is not None:
            d_hits.append(np.hypot(x[pos] - 0.3, y[pos] - 0.1) / 0.272)
    assert len(d_hits) > 100
    assert np.median(d_hits) < 1.3, f"lokaliteten försvann: median u_R {np.median(d_hits):.2f}"


# ---------------------------------------------------------------------------
# Taket bort i värderollen (0060)
# ---------------------------------------------------------------------------

def test_uncapped_fit_lets_the_wage_exceed_the_field():
    """REGRESSION: med q kapat vid 1 var p <= 1, alltså w <= Pi för alla, för
    alltid. Pi var ett supremum ingen kunde passera -- 0.00 procent över
    fältlönen, mot hälften om Pi är yrkets median -- och 41 procent av alla
    anställningar låg på exakt 0.85 = 0.5*0.70 + 0.5*1."""
    from core.occupations.requirement import productivity
    from core.occupations.utils import negotiated_wage

    p = productivity(np.array([1.3]), np.array([0.5]), k=2.0)
    assert p[0] == pytest.approx(1.3)                  # inget klipp
    w = negotiated_wage(p, np.array([1.0]), w_res=1.0, beta=0.5,
                        wage_floor_share=0.70)
    assert w[0] > 1.0                                   # över fältlönen

    # Ankaret överlever exakt: referensarbetaren får Pi
    w_ref = negotiated_wage(np.array([1.0]), np.array([1.0]), w_res=1.0,
                            beta=0.5, wage_floor_share=0.70)
    assert w_ref[0] == pytest.approx(1.0)


def test_meeting_draw_still_treats_fit_as_a_probability():
    """Sannolikhetsrollen kapar själv: q > 1 ska ge möte med sannolikhet 1,
    inte krascha eller överskrida."""
    from core.occupations.utils import search_once, build_job_arrays

    jobs = pd.DataFrame({
        "job_id": ["A"], "x_occ": [0.3], "y_occ": [0.1], "r_o": [0.27],
        "wage": [1.0], "r_req": [0.5], "x": [0.0], "y": [0.0],
        "individual_id": [np.nan], "active": [True],
    })
    ind = pd.Series({"x_occ": 0.3, "y_occ": 0.1, "r_i": 0.0,
                     "x": 0.0, "y": 0.0, "w_res": 0.0})
    A = build_job_arrays(jobs)
    hits = sum(search_once(ind, jobs, np.arange(1), arrays=A,
                           rng=np.random.default_rng(s),
                           competitiveness=lambda jx, jy, jro: np.array([1.4]))[0] == 0
               for s in range(50))
    assert hits == 50


# ---------------------------------------------------------------------------
# Theta, löneandel och arbetsgivareffekt (0061)
# ---------------------------------------------------------------------------

def test_theta_puts_the_median_on_the_field_wage():
    """REGRESSION: den gamla formeln hade en frihetsgrad, inte två.
    Reservationen faller under golvet för alla, max() väljer alltid phi*Pi,
    och första termen är konstant 0.35. Med median p = 0.995 satt medianen
    låst vid 0.8499 -- 87.5 procent av anställningarna följde
    w/Pi = 0.35 + 0.5p på tre decimaler."""
    from core.occupations.utils import negotiated_wage

    Pi = np.array([1.0])
    gammal = dict(beta=0.5, wage_floor_share=0.70)
    ny = dict(theta=0.5, labour_share=0.65, wage_floor_share=0.70)

    # Medianarbetaren, p ~ 1, reservation under golvet
    assert negotiated_wage(np.array([1.0]), Pi, 0.4, **gammal)[0] == pytest.approx(0.85)
    assert negotiated_wage(np.array([1.0]), Pi, 0.4, **ny)[0] == pytest.approx(1.0)

    # Formen består: p under ett ger under Pi, p över ett ger över
    assert negotiated_wage(np.array([0.64]), Pi, 0.4, **ny)[0] == pytest.approx(0.8)
    assert negotiated_wage(np.array([1.44]), Pi, 0.4, **ny)[0] == pytest.approx(1.2)

    # Reservationen står inte längre i formeln: lönen beror inte på hur länge
    # hon varit arbetslös
    a = negotiated_wage(np.array([1.1]), Pi, 0.20, **ny)[0]
    b = negotiated_wage(np.array([1.1]), Pi, 0.65, **ny)[0]
    assert a == pytest.approx(b)


def test_labour_share_lets_below_median_workers_be_hired():
    """Utan lambda vore villkoret p*Pi >= Pi*p**theta, alltså p >= 1: ingen
    under medianen skulle anställas."""
    from core.occupations.utils import negotiated_wage

    Pi = np.array([1.0])
    ny = dict(theta=0.5, labour_share=0.65, wage_floor_share=0.0)
    grind = 0.65 ** (1.0 / (1.0 - 0.5))          # = 0.4225
    assert np.isfinite(negotiated_wage(np.array([grind * 1.05]), Pi, 0.0, **ny)[0])
    assert np.isnan(negotiated_wage(np.array([grind * 0.95]), Pi, 0.0, **ny)[0])
    # utan löneandel skulle grinden ligga vid p = 1
    utan = dict(theta=0.5, labour_share=1.0, wage_floor_share=0.0)
    assert np.isnan(negotiated_wage(np.array([0.9]), Pi, 0.0, **utan)[0])


def test_floor_is_a_floor_not_half_the_formula():
    from core.occupations.utils import negotiated_wage

    w = negotiated_wage(np.array([0.5]), np.array([1.0]), 0.0,
                        theta=1.0, labour_share=0.65, wage_floor_share=0.70)
    assert w[0] == pytest.approx(0.70)          # golvet biter
    w2 = negotiated_wage(np.array([0.9]), np.array([1.0]), 0.0,
                         theta=1.0, labour_share=0.65, wage_floor_share=0.70)
    assert w2[0] == pytest.approx(0.90)         # men bär inte lönen


def test_bargaining_config_reaches_the_wage_formula():
    """REGRESSION: anropet i handle_start_job_search byggde dicten med en
    VITLISTA på beta och wage_floor_share. theta och labour_share filtrerades
    bort, negotiated_wage föll tillbaka på den gamla Nash-grenen, och en hel
    körning gav identiska tal som före patchen -- minsta p vid anställning låg
    kvar på 0.700, den gamla grinden, i stället för 0.455.

    Formeln, defaultfilen och enhetstesterna var alla riktiga. Bara vägen
    däremellan var bruten, och enhetstester som anropar formeln direkt kan
    inte se det."""
    import inspect
    from core import event_handlers as eh
    from core.configreader import ConfigReader
    from core.occupations.utils import negotiated_wage
    import yaml, os

    # 1. Ingen vitlista i anropet
    src = inspect.getsource(eh.handle_start_job_search)
    assert '"beta":' not in src, "vitlista i bargaining-anropet igen"

    # 2. Scenariots block når formeln och byter gren
    d = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenarios")
    cfg = ConfigReader.resolve_extends(
        yaml.safe_load(open(os.path.join(d, "mora_baseline.yml"), encoding="utf-8")), d)
    brg = {k: v for k, v in cfg["simulation"]["bargaining"].items() if k != "enabled"}
    assert "theta" in brg and "labour_share" in brg

    Pi = np.array([1.0])
    assert negotiated_wage(np.array([1.0]), Pi, 0.4, **brg)[0] == pytest.approx(1.0)
    lam, th = brg["labour_share"], brg["theta"]
    grind = max(lam ** (1.0 / (1.0 - th)), brg["wage_floor_share"] * lam)
    assert np.isfinite(negotiated_wage(np.array([grind * 1.02]), Pi, 0.0, **brg)[0])
    assert np.isnan(negotiated_wage(np.array([grind * 0.98]), Pi, 0.0, **brg)[0])
