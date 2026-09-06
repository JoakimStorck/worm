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
        jp, _ = search_once(ind, jbs, cand, sigma_gamma=0.875,
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
