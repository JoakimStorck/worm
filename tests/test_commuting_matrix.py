"""SCB:s pendlingsmatris in i tabellen `commuting`.

Tabellen fanns inte i databasen trots att core/occupations/utils.py kallar den
den enda kalibreringen av commute_cost_per_km och analysis.py skrev i varje
rapport att pendlingen kalibrerats mot den. Den gamla laddaren anropades av
ingenting, hade ett NameError på sista raden, och läste dessutom radetiketten
som första kolumnen -- vilket i SCB:s breda uttag är ÅRTALET, inte
bostadskommunen.

Testerna bygger filer i båda uttagens format, i ISO-8859-1 som SCB skriver, och
kräver att de ger samma matris.
"""
import os
import sqlite3

import pandas as pd
import pytest

from core.database.load_commuting_matrix import las_pendling, load_commuting_matrix

KOMMUNER = [("2031", "Rättvik"), ("2034", "Orsa"), ("2062", "Mora")]
FLODEN = {
    "2031": {"2031": 2000, "2034": 50, "2062": 400},
    "2034": {"2031": 60, "2034": 1500, "2062": 500},
    "2062": {"2031": 300, "2034": 200, "2062": 7000},
}


def _bred(path, kodning="iso-8859-1"):
    """Uttag med arbetsställekommun som kolumner. Två skräprader först, och
    bostadskommunen som TREDJE kolumn efter år och kön."""
    rader = ["Sysselsatta 15-74 år. Årligt register" + ";" * 3, ";" * 3,
             ";".join(["år", "kön", "bostadskommun"]
                      + [f"{k} {n} (arbetsställe)" for k, n in KOMMUNER])]
    for k, n in KOMMUNER:
        rader.append(";".join(["2023", "totalt", f"{k} {n} (bostad)"]
                              + [str(FLODEN[k][kk]) for kk, _ in KOMMUNER]))
    with open(path, "w", encoding=kodning) as f:
        f.write("\n".join(rader) + "\n")


def _lang(path, kodning="iso-8859-1"):
    """Uttag med en rad per par och en kolumn per år."""
    rader = ['"Förvärvsarbetande 16-74 år pendlare över kommungräns"', "",
             '"bostadskommun","arbetsställekommun","kön","2021"']
    for k, n in KOMMUNER:
        for kk, nn in KOMMUNER:
            rader.append(f'"{k} {n}","{kk} {nn}","män och kvinnor",{FLODEN[k][kk]}')
    with open(path, "w", encoding=kodning) as f:
        f.write("\n".join(rader) + "\n")


def _matris(df):
    return {(r.home_municipality, r.work_municipality): r.employed
            for r in df.itertuples()}


def test_bada_uttagen_ger_samma_matris(tmp_path):
    b, l = str(tmp_path / "bred.csv"), str(tmp_path / "lang.csv")
    _bred(b); _lang(l)
    mb, ml = _matris(las_pendling(b)), _matris(las_pendling(l))
    assert mb == ml
    assert mb[("2034", "2062")] == 500


def test_bostadskommunen_las_ur_ratt_kolumn(tmp_path):
    """Den gamla laddaren tog radetiketten som första kolumnen. I det breda
    uttaget står året där, och matrisen hade fått 2023 som bostadskommun."""
    b = str(tmp_path / "bred.csv")
    _bred(b)
    df = las_pendling(b)
    assert set(df["home_municipality"]) == {"2031", "2034", "2062"}
    assert set(df["year"]) == {2023}


def test_diagonalen_foljer_med(tmp_path):
    """Andelen som pendlar över gräns är ett tal med en nämnare, och nämnaren
    är alla sysselsatta med bostad i kommunen -- också de som stannar."""
    l = str(tmp_path / "lang.csv")
    _lang(l)
    df = las_pendling(l)
    egen = df[df["home_municipality"] == df["work_municipality"]]
    assert len(egen) == 3
    tot = df[df["home_municipality"] == "2034"]["employed"].sum()
    over = df[(df["home_municipality"] == "2034")
              & (df["work_municipality"] != "2034")]["employed"].sum()
    assert round(100 * over / tot, 1) == 27.2


@pytest.mark.parametrize("kodning", ["iso-8859-1", "cp1252", "utf-8"])
def test_kodningar(tmp_path, kodning):
    """SCB skriver ISO-8859-1 som förval. Läses den som UTF-8 faller den --
    eller värre, den läses tyst fel."""
    b = str(tmp_path / f"bred_{kodning}.csv")
    _bred(b, kodning=kodning)
    assert len(las_pendling(b)) == 9


def test_skriver_till_databasen(tmp_path):
    b, db = str(tmp_path / "bred.csv"), str(tmp_path / "t.sqlite3")
    _bred(b)
    n = load_commuting_matrix(b, db_path=db)
    assert n == 9
    conn = sqlite3.connect(db)
    df = pd.read_sql("SELECT * FROM commuting", conn)
    conn.close()
    assert set(df.columns) >= {"home_municipality", "work_municipality",
                               "year", "employed"}
    assert df["employed"].sum() == sum(sum(v.values()) for v in FLODEN.values())


def test_otolkbar_fil_kastar_i_stallet_for_att_ge_nollor(tmp_path):
    """En matris full av nollor ser ut som data och skulle passera varje
    senare kontroll."""
    p = str(tmp_path / "fel.csv")
    with open(p, "w", encoding="utf-8") as f:
        f.write("något;helt;annat\n1;2;3\n")
    with pytest.raises(ValueError):
        las_pendling(p)
