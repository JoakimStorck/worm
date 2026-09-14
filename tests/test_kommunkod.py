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


def test_varje_skrivare_av_municipal_code_normaliserar():
    """Varje laddare som skriver en tabell med municipal_code ska ha
    normaliserat koden först.

    Första försöket letade efter ett tilldelningsmönster i källkoden och
    missade därmed load_municipalities, som är den väg create_database.py
    faktiskt tar: den läser en CSV med dtype=str och rör aldrig kolumnen. Ett
    test som letar efter en viss RADFORM hittar bara de ställen man redan
    tänkt på. Det här går i stället per funktion: skriver den en tabell och
    nämner koden, ska hjälparen ha anropats i samma funktion.
    """
    import inspect
    import re

    from core.database import loader

    brister = []
    for namn, fn in inspect.getmembers(loader, inspect.isfunction):
        if not namn.startswith("load_") and not namn.startswith("update_"):
            continue
        try:
            kalla = inspect.getsource(fn)
        except OSError:
            continue
        if "to_sql(" not in kalla:
            continue
        if not re.search(r"municipal_code|kommunkod\b", kalla):
            continue
        if "kommunkod(" not in kalla:
            brister.append(namn)
    assert not brister, f"normaliserar inte kommunkoden: {brister}"
