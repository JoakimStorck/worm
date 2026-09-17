"""Arbetskraft och befolkning per åldersklass ur BAS.

Underlaget för vilka årskullar arbetskraften bor i. Utan det fördelas
arbetskraften platt över hela det arbetsföra intervallet, vilket lägger
omkring 800 personer i Ovansiljan i årskullar som knappt deltar och driver
upp avgångsflödet vid riktåldern.

Åldersklasserna och innehållskoderna nedan är hämtade ur ett verkligt
metadatasvar för TAB2921.
"""
import textwrap

import pytest

from core.database.load_participation import (las_arbetskraft_per_alder,
                                              normalisera_klass)
from scripts.fetch_data import bygg_arbetskraftsuttag


META = {
    "dimension": {
        "Region": {"category": {"index": {"00": 0, "20": 1, "2034": 2,
                                          "2039": 3, "2062": 4}}},
        "Kon": {"category": {"index": {"1": 0, "2": 1, "1+2": 2},
                             "label": {"1": "män", "2": "kvinnor",
                                       "1+2": "totalt"}}},
        "Alder": {"category": {"index": {
            "15-19": 0, "16-19": 1, "20-24": 2, "25-29": 3, "30-34": 4,
            "35-39": 5, "40-44": 6, "45-49": 7, "50-54": 8, "55-59": 9,
            "060-64": 10, "65-69": 11, "70-74": 12, "15-74": 13, "16-64": 14,
            "16-65": 15, "16-66": 16, "20-64": 17, "20-65": 18, "20-66": 19}}},
        "Fodelseregion": {"category": {"index": {"tot": 0, "in": 1, "ut": 2},
                                       "label": {"tot": "totalt"}}},
        "ContentsCode": {"category": {
            "index": {"000001PM": 0, "000001OZ": 1, "000001PN": 2,
                      "000001OX": 3},
            "label": {"000001PM": "antal sysselsatta",
                      "000001OZ": "antal sysselsatta och arbetslösa (arbetskraften)",
                      "000001PN": "antal totalt",
                      "000001OX": "arbetskraftsdeltagande"}}},
        "Tid": {"category": {"index": {"2023": 0, "2024": 1}}},
    },
}


def _koder(uttag, variabel):
    for v in uttag["selection"]["selection"]:
        if v["variableCode"] == variabel:
            return v["valueCodes"]
    return None


# ----------------------------------------------------------------------
# Uttaget
# ----------------------------------------------------------------------

def test_aggregaten_foljer_med():
    """Ingen BAS-tabell bryter ut 65 och 66 som egna klasser. Differenserna
    mellan 16-64, 16-65 och 16-66 är enda vägen dit, och de åldrarna bär
    utträdet."""
    v = _koder(bygg_arbetskraftsuttag(META), "Alder")
    assert {"16-64", "16-65", "16-66"} <= set(v)
    assert "16-19" in v and "65-69" in v and "70-74" in v


def test_femtonaringarna_utesluts():
    """15-19 överlappar 16-19 utan att tillföra något: modellen har ingen
    fjortonåring som fyller femton."""
    v = _koder(bygg_arbetskraftsuttag(META), "Alder")
    assert "15-19" not in v and "15-74" not in v


def test_totalerna_valjs_for_kon_och_fodelseregion():
    """Att hämta delarna och summera dem ger samma tal med sex gånger så
    många celler, plus röjandeskyddets avvikelse mellan total och delsumma."""
    u = bygg_arbetskraftsuttag(META)
    assert _koder(u, "Kon") == ["1+2"]
    assert _koder(u, "Fodelseregion") == ["tot"]


def test_bade_taljare_och_namnare():
    """Deltagandet ska räknas mot SCB:s egen avgränsning, inte mot
    befolkningspyramiden, som avgränsar annorlunda."""
    v = _koder(bygg_arbetskraftsuttag(META), "ContentsCode")
    assert set(v) == {"000001OZ", "000001PN"}


def test_rubrikerna_bar_bade_kod_och_text():
    """Med enbart UseCodes heter de två värdekolumnerna "000001OZ" och
    "000001PN", och en förväxling gör deltagandet till sin egen invers utan
    att något klagar."""
    p = bygg_arbetskraftsuttag(META)["params"]
    assert p["outputFormatParams"] == "UseCodesAndTexts"


def test_bara_kommuner():
    assert _koder(bygg_arbetskraftsuttag(META), "Region") == ["2034", "2039", "2062"]


def test_saknade_aggregat_kastar():
    utan = {"dimension": dict(META["dimension"])}
    utan["dimension"]["Alder"] = {"category": {"index": {"16-19": 0, "20-24": 1}}}
    with pytest.raises(ValueError, match="16-64"):
        bygg_arbetskraftsuttag(utan)


# ----------------------------------------------------------------------
# Läsaren
# ----------------------------------------------------------------------

CSV = """\
"Region","Alder","Tid","000001OZ antal sysselsatta och arbetslösa (arbetskraften)","000001PN antal totalt"
"2062","16-19","2024",180,900
"2062","060-64","2024",1050,1300
"2062","16-64","2024",9200,12000
"2062","16-65","2024",9280,12250
"2062","16-66","2024",9330,12480
"2062","65-69","2024",420,1600
"2039","16-19","2024",60,300
"""


def _skriv(tmp_path, namn, text):
    p = tmp_path / namn
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return str(p)


def test_nollutfyllnaden_normaliseras():
    """SCB skriver "060-64" för att sortera rätt. Nollan skulle annars ge en
    egen klass som ingen matchar mot."""
    assert normalisera_klass("060-64") == "60-64"
    assert normalisera_klass("16-19") == "16-19"
    assert normalisera_klass("tot") is None


def test_laser_bada_vardekolumnerna(tmp_path):
    df = las_arbetskraft_per_alder(_skriv(tmp_path, "ak.csv", CSV))
    rad = df[(df.municipal_code == "2062") & (df.age_group == "16-64")]
    assert int(rad["in_labour_force"].iloc[0]) == 9200
    assert int(rad["total"].iloc[0]) == 12000
    assert set(df["municipal_code"]) == {"2062", "2039"}
    assert "60-64" in set(df["age_group"])


def test_kolumnerna_skiljs_pa_rubrik_inte_position(tmp_path):
    """En fil där de två värdekolumnerna bytt plats ska ge samma resultat.
    Position hade gjort deltagandet till sin egen invers."""
    omvand = CSV.replace(
        '"000001OZ antal sysselsatta och arbetslösa (arbetskraften)","000001PN antal totalt"',
        '"000001PN antal totalt","000001OZ antal sysselsatta och arbetslösa (arbetskraften)"')
    rader = [r.split(",") for r in omvand.strip().splitlines()[1:]]
    kastad = omvand.splitlines()[0] + "\n" + "\n".join(
        ",".join(r[:3] + [r[4], r[3]]) for r in rader)
    df = las_arbetskraft_per_alder(_skriv(tmp_path, "omvand.csv", kastad))
    rad = df[(df.municipal_code == "2062") & (df.age_group == "16-64")]
    assert int(rad["in_labour_force"].iloc[0]) == 9200
    assert int(rad["total"].iloc[0]) == 12000


def test_latin1_gar_att_lasa(tmp_path):
    """Statistikdatabasen gav filen i latin-1, och läsningen föll på 0xf6 --
    ö i "arbetslösa". Befolkningsuttaget märktes inte av det: med enbart
    koder innehåller den filen inga å, ä eller ö alls."""
    p = tmp_path / "latin.csv"
    p.write_bytes(textwrap.dedent(CSV).encode("iso-8859-1"))
    df = las_arbetskraft_per_alder(str(p))
    rad = df[(df.municipal_code == "2062") & (df.age_group == "16-64")]
    assert int(rad["in_labour_force"].iloc[0]) == 9200
    assert int(rad["total"].iloc[0]) == 12000


def test_en_rad_per_kommun_ar_och_klass(tmp_path):
    """Kommer kön eller födelseregion med som delar vid sidan av sina totaler
    är talen dubbelräknade."""
    dubbel = CSV + '"2062","16-64","2024",4600,6000\n'
    with pytest.raises(ValueError, match="totalvärdena"):
        las_arbetskraft_per_alder(_skriv(tmp_path, "dubbel.csv", dubbel))


def test_saknad_vardekolumn_ger_begripligt_fel(tmp_path):
    bara_en = '"Region","Alder","Tid","000001OZ antal ... (arbetskraften)"\n"2062","16-64","2024",9200\n'
    with pytest.raises(ValueError, match="UseCodesAndTexts"):
        las_arbetskraft_per_alder(_skriv(tmp_path, "en.csv", bara_en))
