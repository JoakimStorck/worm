"""Vakansgraden och jobbmålet (docs/stockarna.md, C1).

Pendlingsmatrisens kolumnsumma räknar sysselsatta, alltså besatta jobb.
Modellen tog den som antalet positioner, så varje vakans blev en sysselsatt
för lite: u = u_min + V/L, med V/L omkring 6 procentenheter över SCB:s
arbetslöshet i Ovansiljan. Positionerna är nu J_data · (1 + v), v ur
SCB:s lediga jobb per anställning i kommunens län (TAB6605)."""
import sqlite3

import pandas as pd
import pytest

from core.database.load_lediga_jobb import las_lediga_jobb
from core.scenariobuilder import ScenarioBuilder

# Rubriken som PxWeb skriver den: innehåll och kvartal i värdekolumnerna.
RUBRIK = ('"LedJobbTyp - typ av lediga jobb","AARegion - region",'
          '"0000081B - antal, per anställning 2024K2 - 2024K2",'
          '"0000081B - antal, per anställning 2024K3 - 2024K3",'
          '"0000081C - antal, per anställning, osäkerhetsmarginal 2024K2 - 2024K2",'
          '"0000081C - antal, per anställning, osäkerhetsmarginal 2024K3 - 2024K3"\n')


def _fil(tmp_path, rader, rubrik=RUBRIK, kodning="latin-1"):
    p = tmp_path / "lediga.csv"
    p.write_bytes((rubrik + "".join(rader)).encode(kodning))
    return p


def test_lanen_valjs_och_rubriken_tas_isar(tmp_path):
    """Regionerna blandar riket, län, riksområden och NUTS2 utan totalrader.
    Bara länen ska med, och kvartalet står i rubriken, inte i en kolumn.
    Filen är latin-1, som svaret från PxWeb när det bär klartext."""
    rader = ['"LJtotA - lediga jobb, totalt","00 - 00 Sverige",3.1,2.2,0.2,0.1\n',
             '"LJtotA - lediga jobb, totalt","20 - 20 Dalarnas län",2.1,1.9,0.5,0.5\n',
             '"LJtotA - lediga jobb, totalt","SE31 - SE31 Norra Mellansverige",2.8,2.3,0.4,0.4\n',
             '"LJtotA - lediga jobb, totalt","SE3 - SE3 Norra Sverige",3.1,2.2,0.3,0.3\n',
             '"LJomgA - lediga jobb med omgående tillträde","20 - 20 Dalarnas län",1.1,..,0.3,0.4\n']
    df = las_lediga_jobb(_fil(tmp_path, rader))
    assert set(df["county_code"]) == {"20"}
    tot = df[df.vacancy_type == "LJtotA"].set_index("quarter")
    assert tot.loc["2024K2", "per_100"] == pytest.approx(2.1)
    assert tot.loc["2024K3", "per_100"] == pytest.approx(1.9)
    assert tot.loc["2024K2", "margin"] == pytest.approx(0.5)
    # ".." är ett saknat värde och ska inte bli en rad, inte heller när
    # osäkerhetsmarginalen finns (i TAB6605 saknas i dag båda samtidigt)
    omg = df[df.vacancy_type == "LJomgA"]
    assert list(omg["quarter"]) == ["2024K2"]


def test_rubrik_utan_kvartal_kastar(tmp_path):
    fel = '"LedJobbTyp - typ","AARegion - region","0000081B - antal, per anställning"\n'
    with pytest.raises(ValueError, match="kvartal"):
        las_lediga_jobb(_fil(tmp_path, ['"LJtotA - x","20 - Dalarna",2.0\n'], rubrik=fel))


class _Konfig:
    def __init__(self, simulation):
        self.config = {"simulation": simulation}


class _Byggare:
    def __init__(self, conn, utlovad_andel=0.0):
        self.conn = conn
        sim = {} if utlovad_andel is None else {"utlovad_andel": utlovad_andel}
        self.cfg_reader = _Konfig(sim)

    vakansgrad = ScenarioBuilder.vakansgrad
    positioner = ScenarioBuilder.positioner


def _db(rader=None):
    conn = sqlite3.connect(":memory:")
    if rader is not None:
        pd.DataFrame(rader, columns=["county_code", "vacancy_type", "quarter",
                                     "per_100", "margin"]).to_sql(
            "vacancy_rate_county", conn, index=False)
    return conn


DALARNA_OCH_STOCKHOLM = [
    ("20", "LJtotA", "2024K2", 2.1, 0.5), ("20", "LJtotA", "2024K3", 1.9, 0.5),
    ("20", "LJomgA", "2024K2", 1.1, 0.3), ("20", "LJomgA", "2024K3", 1.1, 0.3),
    ("01", "LJtotA", "2024K2", 3.6, 0.4), ("01", "LJtotA", "2024K3", 3.0, 0.4),
]


def test_vakansgraden_ar_lanets_medel_av_lediga_jobb_totalt():
    """Totalt, inte omgående: modellens öppna vakans är en befattning som
    söks, med eller utan omedelbart tillträde. Medlet över kvartalen, som
    andel. Stockholms 0180 tappar sin nolla som heltal och hör till län 01."""
    v = _Byggare(_db(DALARNA_OCH_STOCKHOLM)).vakansgrad([2062, "2034", 180])
    assert v["2062"] == pytest.approx(0.020)
    assert v["2034"] == pytest.approx(0.020)
    assert v["0180"] == pytest.approx(0.033)


def test_positionerna_ar_de_sysselsatta_plus_de_lediga():
    """Varje kommun får sitt eget läns grad; kommunkoden bär länet."""
    b = _Byggare(_db(DALARNA_OCH_STOCKHOLM))
    p = b.positioner({"2062": 10_000, "2034": 3_000, "0180": 1_000})
    assert p == {"2062": 10_200, "2034": 3_060, "0180": 1_033}


def test_de_utlovade_positionerna_laggs_till():
    """C4c: den som byter jobb räknas i J_data en gång, på det gamla, och den
    väntande befattningen finns inte där. Utan andelen blev varje utlovad
    position en sysselsatt för lite."""
    b = _Byggare(_db(DALARNA_OCH_STOCKHOLM), utlovad_andel=0.018)
    assert b.positioner({"2062": 10_000}) == {"2062": 10_380}


def test_utan_utlovad_andel_ingen_tyst_nolla():
    with pytest.raises(ValueError, match="utlovad_andel"):
        _Byggare(_db(DALARNA_OCH_STOCKHOLM), utlovad_andel=None).positioner({"2062": 10})


def test_utan_vakansgrad_ingen_tyst_reserv():
    """Utan tabellen blev positionerna lika många som de sysselsatta -- det är
    felet som rättas, och det ska inte smyga tillbaka när filen fattas."""
    with pytest.raises(ValueError, match="fetch_data.py --only"):
        _Byggare(_db()).vakansgrad(["2062"])
    with pytest.raises(ValueError, match=r"länen \['24'\]"):
        _Byggare(_db(DALARNA_OCH_STOCKHOLM)).positioner({"2062": 10, "2480": 10})
