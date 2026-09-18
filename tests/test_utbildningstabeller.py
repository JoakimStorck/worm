"""Läsarna för steg 4 (core/database/load_utbildning.py): TAB4359, TAB4360
och TAB655, mot filer i det format fetch_data.py skriver."""
import pandas as pd
import pytest

from core.database.load_utbildning import kontrollera_yrkestotaler, las_tabell

NIVA = {"Yrke2012": "ssyk_code", "UtbNivaSun2020": "level", "Alder": "age_class", "Kon": "sex"}
INRIKTNING = {"Yrke2012": "ssyk_code", "UtbinriktnSUN2020": "field",
              "Alder": "age_class", "Kon": "sex"}


def _fil(tmp_path, namn, text, kodning="utf-8"):
    p = tmp_path / namn
    p.write_bytes(text.encode(kodning))
    return p


def test_aret_i_kolumnen_eller_i_rubriken(tmp_path):
    """PxWeb hörsammar ibland placeringen av Tid och ibland inte; då står året
    i värdekolumnens rubrik (fallgrop 3). Båda formerna ger samma tabell."""
    med_tid = _fil(tmp_path, "a.csv",
                   '"Yrke2012","UtbNivaSun2020","Alder","Kon","Tid","000006XQ"\n'
                   '"532","4","25-29","2","2024",120\n"0002","US","25-29","2","2024",3\n')
    i_rubrik = _fil(tmp_path, "b.csv",
                    '"Yrke2012","UtbNivaSun2020","Alder","Kon","000006XQ 2024"\n'
                    '"532","4","25-29","2",120\n"0002","US","25-29","2",3\n')
    a = las_tabell(med_tid, NIVA, "employed")
    b = las_tabell(i_rubrik, NIVA, "employed")
    pd.testing.assert_frame_equal(a, b)
    assert list(a.columns) == ["ssyk_code", "level", "age_class", "sex", "year", "employed"]
    assert set(a.year) == {2024}
    # restposterna behålls: de är inte summor
    assert set(zip(a.ssyk_code, a.level)) == {("532", "4"), ("0002", "US")}


def test_utan_ar_eller_med_tva_varden_kastar(tmp_path):
    utan_ar = _fil(tmp_path, "c.csv",
                   '"Yrke2012","UtbNivaSun2020","Alder","Kon","000006XQ"\n"532","4","25-29","2",1\n')
    with pytest.raises(ValueError, match="året"):
        las_tabell(utan_ar, NIVA, "employed")
    tva = _fil(tmp_path, "d.csv",
               '"Yrke2012","UtbNivaSun2020","Alder","Kon","Tid","X","Y"\n"532","4","25-29","2","2024",1,2\n')
    with pytest.raises(ValueError, match="EN värdekolumn"):
        las_tabell(tva, NIVA, "employed")


def _tabeller(n_niva):
    inr = pd.DataFrame({"ssyk_code": ["532", "532", "911"], "field": ["7", "0", "0"],
                        "age_class": "25-29", "sex": "2", "year": 2024,
                        "employed": [100, 20, 40]})
    niv = pd.DataFrame({"ssyk_code": ["532", "532", "911"], "level": ["4", "5", "2"],
                        "age_class": "25-29", "sex": "2", "year": 2024,
                        "employed": n_niva})
    return inr, niv


def test_yrkestotalerna_ska_vara_identiska():
    """TAB4359 och TAB4360 räknar samma anställda. Skiljer yrkestotalerna är
    ett av uttagen fel år eller ofullständigt, och rakingen hade fått två
    marginaler som inte går att förena."""
    inr, niv = _tabeller([90, 30, 40])
    kontrollera_yrkestotaler(inr, niv)
    inr, niv = _tabeller([90, 30, 39])
    with pytest.raises(ValueError, match="911"):
        kontrollera_yrkestotaler(inr, niv)
    inr, niv = _tabeller([90, 30, 40])
    with pytest.raises(ValueError, match="olika yrkestotaler"):
        kontrollera_yrkestotaler(inr, niv[niv.ssyk_code != "911"])
