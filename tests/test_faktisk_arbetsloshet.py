"""Arbetslösheten per kommun ur SCB i stället för ur scenariofilen.

Sedan 0137 back-räknas arbetskraften ur unemployment_rate: L = syss / (1 - u).
Eftersom u = u_min + V/L med u_min = 1 - J/L sätter talet golvet för modellens
arbetslöshet direkt. För Ovansiljan gav platshållarna 6.5, 7.5 och 7.0 procent
ett golv på 6.8 procent; SCB:s faktiska 2.35, 3.51 och 3.17 ger 2.75.

Modellen rapporterade u = 12.31 procent med v = 5.91, alltså u_min = 6.40 --
nästan exakt platshållarnas golv. Felet låg i indata jag själv skrivit och
sedan mätte modellen mot.
"""
import sqlite3

import numpy as np
import pandas as pd
import pytest

from core.scenariobuilder import ScenarioBuilder


class _Byggare:
    def __init__(self, conn):
        self.conn = conn

    faktisk_arbetsloshet = ScenarioBuilder.faktisk_arbetsloshet


def _db(rader):
    conn = sqlite3.connect(":memory:")
    pd.DataFrame(rader).to_sql("labour_market_status", conn, index=False)
    return conn


def test_talen_las_som_andel():
    conn = _db([{"municipal_code": "2062", "u_rate": 2.35},
                {"municipal_code": "2034", "u_rate": 3.51}])
    u = _Byggare(conn).faktisk_arbetsloshet(["2062", "2034"])
    assert u["2062"] == pytest.approx(0.0235)
    assert u["2034"] == pytest.approx(0.0351)


def test_golvet_foljer_av_talet():
    """Räkningen som motiverar patchen, som ett test: u_min = 1 - J/L där
    L = summa syss/(1-u)."""
    syss = {"2062": 9004, "2034": 3025, "2039": 3083}
    J = sum(syss.values())
    for u_vals, vantat in (({"2062": .065, "2034": .075, "2039": .070}, 6.8),
                           ({"2062": .0235, "2034": .0351, "2039": .0317}, 2.75)):
        L = sum(s / (1 - u_vals[k]) for k, s in syss.items())
        assert 100 * (1 - J / L) == pytest.approx(vantat, abs=0.05)


def test_heltalskoder_och_nollor():
    """Kommunkoderna i scenariofilen är heltal, och Stockholms 0180 tappar
    sin nolla om den lagrats numeriskt."""
    conn = _db([{"municipal_code": 180, "u_rate": 5.0},
                {"municipal_code": "2062", "u_rate": 2.35}])
    u = _Byggare(conn).faktisk_arbetsloshet([180, 2062])
    assert set(u) == {"0180", "2062"}


def test_delvis_tackning_ger_fallback():
    """Delvis täckning duger inte: några kommuner skulle ha uppmätt
    arbetslöshet och andra en gissning, och jämförelsen mellan dem mäta
    skillnaden mellan källorna."""
    conn = _db([{"municipal_code": "2062", "u_rate": 2.35}])
    assert _Byggare(conn).faktisk_arbetsloshet(["2062", "2034"]) is None


def test_saknad_tabell_ger_fallback():
    conn = sqlite3.connect(":memory:")
    assert _Byggare(conn).faktisk_arbetsloshet(["2062"]) is None


def test_nan_raknas_som_saknat():
    conn = _db([{"municipal_code": "2062", "u_rate": 2.35},
                {"municipal_code": "2034", "u_rate": None}])
    assert _Byggare(conn).faktisk_arbetsloshet(["2062", "2034"]) is None


def test_forvalet_ar_register():
    import os

    import yaml

    from core.configreader import ConfigReader
    rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scen = os.path.join(rot, "scenarios")
    with open(os.path.join(scen, "_simulation_defaults.yml"), encoding="utf-8") as f:
        cfg = ConfigReader.resolve_extends(yaml.safe_load(f), scen)
    assert cfg["simulation"]["unemployment_source"] == "register"


def test_scenario_source_stanger_av():
    import inspect

    from core import scenariobuilder

    kalla = inspect.getsource(scenariobuilder.ScenarioBuilder.generate)
    assert 'unemployment_source' in kalla
    assert '"register"' in kalla
