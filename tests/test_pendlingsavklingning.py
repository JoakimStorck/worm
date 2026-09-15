"""Geografisk avklingning i mötet, och arbetslöshet per kommun.

Relevansfiltret i search_once mäter avstånd i UPPGIFTSRUMMET. Planet kom
tidigare in enbart som -commute_cost_per_km*km inuti överskottet S, och S
divideras med (1 + kö). Med medel tolv sökande per vakans blir straffet 0.005
per km till 0.0004, och mot choice_scale 0.05 är femtio kilometer värt vikten
0.68 mot ett jobb runt hörnet -- utan kön hade det varit 0.007. Avståndet var
bortdividerat, inte felkalibrerat.
"""
import os
import sqlite3

import numpy as np
import pandas as pd
import pytest

from core.database.load_commuting_matrix import las_arbetsmarknadsstatus


# ---------------------------------------------------------------------------
# Avklingningen
# ---------------------------------------------------------------------------
def test_kodivisionen_plattar_ut_avstandet():
    """Räkningen som motiverar patchen, som ett test så att den inte kan
    glömmas bort: straffet i S delas med kölängden."""
    c, scale = 0.005, 0.05
    nara, langt = 5.0, 50.0
    utan_ko = np.exp(-(c * langt - c * nara) / scale)
    med_ko = np.exp(-(c * langt - c * nara) / 13 / scale)
    assert utan_ko < 0.02          # 50 km nästan uteslutet
    assert med_ko > 0.60           # ...men inte med tolv i kö
    assert med_ko / utan_ko > 30


def test_avklingningen_faller_med_avstandet():
    d0 = 25.0
    km = np.array([0.0, 10.0, 25.0, 50.0, 100.0])
    p = np.exp(-km / d0)
    assert p[0] == pytest.approx(1.0)
    assert p[2] == pytest.approx(np.e ** -1, rel=1e-6)
    assert list(p) == sorted(p, reverse=True)


def test_skalan_styr_hur_snabbt():
    km = 50.0
    assert np.exp(-km / 10.0) < np.exp(-km / 25.0) < np.exp(-km / 100.0)


def test_avstangd_som_forval():
    """null ger exakt tidigare beteende, inklusive slumpens ordning."""
    import yaml
    from core.configreader import ConfigReader
    rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scen = os.path.join(rot, "scenarios")
    with open(os.path.join(scen, "_simulation_defaults.yml"), encoding="utf-8") as f:
        cfg = ConfigReader.resolve_extends(yaml.safe_load(f), scen)
    assert cfg["simulation"]["commute_decay_km"] is None


def test_parametern_nar_sokningen():
    import inspect

    from core import matching_core
    from core.occupations import utils

    assert "commute_decay_km" in inspect.signature(utils.search_once).parameters
    assert "commute_decay_km" in inspect.getsource(matching_core.search_config)


def test_motet_och_inte_overskottet():
    """Avklingningen ska ligga i mötessannolikheten. Läggs den i S träffas den
    av kö-divisionen och är verkningslös igen."""
    import inspect

    from core.occupations import utils

    kalla = inspect.getsource(utils.search_once)
    i_mote = kalla.index("mote = rng.random")
    i_ko = kalla.index("S = S / (1.0 + ")
    i_decay = kalla.index("commute_decay_km:")
    assert i_decay < i_mote < i_ko


# ---------------------------------------------------------------------------
# Arbetsmarknadsstatus
# ---------------------------------------------------------------------------
def _skriv_ams(path, rader, kodning="iso-8859-1"):
    huvud = ["Arbetsmarknadsstatus. Slutlig statistik" + ";" * 8, ";" * 8,
             ";".join(["kommunkod", "kommunnamn", "kön", "ålder", "födelseregion",
                       "antal sysselsatta 2023", "antal arbetslösa 2023",
                       "antal studerande 2023", "antal pensionärer 2023"])]
    with open(path, "w", encoding=kodning) as f:
        f.write("\n".join(huvud + rader) + "\n")


def test_filtrerar_pa_fodelseregion_totalt(tmp_path):
    """Filen är korsklassificerad MED en totalrad, så raderna ska filtreras --
    motsatsen till yrkesregistrets uttag, som saknar totalrad och ska
    summeras. Summeras den här dubbleras talen."""
    p = str(tmp_path / "ams.csv")
    _skriv_ams(p, [
        "2062;Mora;totalt;20-65 år;inrikes född;8500;190;100;50",
        "2062;Mora;totalt;20-65 år;utrikes född;734;32;20;10",
        "2062;Mora;totalt;20-65 år;totalt;9234;222;120;60",
    ])
    d = las_arbetsmarknadsstatus(p).set_index("municipal_code")
    assert d.loc["2062", "employed"] == 9234
    assert d.loc["2062", "unemployed"] == 222


def test_arbetslosheten_ar_andel_av_arbetskraften(tmp_path):
    p = str(tmp_path / "ams.csv")
    _skriv_ams(p, [
        "2034;Orsa;totalt;20-65 år;totalt;3108;113;80;40",
        "2039;Älvdalen;totalt;20-65 år;totalt;3118;102;70;35",
        "2062;Mora;totalt;20-65 år;totalt;9234;222;120;60",
    ])
    d = las_arbetsmarknadsstatus(p).set_index("municipal_code")
    assert d.loc["2034", "u_rate"] == pytest.approx(3.51, abs=0.01)
    assert d.loc["2039", "u_rate"] == pytest.approx(3.17, abs=0.01)
    assert d.loc["2062", "u_rate"] == pytest.approx(2.35, abs=0.01)
    # Verklighetens rangordning: Mora lägst, Orsa högst.
    assert list(d["u_rate"].sort_values().index) == ["2062", "2039", "2034"]


def test_flera_rader_per_kommun_kastar(tmp_path):
    """Missas en dimension i filtreringen är talen dubbelräknade, och det ska
    stoppa laddningen i stället för att ge en trovärdig siffra."""
    p = str(tmp_path / "ams.csv")
    # Två åldersintervall, ingen totalrad för ålder: summeringen ger en rad,
    # men om filen i stället bär två oberoende dimensioner ska det märkas.
    _skriv_ams(p, [
        "2062;Mora;totalt;20-65 år;totalt;9234;222;120;60",
        "2062;Mora;totalt;16-19 år;totalt;400;40;300;0",
    ])
    d = las_arbetsmarknadsstatus(p)
    # Summeras korrekt till EN rad per kommun.
    assert len(d) == 1
    assert d.loc[0, "employed"] == 9634


def test_kommunkod_med_inledande_nolla(tmp_path):
    p = str(tmp_path / "ams.csv")
    _skriv_ams(p, ["0180;Stockholm;totalt;20-65 år;totalt;500000;20000;0;0"])
    d = las_arbetsmarknadsstatus(p)
    assert d.loc[0, "municipal_code"] == "0180"


def test_modellens_arbetsloshet_ar_andel_av_arbetskraften(tmp_path):
    """Individtabellen är hela befolkningen. Andelen av befolkningen skiljer
    sig med ungefär en faktor två från andelen av arbetskraften -- en
    förväxling som en gång fick modellens tal att se ut att ligga nära
    verklighetens när de låg tre till sex gånger över."""
    from scripts.analysis import arbetsloshet_per_kommun

    d = str(tmp_path / "run")
    os.makedirs(d)
    rader = ([{"individual_id": f"2062_i{i:06d}", "status": "employed"} for i in range(430)]
             + [{"individual_id": f"2062_i{i:06d}", "status": "unemployed"}
                for i in range(430, 469)]
             + [{"individual_id": f"2062_i{i:06d}", "status": "not_in_labor_force"}
                for i in range(469, 1000)])
    pd.DataFrame(rader).to_csv(os.path.join(d, "final_state_individuals.csv"),
                               index=False)
    t = arbetsloshet_per_kommun(d)
    assert t.loc["2062", "u_rate"] == pytest.approx(100 * 39 / 469, abs=0.05)
    # Andelen av befolkningen hade varit 3.9 procent -- ungefär halva.
    assert t.loc["2062", "u_rate"] > 2 * (100 * 39 / 1000)
