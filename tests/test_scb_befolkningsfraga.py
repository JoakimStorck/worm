"""JSON-frågan för folkmängd per kommun och ettårsklass.

Ett tidigare utkast skrev värdemängden för hand ("vs:RegionKommun07EjAggr").
Namnet gick inte att verifiera, och en felaktig värdemängd ger 400 utan att
säga vilken. Frågan byggs nu ur tabellens egen metadata.

Metadatan nedan är ett utdrag ur ett verkligt GET-svar från
api.scb.se/OV0104/v1/doris/sv/ssd/BE/BE0101/BE0101A/BefolkningNy: samma
struktur, kortade värdelistor.
"""
import pytest

from scripts.fetch_data import bygg_befolkningsfraga


META = {
    "title": "Folkmängd efter region, civilstånd, ålder, kön, tabellinnehåll och år",
    "variables": [
        {"code": "Region", "text": "region",
         # Platt lista: riket, län OCH kommuner om vartannat.
         "values": ["00", "01", "0114", "0115", "20", "2034", "2039", "2062"],
         "elimination": True},
        {"code": "Civilstand", "text": "civilstånd",
         "values": ["OG", "G", "ÄNKL", "SK"], "elimination": True},
        {"code": "Alder", "text": "ålder",
         "values": ["0", "1", "2", "99", "100+", "tot"], "elimination": True},
        {"code": "Kon", "text": "kön", "values": ["1", "2"], "elimination": True},
        {"code": "ContentsCode", "text": "tabellinnehåll",
         "values": ["BE0101N1", "BE0101N2"]},
        {"code": "Tid", "text": "år", "values": ["2022", "2023", "2024"],
         "time": True},
    ],
}


def _val(fraga, kod):
    for f in fraga["query"]:
        if f["code"] == kod:
            return f["selection"]["values"]
    return None


def test_bara_kommuner():
    """Riket och länen hade räknat varje invånare tre gånger om de summerats."""
    v = _val(bygg_befolkningsfraga(META), "Region")
    assert v == ["0114", "0115", "2034", "2039", "2062"]


def test_alderstotalen_utesluts():
    v = _val(bygg_befolkningsfraga(META), "Alder")
    assert "tot" not in v and "100+" in v and len(v) == 5


def test_civilstand_och_kon_utelamnas():
    """Båda har elimination = true, så SCB summerar över dem. Att räkna upp
    dem hade fyrdubblat respektive fördubblat antalet celler utan att tillföra
    något modellen använder."""
    fraga = bygg_befolkningsfraga(META)
    koder = [f["code"] for f in fraga["query"]]
    assert "Civilstand" not in koder and "Kon" not in koder
    assert koder == ["Region", "Alder", "ContentsCode", "Tid"]


def test_folkmangd_inte_folkokning():
    assert _val(bygg_befolkningsfraga(META), "ContentsCode") == ["BE0101N1"]


def test_senaste_aret_om_inget_anges():
    assert _val(bygg_befolkningsfraga(META), "Tid") == ["2024"]


def test_valt_ar():
    assert _val(bygg_befolkningsfraga(META, ar=2023), "Tid") == ["2023"]


def test_ar_utanfor_tabellen_kastar():
    """BefolkningNy slutar vid 2024; 2025 ligger i BefolkningCKM. Ett tyst
    fallback till närmaste år hade gett fel årgång utan att det syns."""
    with pytest.raises(ValueError, match="2025"):
        bygg_befolkningsfraga(META, ar=2025)


def test_csv3_och_inte_csv():
    """csv ger klartexter ("Mora"), csv3 ger koderna ("2062"). Läsaren kräver
    fyrsiffrig kommunkod, så csv hade gett en fil utan en enda giltig rad."""
    assert bygg_befolkningsfraga(META)["response"]["format"] == "csv3"
