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
    """S = p*w - c*km - w_res, komponent för komponent."""
    i = individuals.iloc[[0]]
    j = jobs.iloc[[0]]
    S = compute_surplus_matrix(i, j, sigma_gamma=1.0, commute_cost_per_km=0.01)[0, 0]
    d = np.hypot(i["x_occ"].iloc[0] - j["x_occ"].iloc[0],
                 i["y_occ"].iloc[0] - j["y_occ"].iloc[0])
    sigma2 = j["r_o"].iloc[0] ** 2 + i["r_i"].iloc[0] ** 2
    p = np.exp(-0.5 * d ** 2 / sigma2)
    km = np.hypot(i["x"].iloc[0] - j["x"].iloc[0], i["y"].iloc[0] - j["y"].iloc[0]) / 1000.0
    assert S == pytest.approx(p * j["wage"].iloc[0] - 0.01 * km - i["w_res"].iloc[0])


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
