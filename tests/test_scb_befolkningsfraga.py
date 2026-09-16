"""Uttaget för folkmängd per kommun och ettårsklass, PxWebApi v2.

Två utkast har varit fel före detta. Det första skrev värdemängden för hand
("vs:RegionKommun07EjAggr") -- ett namn som inte gick att verifiera. Det andra
byggde frågan ur metadatan men mot v1, som SCB ersatte i oktober 2025.

Strukturerna nedan följer PxAPI-2.yml och dess exempelfiler: /tables svarar med
en lista av tabeller med id, variableNames och period; /tables/{id}/metadata
svarar med json-stat2, där varje dimension har category.index.
"""
import pytest

from scripts.fetch_data import bygg_befolkningsuttag, valj_tabell


TABELLER = {
    "language": "sv",
    "tables": [
        {"id": "TAB0001", "label": "Folkmängden efter region, civilstånd, ålder och kön",
         "firstPeriod": "1968", "lastPeriod": "2024", "discontinued": False,
         "variableNames": ["region", "civilstånd", "ålder", "kön", "år"]},
        # Rätt variabler, fel period: 2025 och framåt ligger i en egen tabell.
        {"id": "TAB0002", "label": "Folkmängden efter region, civilstånd, ålder och kön. År 2025",
         "firstPeriod": "2025", "lastPeriod": "2025", "discontinued": False,
         "variableNames": ["region", "civilstånd", "ålder", "kön", "år"]},
        # Täcker året men saknar ålder.
        {"id": "TAB0003", "label": "Folkmängden per distrikt efter kön",
         "firstPeriod": "2015", "lastPeriod": "2024", "discontinued": False,
         "variableNames": ["region", "kön", "år"]},
    ],
}

META = {
    "version": "2.0", "class": "dataset",
    "label": "Folkmängden efter region, civilstånd, ålder, kön, tabellinnehåll och år",
    "id": ["Region", "Civilstand", "Alder", "Kon", "ContentsCode", "Tid"],
    "dimension": {
        # Platt lista: riket, län OCH kommuner om vartannat.
        "Region": {"label": "region", "category": {"index": {
            "00": 0, "01": 1, "0114": 2, "20": 3, "2034": 4, "2039": 5, "2062": 6}}},
        "Civilstand": {"category": {"index": {"OG": 0, "G": 1, "ÄNKL": 2, "SK": 3}}},
        "Alder": {"category": {"index": {"0": 0, "1": 1, "99": 2, "100+": 3, "tot": 4}}},
        "Kon": {"category": {"index": {"1": 0, "2": 1}}},
        "ContentsCode": {"category": {"index": {"BE0101N1": 0, "BE0101N2": 1}}},
        "Tid": {"category": {"index": {"2022": 0, "2023": 1, "2024": 2}}},
    },
}


# ----------------------------------------------------------------------
# Tabellvalet
# ----------------------------------------------------------------------

def test_valjer_tabellen_som_tacker_aret_och_har_alder():
    assert valj_tabell(TABELLER, "2024") == "TAB0001"
    assert valj_tabell(TABELLER, "2025") == "TAB0002"


def test_flera_eller_inga_traffar_kastar_med_kandidaterna():
    """Sökningen ska inte gissa åt oss. Felet listar kandidaterna så att id:t
    kan låsas i manifestet."""
    with pytest.raises(ValueError, match="TAB0001.*TAB0003"):
        valj_tabell(TABELLER, "2024", krav=("region",))


def test_nedlagd_tabell_valjs_inte():
    svar = {"tables": [dict(TABELLER["tables"][0], discontinued=True)]}
    with pytest.raises(ValueError, match="0 tabeller"):
        valj_tabell(svar, "2024")


# ----------------------------------------------------------------------
# Frågan
# ----------------------------------------------------------------------

def test_bara_kommuner():
    """Riket och länen hade räknat varje invånare tre gånger om de summerats."""
    p = bygg_befolkningsuttag(META)
    assert p["valuecodes[Region]"] == "0114,2034,2039,2062"


def test_alderstotalen_utesluts():
    v = bygg_befolkningsuttag(META)["valuecodes[Alder]"].split(",")
    assert "tot" not in v and "100+" in v and len(v) == 4


def test_civilstand_och_kon_utelamnas():
    """Båda har elimination = true, så SCB summerar över dem. Att räkna upp
    dem hade fyrdubblat respektive fördubblat antalet celler utan att tillföra
    något modellen använder."""
    p = bygg_befolkningsuttag(META)
    assert not any("Civilstand" in k or "Kon" in k for k in p)


def test_folkmangd_inte_folkokning():
    """Tabellen bär bådadera. Utan valet hade uttaget fått två värdekolumner."""
    assert bygg_befolkningsuttag(META)["valuecodes[ContentsCode]"] == "BE0101N1"


def test_koder_inte_klartext():
    """UseTexts hade gett "Mora" utan kommunkod, och koden är nyckeln mot
    resten av databasen."""
    p = bygg_befolkningsuttag(META)
    assert p["outputFormat"] == "csv"
    assert p["outputFormatParams"] == "UseCodes"


def test_senaste_aret_om_inget_anges():
    assert bygg_befolkningsuttag(META)["valuecodes[Tid]"] == "2024"


def test_valt_ar():
    assert bygg_befolkningsuttag(META, ar=2023)["valuecodes[Tid]"] == "2023"


def test_ar_utanfor_tabellen_kastar():
    with pytest.raises(ValueError, match="2025"):
        bygg_befolkningsuttag(META, ar=2025)
