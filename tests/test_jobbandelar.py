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


def test_jobben_foljer_kolumnsumman():
    conn = _db(_rader({"2062": 9948, "2034": 2235, "2039": 2933}))
    m = _Byggare(conn).jobbandelar(["2062", "2034", "2039"], 2023)
    j = m["jobb"]
    # Ovansiljans faktiska ordning: Mora, Älvdalen, Orsa.
    assert j["2062"] > j["2039"] > j["2034"]
    assert round(j["2062"]) == 9948


def test_bada_marginalerna_summerar_lika():
    """Delmatrisen ÄR en sluten arbetsmarknad: kolumnsummorna och
    radsummorna är samma tal. Det är det som gör att scenariot kan ha
    olika dag/natt per kommun utan att jobben tar slut eller blir över."""
    conn = _db(_rader({"2062": 9948, "2034": 2235, "2039": 2933}))
    m = _Byggare(conn).jobbandelar(["2062", "2034", "2039"], 2023)
    assert round(sum(m["jobb"].values())) == round(sum(m["boende"].values()))


def test_boende_kommer_ur_radsumman():
    """Nämnaren får inte komma ur scenariofilens workforce_ratio. Med
    platshållarna för Ovansiljan fick Mora 63.3 procent av invånarna mot
    SCB:s 59.6 och Älvdalen 18.1 mot 20.4, vilket ensamt förklarade att
    dag/natt blev 1.04 och 1.07 i stället för 1.10 och 0.95."""
    conn = _db([
        {"home_municipality": "2062", "work_municipality": "2062",
         "year": 2023, "employed": 8360},
        {"home_municipality": "2034", "work_municipality": "2062",
         "year": 2023, "employed": 1219},
        {"home_municipality": "2062", "work_municipality": "2034",
         "year": 2023, "employed": 431},
        {"home_municipality": "2034", "work_municipality": "2034",
         "year": 2023, "employed": 1759},
    ])
    m = _Byggare(conn).jobbandelar(["2062", "2034"], 2023)
    assert m["boende"]["2062"] == 8360 + 431
    assert m["boende"]["2034"] == 1219 + 1759
    # Och dag/natt blir SCB:s egna kvoter.
    assert m["jobb"]["2062"] / m["boende"]["2062"] == pytest.approx(1.09, abs=0.01)
    assert m["jobb"]["2034"] / m["boende"]["2034"] == pytest.approx(0.74, abs=0.01)



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
    m = _Byggare(conn).jobbandelar(["2062", "2034"], 2023)
    assert m["jobb"]["2062"] == 8360 + 1219      # kolumnsumma
    assert m["boende"]["2062"] == 8360 + 431     # radsumma
    assert m["jobb"]["2062"] != m["boende"]["2062"]


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
    m = _Byggare(conn).jobbandelar(["2062", "2034"], 2024)
    assert m is not None
    assert round(sum(m["jobb"].values())) == round(sum(m["boende"].values()))


def test_nycklarna_ar_strangar_aven_for_heltalskoder():
    """Kommunkoderna i scenariofilen är heltal. Slog anroparen upp med rå kod
    blev det KeyError vid första kommunen, mitt i en körning."""
    conn = _db(_rader({"2062": 9948, "2034": 2235}))
    m = _Byggare(conn).jobbandelar([2062, 2034], 2023)
    assert set(m["jobb"]) == {"2062", "2034"}
    assert m["jobb"][str(2062)] > m["jobb"][str(2034)]
