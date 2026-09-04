"""Prisfältet Pi(r) -- form och struktur enligt Technology fields."""
import numpy as np
import pytest

from core.occupations.price_field import PriceField

# Koefficienter, spec S1_field
PF = PriceField(m0=3.4194807, m1=0.1920737, m2=0.0888571,
                m3=-0.0646767, m4=0.0081559, m5=0.8912501)


def test_log_pi_is_the_stated_form():
    xi, chi = 0.7, 0.4
    expected = (PF.m0 + PF.m1 * np.cos(xi) + PF.m2 * np.sin(xi)
                + chi * (PF.m3 + PF.m4 * np.cos(xi) + PF.m5 * np.sin(xi)))
    assert PF.log_pi(xi, chi) == pytest.approx(expected)


def test_depth_pays_in_the_north():
    """m5 dominerar: djup betalar sig analytiskt (norr), inte fysiskt-manuellt."""
    assert PF.beta_chi(np.pi / 2) > 0.5      # norr
    assert PF.beta_chi(np.pi) < 0.1          # väster


def test_deepening_north_raises_wage():
    assert PF.pi(np.pi / 2, 0.8) > PF.pi(np.pi / 2, 0.2)


def test_cartesian_matches_polar():
    xi, chi = 1.1, 0.6
    assert PF.pi_rel_cart(chi * np.cos(xi), chi * np.sin(xi)) == pytest.approx(PF.pi_rel(xi, chi))


def test_normalisation_is_relative():
    pf = PF.with_norm(30.0)
    assert pf.pi_rel(0.5, 0.3) == pytest.approx(pf.pi(0.5, 0.3) / 30.0)
    assert PF.pi_rel(0.5, 0.3) == pytest.approx(PF.pi(0.5, 0.3))   # norm=1 default


def test_vectorised():
    xi = np.linspace(0, 2 * np.pi, 7)
    chi = np.linspace(0, 1, 7)
    out = PF.pi(xi, chi)
    assert out.shape == (7,) and np.all(np.isfinite(out))
