"""Kommunkoder med inledande nolla.

SCB:s koder är fyra siffror och 127 av dem börjar med nolla -- hela
Stockholms, Uppsala, Södermanlands, Östergötlands, Jönköpings, Kronobergs och
Kalmar län. Läses ett lager ur en gpkg där kolumnen är numerisk blir 0180 till
180, och varje uppslag faller tyst: ingen tabell klagar, raden finns bara
inte.

Felet upptäcktes i pendlingsdiagnosen, där Stockholm och Solna skrevs ut som
0180 och 0184 medan alla Dalakoder slog rätt. Dalarnas koder börjar på 2 och
överlever konverteringen, vilket är precis varför felet kunde ligga kvar: en
modell som körs på Mora, Orsa och Rättvik ser aldrig något fel.
"""
import sqlite3

import pandas as pd
import pytest

from core.database.utils import kommunkod


def test_inledande_nolla_bevaras():
    assert list(kommunkod(pd.Series([180, 184, 2062]))) == ["0180", "0184", "2062"]


def test_redan_korrekta_strangar_ar_orörda():
    assert list(kommunkod(pd.Series(["0180", "2062"]))) == ["0180", "2062"]


def test_flyttal_ur_gpkg_tappar_inte_koden():
    """geopandas ger ibland float64 för heltalskolumner med NULL i sig, och
    str(180.0) är '180.0' -- som zfill:as till '180.0', inte '0180'."""
    assert list(kommunkod(pd.Series([180.0, 2062.0]))) == ["0180", "2062"]


def test_blanksteg_trimmas():
    assert list(kommunkod(pd.Series([" 0180 ", "2062\t"]))) == ["0180", "2062"]


def test_uppslag_mot_pendlingstabellen_traffar(tmp_path):
    """Hela poängen: en kod ur commuting ska hitta sitt namn i municipalities
    även när den ena sidan lagrats numeriskt."""
    db = str(tmp_path / "db.sqlite3")
    conn = sqlite3.connect(db)
    # municipalities som den såg ut FÖRE rättningen: numerisk kod.
    pd.DataFrame([{"municipal_code": 180, "municipality": "Stockholm"},
                  {"municipal_code": 2062, "municipality": "Mora"}]
                 ).to_sql("municipalities", conn, index=False)
    conn.close()

    conn = sqlite3.connect(db)
    namn = {str(k).strip().zfill(4): n for k, n in
            conn.execute("SELECT municipal_code, municipality FROM municipalities")}
    conn.close()
    assert namn["0180"] == "Stockholm"
    assert namn["2062"] == "Mora"


def test_loaders_gar_via_hjalparen():
    """Varje skrivning av municipal_code ska normaliseras. En loader som
    glöms bort skriver koder som ser riktiga ut för Dalarna och tyst fel för
    halva Sverige."""
    import inspect

    from core.database import loader

    kalla = inspect.getsource(loader)
    for rad in kalla.splitlines():
        r = rad.strip()
        if r.startswith(("gdf[\"municipal_code\"] =", "gdf['municipal_code'] =",
                         "gdf[\"kommunkod\"] =")):
            assert "kommunkod(" in r, r
