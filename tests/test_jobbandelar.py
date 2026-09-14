"""Jobbens fördelning mellan kommunerna.

Tidigare fick varje kommun target_jobs = workforce - n_unemployed, alltså
exakt lika många jobb som den har sysselsatta invånare. Nettopendlingen blev
noll i varje kommun per konstruktion och bara symmetriska bruttoflöden kunde
uppstå. I SCB:s tal för Ovansiljan har Mora 1.11 jobb per sysselsatt invånare,
Orsa 0.74 och Älvdalen 0.83.

employment_municipality_sni räknar sysselsatta efter ARBETSSTÄLLE, så summan
per kommun är dagbefolkningen, och kvoten mellan kommunerna är den fördelning
jobben ska ha. Nivån hämtas INTE därifrån: scenariot är slutet, och fler jobb
än sysselsatta invånare blir vakanser ingen kan fylla.
"""
import sqlite3

import pandas as pd
import pytest

from core.scenariobuilder import ScenarioBuilder


class _Byggare:
    """ScenarioBuilder utan __init__ -- bara conn och metoden som prövas."""

    def __init__(self, conn):
        self.conn = conn

    jobbandelar = ScenarioBuilder.jobbandelar


def _db(rader):
    conn = sqlite3.connect(":memory:")
    pd.DataFrame(rader).to_sql("commuting", conn, index=False)
    return conn


def _rader(jobb_per_kommun, year=2023):
    """Pendlingsmatris vars KOLUMNSUMMOR blir de önskade jobbtalen.

    Diagonalen bär huvuddelen och en liten ström läggs mellan kommunerna, så
    att kolumnsumman verkligen måste summeras och inte råkar bli diagonalen.
    """
    koder = list(jobb_per_kommun)
    ut = []
    for mal, tot in jobb_per_kommun.items():
        ovriga = [k for k in koder if k != mal]
        fran_andra = min(len(ovriga) * 10, max(tot - 1, 0))
        per = fran_andra // len(ovriga) if ovriga else 0
        for h in ovriga:
            if per:
                ut.append({"home_municipality": h, "work_municipality": mal,
                           "year": year, "employed": per})
        ut.append({"home_municipality": mal, "work_municipality": mal,
                   "year": year, "employed": tot - per * len(ovriga)})
    return ut


def test_andelarna_foljer_arbetsstallestatistiken():
    conn = _db(_rader({"2062": 9948, "2034": 2235, "2039": 2933}))
    a = _Byggare(conn).jobbandelar(["2062", "2034", "2039"], 2023)
    assert round(sum(a.values()), 6) == 1.0
    # Ovansiljans faktiska ordning: Mora, Älvdalen, Orsa.
    assert a["2062"] > a["2039"] > a["2034"]
    assert round(a["2062"], 3) == round(9948 / (9948 + 2235 + 2933), 3)


def test_summan_bevaras_och_asymmetrin_uppstar():
    """Totalen är scenariots egen; fördelningen kommer ur data. Mora ska få
    fler jobb än sina egna sysselsatta invånare, Orsa färre."""
    conn = _db(_rader({"2062": 9948, "2034": 2235}))
    a = _Byggare(conn).jobbandelar(["2062", "2034"], 2023)
    boende = {"2062": 8953, "2034": 3013}
    total = sum(boende.values())
    jobb = {k: round(total * v) for k, v in a.items()}
    assert sum(jobb.values()) == pytest.approx(total, abs=1)
    assert jobb["2062"] / boende["2062"] > 1.05
    assert jobb["2034"] / boende["2034"] < 0.85


def test_kolumnsumman_och_inte_radsumman():
    """DAG, INTE NATT. Kolumnsumman är jobben i kommunen; radsumman är dess
    boende sysselsatta. Orsa skiljer dem åt -- 2 235 jobb mot 3 348 boende --
    medan Mora skiljer bara någon procent och inte duger som kontroll.
    Förväxlingen gav andelar identiska med den gamla fördelningen, fast
    uppmätta i stället för antagna."""
    conn = _db([
        {"home_municipality": "2062", "work_municipality": "2062",
         "year": 2023, "employed": 8360},
        {"home_municipality": "2034", "work_municipality": "2062",
         "year": 2023, "employed": 1219},   # Orsabor med jobb i Mora
        {"home_municipality": "2062", "work_municipality": "2034",
         "year": 2023, "employed": 431},
        {"home_municipality": "2034", "work_municipality": "2034",
         "year": 2023, "employed": 1759},
    ])
    a = _Byggare(conn).jobbandelar(["2062", "2034"], 2023)
    jobb_mora, jobb_orsa = 8360 + 1219, 431 + 1759          # kolumnsummor
    assert round(a["2062"], 4) == round(jobb_mora / (jobb_mora + jobb_orsa), 4)
    # Radsumman hade gett Orsa en större andel -- kontrollen som saknades.
    boende_orsa = 1219 + 1759
    assert a["2034"] < boende_orsa / (8360 + 431 + boende_orsa)


def test_en_kommun_utan_underlag_ger_fallback():
    """Saknas arbetsställestatistik för NÅGON kommun används den gamla
    fördelningen för alla. En blandning -- data för några, egen arbetskraft
    för resten -- ger en total som inte stämmer med någondera."""
    conn = _db(_rader({"2062": 9948}))
    assert _Byggare(conn).jobbandelar(["2062", "2034"], 2023) is None


def test_nollrader_raknas_som_saknat_underlag():
    conn = _db([{"home_municipality": "2062", "work_municipality": "2062",
                 "year": 2023, "employed": 9948}])
    assert _Byggare(conn).jobbandelar(["2062", "2034"], 2023) is None


def test_aldre_ar_duger_via_fallback():
    """fetch_with_fallback tar närmaste tidigare år. Ett scenario som startar
    2024 ska kunna använda 2023 års statistik."""
    conn = _db(_rader({"2062": 9948, "2034": 2235}, year=2023))
    a = _Byggare(conn).jobbandelar(["2062", "2034"], 2024)
    assert a is not None and round(sum(a.values()), 6) == 1.0


def test_nycklarna_ar_strangar_aven_for_heltalskoder():
    """Kommunkoderna i scenariofilen är heltal. Slog anroparen upp med rå kod
    blev det KeyError vid första kommunen, mitt i en körning."""
    conn = _db(_rader({"2062": 9948, "2034": 2235}))
    a = _Byggare(conn).jobbandelar([2062, 2034], 2023)
    assert set(a) == {"2062", "2034"}
    assert a[str(2062)] > a[str(2034)]
