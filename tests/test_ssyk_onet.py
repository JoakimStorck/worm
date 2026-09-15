"""SSYK 2012 -> O*NET-SOC 2019.

Två tabeller med avsikt: ssyk_isco_key är ren avskrift av SCB:s nyckel och
ändras bara när SCB publicerar en ny, medan ssyk3_onet_crosswalk är härledd och
bär fyra likformighetsantaganden. Ligger de i samma tabell går det inte att
skilja SCB:s uppgift från vår approximation.

Kedjan har fem led, tre av dem många-till-många:
    SSYK3 -> SSYK4 -> ISCO4 -> ISCO3 -> ESCO-yrke -> O*NET-SOC 2019
"""
import os

import pandas as pd
import pytest

from core.database.load_ssyk_onet import (MATCHVIKTER, bygg_crosswalk,
                                          las_esco_onet, las_ssyk_isco)


def _nyckel(path, rader):
    huvud = [["Nyckel SSYK 2012 - ISCO-08 (fyrsiffernivå)", None, None, None],
             [None] * 4, [None] * 4,
             ["SSYK 2012 kod", None, "ISCO-08 kod", None]]
    with pd.ExcelWriter(path) as w:
        pd.DataFrame(huvud + rader).to_excel(w, sheet_name="Nyckel",
                                             header=False, index=False)


def _crosswalk(path, rader):
    """Sexton metadatarader, som i ESCO-sekretariatets fil."""
    kol = ["O*NET Id", "O*NET Title", "O*NET Description", "ESCO or ISCO URI",
           "ESCO or ISCO Title", "ESCO or ISCO Description", "Type of Match"]
    with open(path, "w", encoding="utf-8") as f:
        for i in range(16):
            f.write(f"Mapping metadata {i},x,,,,,\n")
        f.write(",".join(f'"{c}"' for c in kol) + "\n")
        for r in rader:
            f.write(",".join(f'"{v}"' for v in r) + "\n")


def _esco(path, rader):
    pd.DataFrame(rader).to_csv(path, index=False)


# ---------------------------------------------------------------------------
# Nyckeln
# ---------------------------------------------------------------------------
def test_kommalistor_splittas(tmp_path):
    """0210 avbildas på "0110, 0210" och 1120 på "1120, 1420" i SCB:s fil."""
    p = str(tmp_path / "n.xlsx")
    _nyckel(p, [["0210", None, "0110, 0210", None],
                ["1120", None, "1120, 1420", None]])
    d = las_ssyk_isco(p)
    assert len(d) == 4
    assert set(d[d.ssyk4 == "0210"].isco4) == {"0110", "0210"}


def test_tappade_nollor_aterstalls(tmp_path):
    """Excel har tolkat 0110 som talet 110. Samma fälla som kommunkoderna i
    0132: koden ser riktig ut och matchar ingenting."""
    p = str(tmp_path / "n.xlsx")
    _nyckel(p, [["0110", None, 110, None], ["0310", None, 310, None]])
    d = las_ssyk_isco(p)
    assert set(d.isco4) == {"0110", "0310"}
    assert set(d.ssyk4) == {"0110", "0310"}


def test_rubrikraden_soks_upp(tmp_path):
    """Antalet metadatarader varierar mellan SCB:s utgåvor. En fast hoppning
    går sönder vid nästa."""
    p = str(tmp_path / "n.xlsx")
    with pd.ExcelWriter(p) as w:
        pd.DataFrame([["titel"], [None], [None], [None], [None],
                      ["SSYK 2012 kod", None, "ISCO-08 kod"],
                      ["1211", None, "1211"]]).to_excel(
            w, sheet_name="Nyckel", header=False, index=False)
    d = las_ssyk_isco(p)
    assert d.to_dict("records") == [{"ssyk4": "1211", "isco4": "1211"}]


def test_utan_rubrikrad_kastar(tmp_path):
    p = str(tmp_path / "n.xlsx")
    with pd.ExcelWriter(p) as w:
        pd.DataFrame([["a", "b"], ["1", "2"]]).to_excel(
            w, sheet_name="Nyckel", header=False, index=False)
    with pytest.raises(ValueError):
        las_ssyk_isco(p)


# ---------------------------------------------------------------------------
# ESCO-crosswalken
# ---------------------------------------------------------------------------
def test_matchvikterna_styr_urvalet(tmp_path):
    """broadMatch är den största posten i filen och den vagaste: chief
    operating officer står som broadMatch till Chief Executives, vilket ser ut
    som motsatt riktning mot SKOS-konventionen."""
    pc, pe = str(tmp_path / "c.csv"), str(tmp_path / "e.csv")
    _crosswalk(pc, [
        ["11-1011.00", "t", "d", "http://data.europa.eu/esco/occupation/A", "a", "d", "exactMatch"],
        ["11-1021.00", "t", "d", "http://data.europa.eu/esco/occupation/A", "a", "d", "broadMatch"],
    ])
    _esco(pe, [{"conceptUri": "http://data.europa.eu/esco/occupation/A",
                "iscoGroup": "1120", "preferredLabel": "a"}])
    d = las_esco_onet(pc, pe)
    assert set(d.onet_code) == {"11-1011.00"}
    # ...men vikterna går att ändra.
    d2 = las_esco_onet(pc, pe, matchvikter={**MATCHVIKTER, "broadMatch": 1.0})
    assert set(d2.onet_code) == {"11-1011.00", "11-1021.00"}


def test_isco_rader_tas_med_utan_omvag(tmp_path):
    """43 av 4 253 rader pekar direkt på en ISCO-grupp, C2611 -> 261."""
    pc, pe = str(tmp_path / "c.csv"), str(tmp_path / "e.csv")
    _crosswalk(pc, [["23-1011.00", "t", "d",
                     "http://data.europa.eu/esco/isco/C2611", "j", "d", "exactISCO"]])
    _esco(pe, [{"conceptUri": "x", "iscoGroup": "1120", "preferredLabel": "a"}])
    d = las_esco_onet(pc, pe)
    assert d.to_dict("records") == [{"isco3": "261", "onet_code": "23-1011.00",
                                     "vikt": 1.0}]


def test_okand_esco_uri_utesluts(tmp_path):
    """Versionsdrift: crosswalken är byggd mot ESCO v1.1.0. I v1.2.1 saknas
    tre av 4 210 URI:er."""
    pc, pe = str(tmp_path / "c.csv"), str(tmp_path / "e.csv")
    _crosswalk(pc, [["11-1011.00", "t", "d",
                     "http://data.europa.eu/esco/occupation/SAKNAS", "a", "d",
                     "exactMatch"]])
    _esco(pe, [{"conceptUri": "http://data.europa.eu/esco/occupation/A",
                "iscoGroup": "1120", "preferredLabel": "a"}])
    assert las_esco_onet(pc, pe).empty


# ---------------------------------------------------------------------------
# Den härledda tabellen
# ---------------------------------------------------------------------------
def _enkel():
    nyckel = pd.DataFrame([{"ssyk4": "1211", "isco4": "1211"},
                           {"ssyk4": "1212", "isco4": "1212"}])
    eo = pd.DataFrame([{"isco3": "121", "onet_code": "A", "vikt": 3.0},
                       {"isco3": "121", "onet_code": "B", "vikt": 1.0}])
    return nyckel, eo


def test_andelarna_summerar_till_ett_per_ssyk3():
    cw = bygg_crosswalk(*_enkel())
    summor = cw.groupby("occupation_code").share.sum()
    assert summor.to_numpy() == pytest.approx(1.0)


def test_vikterna_inom_isco_gruppen_bevaras():
    cw = bygg_crosswalk(*_enkel()).set_index("onet_code")
    assert cw.loc["A", "share"] == pytest.approx(0.75)
    assert cw.loc["B", "share"] == pytest.approx(0.25)


def test_ssyk4_med_flera_isco_delar_vikten():
    """Antagande 2: SCB publicerar inga andelar, så en SSYK4 som pekar på två
    ISCO-koder ger halva vikten åt vardera."""
    nyckel = pd.DataFrame([{"ssyk4": "1120", "isco4": "1120"},
                           {"ssyk4": "1120", "isco4": "1420"}])
    eo = pd.DataFrame([{"isco3": "112", "onet_code": "A", "vikt": 1.0},
                       {"isco3": "142", "onet_code": "B", "vikt": 1.0}])
    cw = bygg_crosswalk(nyckel, eo).set_index("onet_code")
    assert cw.loc["A", "share"] == pytest.approx(0.5)
    assert cw.loc["B", "share"] == pytest.approx(0.5)


def test_ssyk4_koderna_vags_lika_inom_gruppen():
    """Antagande 1: rätt vikt vore antalet anställda per SSYK4, men
    nattbefolkningen publiceras bara på SSYK3. En SSYK4 med många ISCO-koder
    ska inte få mer vikt än en med få."""
    nyckel = pd.DataFrame([
        {"ssyk4": "1211", "isco4": "1211"},
        {"ssyk4": "1212", "isco4": "1212"}, {"ssyk4": "1212", "isco4": "1213"},
    ])
    eo = pd.DataFrame([{"isco3": "121", "onet_code": "A", "vikt": 1.0}])
    cw = bygg_crosswalk(nyckel, eo)
    # Båda SSYK4 hamnar i samma ISCO3 och samma O*NET-kod: en rad, full vikt.
    assert len(cw) == 1 and cw.share.iloc[0] == pytest.approx(1.0)


def test_urval_av_onet_koder_normaliseras_om():
    """Geometrin har 1 016 koder; crosswalken 940. Faller en kod bort ska den
    kvarvarande vikten summera till ett ändå, annars får den SSYK3-gruppen
    systematiskt lägre total."""
    nyckel, eo = _enkel()
    cw = bygg_crosswalk(nyckel, eo, onet_koder={"A"})
    assert cw.share.to_numpy() == pytest.approx([1.0])


def test_ssyk3_utan_koppling_faller_bort_tyst_men_matbart():
    nyckel = pd.DataFrame([{"ssyk4": "9999", "isco4": "9999"}])
    eo = pd.DataFrame([{"isco3": "121", "onet_code": "A", "vikt": 1.0}])
    assert bygg_crosswalk(nyckel, eo).empty


# ---------------------------------------------------------------------------
# Produkten: SSYK-vikter per kommun x crosswalk -> O*NET-vikter
# ---------------------------------------------------------------------------
def _db_med_vikter(tmp_path, vikter, crosswalk):
    import sqlite3
    db = str(tmp_path / "w.sqlite3")
    conn = sqlite3.connect(db)
    pd.DataFrame(vikter).to_sql("occupation_weights_ssyk_by_municipality",
                                conn, index=False)
    pd.DataFrame(crosswalk).to_sql("ssyk3_onet_crosswalk", conn, index=False)
    conn.close()
    return db


def test_produkten_ger_onet_vikter(tmp_path):
    import sqlite3

    from core.database.load_ssyk_onet import load_onet_weights

    db = _db_med_vikter(tmp_path, [
        {"municipal_code": "2062", "occupation_code": "121", "weight": 0.6},
        {"municipal_code": "2062", "occupation_code": "234", "weight": 0.4},
    ], [
        {"occupation_code": "121", "onet_code": "A", "share": 0.75},
        {"occupation_code": "121", "onet_code": "B", "share": 0.25},
        {"occupation_code": "234", "onet_code": "C", "share": 1.0},
    ])
    load_onet_weights(db_path=db)
    conn = sqlite3.connect(db)
    d = pd.read_sql("SELECT * FROM occupation_weights_by_municipality",
                    conn).set_index("onet_code")
    conn.close()
    assert d.loc["A", "weight"] == pytest.approx(0.45)
    assert d.loc["B", "weight"] == pytest.approx(0.15)
    assert d.loc["C", "weight"] == pytest.approx(0.40)


def test_vikten_normaliseras_om_nar_en_grupp_saknar_koppling(tmp_path):
    """SSYK-grupper utan O*NET-koppling -- militära yrken och okänt yrke --
    ska inte ge kommunen lägre total. Den kvarvarande vikten fördelas om."""
    import sqlite3

    from core.database.load_ssyk_onet import load_onet_weights

    db = _db_med_vikter(tmp_path, [
        {"municipal_code": "2062", "occupation_code": "121", "weight": 0.5},
        {"municipal_code": "2062", "occupation_code": "011", "weight": 0.5},
    ], [{"occupation_code": "121", "onet_code": "A", "share": 1.0}])
    load_onet_weights(db_path=db)
    conn = sqlite3.connect(db)
    d = pd.read_sql("SELECT * FROM occupation_weights_by_municipality", conn)
    conn.close()
    assert d.weight.to_numpy() == pytest.approx([1.0])


def test_alla_kommuner_far_vikter_inte_bara_ett_scenario(tmp_path):
    """Modellen ska kunna byggas av vilka kommuner som helst. Avgränsningen
    sker när ett scenario väljer sina kommuner, inte i laddaren."""
    import sqlite3

    from core.database.load_ssyk_onet import load_onet_weights

    db = _db_med_vikter(tmp_path, [
        {"municipal_code": k, "occupation_code": "121", "weight": 1.0}
        for k in ("0180", "1280", "2062", "2584")
    ], [{"occupation_code": "121", "onet_code": "A", "share": 1.0}])
    load_onet_weights(db_path=db)
    conn = sqlite3.connect(db)
    d = pd.read_sql("SELECT * FROM occupation_weights_by_municipality", conn)
    conn.close()
    assert set(d.municipal_code) == {"0180", "1280", "2062", "2584"}


def test_kolumnerna_ar_de_register_profile_laser():
    """_register_profile gör SELECT onet_code, weight, year FROM
    occupation_weights_by_municipality WHERE municipal_code = ?. Saknas en
    kolumn faller den tyst tillbaka på SNI-vägen."""
    import inspect

    from core.database import load_ssyk_onet

    kalla = inspect.getsource(load_ssyk_onet.load_onet_weights)
    assert 'to_sql("occupation_weights_by_municipality"' in kalla
    for kol in ("municipal_code", "onet_code", "weight"):
        assert kol in kalla
