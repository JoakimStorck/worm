"""Geometrin: avstånd, kärnbredd, sampler, kapabilitetsdynamik."""
import numpy as np
import pandas as pd
import pytest

from core.occupations.utils import (
    _occ_distance, _occ_prob, apply_capability_update,
    sample_centers_xy_jitter,
)


def test_distance_is_euclidean():
    """Avståndet ska vara euklidiskt i (x_occ, y_occ) -- inte sqrt(dchi^2+dxi^2),
    som förvrängde vinkelavstånd nära origo."""
    i = pd.DataFrame({"x_occ": [0.0, 0.3], "y_occ": [0.0, 0.4]})
    j = pd.DataFrame({"x_occ": [3.0, 0.0], "y_occ": [4.0, 0.0]})
    d = _occ_distance(i, j)
    assert d[0, 0] == pytest.approx(5.0)
    assert d[1, 1] == pytest.approx(0.5)


def test_distance_symmetric_in_angle_near_origin():
    """Två punkter lika långt från origo men i motsatt riktning ska ligga
    2*chi isär oavsett var på cirkeln de sitter."""
    for base in (0.0, 1.0, 2.5):
        chi = 0.2
        i = pd.DataFrame({"x_occ": [chi * np.cos(base)], "y_occ": [chi * np.sin(base)]})
        j = pd.DataFrame({"x_occ": [chi * np.cos(base + np.pi)],
                          "y_occ": [chi * np.sin(base + np.pi)]})
        assert _occ_distance(i, j)[0, 0] == pytest.approx(2 * chi)


def test_kernel_width_uses_job_radius():
    """Bredden ska sitta på yrkets r_o. Större r_o -> högre matchsannolikhet
    på samma avstånd."""
    i = pd.DataFrame({"x_occ": [0.0], "y_occ": [0.0], "r_i": [0.0]})
    j = pd.DataFrame({"x_occ": [0.3, 0.3], "y_occ": [0.0, 0.0], "r_o": [0.15, 0.45]})
    d = _occ_distance(i, j)
    p = _occ_prob(i, j, d)
    assert p[0, 1] > p[0, 0]


def test_experience_radius_widens_kernel():
    """r_i > 0 ska bredda kärnan (arbetartolerans faltad med yrkesräckvidd)."""
    j = pd.DataFrame({"x_occ": [0.4], "y_occ": [0.0], "r_o": [0.25]})
    narrow = pd.DataFrame({"x_occ": [0.0], "y_occ": [0.0], "r_i": [0.0]})
    broad = pd.DataFrame({"x_occ": [0.0], "y_occ": [0.0], "r_i": [0.4]})
    p_n = _occ_prob(narrow, j, _occ_distance(narrow, j))
    p_b = _occ_prob(broad, j, _occ_distance(broad, j))
    assert p_b[0, 0] > p_n[0, 0]


def test_sigma_gamma_sharpens():
    i = pd.DataFrame({"x_occ": [0.0], "y_occ": [0.0], "r_i": [0.0]})
    j = pd.DataFrame({"x_occ": [0.3], "y_occ": [0.0], "r_o": [0.27]})
    d = _occ_distance(i, j)
    assert _occ_prob(i, j, d, sigma_gamma=0.5)[0, 0] < _occ_prob(i, j, d, sigma_gamma=1.0)[0, 0]


def test_sampler_stays_in_unit_disc(rng):
    x0, y0 = np.array([0.9, -0.9, 0.0]), np.array([0.0, 0.0, 0.95])
    x, y = sample_centers_xy_jitter(x0, y0, np.ones(3), 2000, sigma_xy=0.3)
    assert np.hypot(x, y).max() <= 1.0 + 1e-9


class TestCapabilityUpdate:
    def test_pure_deepening_is_free(self):
        chi, xi, r_i, x, y = apply_capability_update(0.5, 0.0, 0.0,
                                                     delta_chi=0.1, switch_cost_kappa=0.05)
        assert chi == pytest.approx(0.6)

    def test_reorientation_costs_depth(self):
        chi, *_ = apply_capability_update(0.5, 0.0, 0.0,
                                          delta_xi=1.5, switch_cost_kappa=0.05)
        assert chi == pytest.approx(0.5 - 0.05 * 1.5)

    def test_cost_uses_shortest_angle(self):
        """Ett steg på 2pi-0.2 är i själva verket 0.2 radianer."""
        a, *_ = apply_capability_update(0.6, 0.0, 0.0, delta_xi=0.2, switch_cost_kappa=0.05)
        b, *_ = apply_capability_update(0.6, 0.0, 0.0, delta_xi=-(2 * np.pi - 0.2),
                                        switch_cost_kappa=0.05)
        assert a == pytest.approx(b)

    def test_cartesian_stays_synced(self):
        chi, xi, r_i, x, y = apply_capability_update(0.5, 0.3, 0.1, delta_xi=1.2,
                                                     delta_chi=0.05, switch_cost_kappa=0.05)
        assert x == pytest.approx(chi * np.cos(xi))
        assert y == pytest.approx(chi * np.sin(xi))

    def test_movement_widens_experience(self):
        _, _, r_still, _, _ = apply_capability_update(0.5, 0.0, 0.0)
        _, _, r_moved, _, _ = apply_capability_update(0.5, 0.0, 0.0, delta_xi=1.5)
        assert r_still == pytest.approx(0.0)
        assert r_moved > 0.0

    def test_chi_bounded(self):
        chi, *_ = apply_capability_update(0.95, 0.0, 0.0, delta_chi=1.0)
        assert chi <= 1.0
        chi, *_ = apply_capability_update(0.05, 0.0, 0.0, delta_chi=-1.0)
        assert chi >= 0.0
