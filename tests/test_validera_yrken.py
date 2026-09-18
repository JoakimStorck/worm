"""Valideringens räknefunktioner (scripts/validera_yrken_per_kommun.py)."""
import importlib.util
import os

import numpy as np
import pandas as pd
import pytest

_spec = importlib.util.spec_from_file_location(
    "validera", os.path.join(os.path.dirname(__file__), "..", "scripts",
                             "validera_yrken_per_kommun.py"))
v = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v)


def test_forvantad_ar_branschmixen_gånger_rikets_yrken():
    p = pd.DataFrame({"532": [0.8, 0.0], "723": [0.2, 1.0]}, index=["Q", "G"])
    f = v.forvantad(pd.Series({"Q": 0.25, "G": 0.75}), p)
    assert f.to_dict() == pytest.approx({"532": 0.2, "723": 0.8})
    with pytest.raises(ValueError, match="X"):
        v.forvantad(pd.Series({"X": 1.0}), p)


def test_overlapp_och_brusgolv():
    a = pd.Series({"1": 0.5, "2": 0.5})
    assert v.overlapp(a, pd.Series({"2": 0.5, "3": 0.5})) == pytest.approx(0.5)
    assert v.overlapp(a, a) == pytest.approx(1.0)
    q = pd.Series(np.full(100, 0.01), index=[str(i) for i in range(100)])
    rng = np.random.default_rng(0)
    # ett litet urval ur en platt fördelning ligger långt från den, ett stort nära
    assert v.brusgolv(q, 50, rng) < 0.5 < 0.9 < v.brusgolv(q, 100000, rng)
