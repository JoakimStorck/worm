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


# ---------------------------------------------------------------------------
# Inträdets tabeller (docs/intradet.md, 6b-1)
# ---------------------------------------------------------------------------

def test_studiedeltagandet_summerar_barnens_alder_och_tal_latin1(tmp_path):
    """TAB3731 i latin-1 (FÖRV). Yngsta barnets ålder är en uppdelning, ingen
    total: den summeras."""
    from core.database.load_utbildning import las_studiedeltagande
    p = _fil(tmp_path, "s.csv",
             '"Kon","Alder","Studiedeltagande","UtbildningsNiva","Sysselsattning","BarnAlder","Tid","UF0507G1"\n'
             '"1","19","H","4","FÖRV","4","2024",30\n'
             '"1","19","H","4","FÖRV","1","2024",2\n'
             '"1","19","0","4","EJFÖRV","4","2024",5\n', kodning="latin-1")
    d = las_studiedeltagande(p)
    assert len(d) == 2
    assert d.set_index(["study", "employment"]).population[("H", "FÖRV")] == 32


FLODE_RUBRIK = ('"Region","Utbildngrupp","KonAlderFodelseland",'
                '"000008QG 2023-2024","000008QH 2023-2024","000008QI 2023-2024",'
                '"000008QM 2023-2024"\n')


def test_flodena_i_langt_format_utan_de_odefinierade(tmp_path):
    """Riket har ".." för flyttningarna; de blir ingen rad."""
    from core.database.load_utbildning import las_utbildningsfloden
    p = _fil(tmp_path, "f.csv", FLODE_RUBRIK
             + '"2062","03","18-24",1316,1301,-15,-217\n'
             + '"00","03","18-24",100,110,10,..\n')
    d = las_utbildningsfloden(p)
    ut = d[(d.municipal_code == "2062") & (d.measure == "out_migrants")]
    assert ut.value.tolist() == [-217] and ut.period.tolist() == ["2023-2024"]
    assert d[(d.municipal_code == "00")].measure.tolist() == ["population_1", "population_2", "net"]


def test_befolkningen_ar_2_ska_vara_ar_1_plus_nettot(tmp_path):
    from core.database.load_utbildning import las_utbildningsfloden
    p = _fil(tmp_path, "f.csv", FLODE_RUBRIK + '"2062","03","18-24",1316,1302,-15,-217\n')
    with pytest.raises(ValueError, match="år 1 plus nettot"):
        las_utbildningsfloden(p)
    fel = _fil(tmp_path, "g.csv", FLODE_RUBRIK.replace("000008QM", "000008XX")
               + '"2062","03","18-24",1316,1301,-15,-217\n')
    with pytest.raises(ValueError, match="okända"):
        las_utbildningsfloden(fel)
