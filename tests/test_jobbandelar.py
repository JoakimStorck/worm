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
    pd.DataFrame(rader).to_sql("employment_deso_sni", conn, index=False)
    return conn


def _rader(per_kommun, year=2023, med_total=True, deso_per_kommun=3):
    """Totalrader OCH branschrader, fördelade över flera DeSO per kommun --
    andelarna ska summera per kommun och bara över totalraderna."""
    ut = []
    for kod, tot in per_kommun.items():
        delar = [tot // deso_per_kommun] * deso_per_kommun
        delar[-1] = tot - sum(delar[:-1])
        for i, d in enumerate(delar):
            deso = f"{kod}A{i:04d}"
            if med_total:
                ut.append({"deso_code": deso, "year": year,
                           "sni_code": "TOTAL", "employed": d})
            # Branschrader: ska INTE räknas med i andelarna.
            ut.append({"deso_code": deso, "year": year,
                       "sni_code": "A", "employed": d // 4})
            ut.append({"deso_code": deso, "year": year,
                       "sni_code": "Q", "employed": d // 3})
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


def test_branschraderna_raknas_inte_med():
    """Andelen ska bygga på totalraden. Summeras branschraderna med blir
    talet ungefär dubbelt och dessutom snedvridet av sekretessprickning."""
    conn = _db(_rader({"2062": 9948, "2034": 2235}))
    a = _Byggare(conn).jobbandelar(["2062", "2034"], 2023)
    assert round(a["2062"], 3) == round(9948 / (9948 + 2235), 3)


def test_utan_totalrad_ges_fallback():
    """En tabell laddad med den gamla extract_sni_code har ingen TOTAL-kod --
    totalen ligger dold under näringsgren A. Då ska andelarna inte gissas."""
    conn = _db(_rader({"2062": 9948, "2034": 2235}, med_total=False))
    assert _Byggare(conn).jobbandelar(["2062", "2034"], 2023) is None


def test_en_kommun_utan_underlag_ger_fallback():
    """Saknas arbetsställestatistik för NÅGON kommun används den gamla
    fördelningen för alla. En blandning -- data för några, egen arbetskraft
    för resten -- ger en total som inte stämmer med någondera."""
    conn = _db(_rader({"2062": 9948}))
    assert _Byggare(conn).jobbandelar(["2062", "2034"], 2023) is None


def test_nollrader_raknas_som_saknat_underlag():
    conn = _db(_rader({"2062": 9948, "2034": 0}))
    assert _Byggare(conn).jobbandelar(["2062", "2034"], 2023) is None


def test_aldre_ar_duger_via_fallback():
    """fetch_with_fallback tar närmaste tidigare år. Ett scenario som startar
    2024 ska kunna använda 2023 års statistik."""
    conn = _db(_rader({"2062": 9948, "2034": 2235}, year=2023))
    a = _Byggare(conn).jobbandelar(["2062", "2034"], 2024)
    assert a is not None and round(sum(a.values()), 6) == 1.0
