"""Uttaget för folkmängd per kommun och ettårsklass, PxWebApi v2.

Två utkast har varit fel före detta. Det första skrev värdemängden för hand
("vs:RegionKommun07EjAggr") -- ett namn som inte gick att verifiera. Det andra
byggde frågan ur metadatan men mot v1, som SCB ersatte i oktober 2025.

Strukturerna nedan följer PxAPI-2.yml och dess exempelfiler: /tables svarar med
en lista av tabeller med id, variableNames och period; /tables/{id}/metadata
svarar med json-stat2, där varje dimension har category.index.
"""
import pytest

from scripts.fetch_data import (_kontrollera, bygg_befolkningsuttag,
                                valj_tabell)


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

def _koder(uttag, variabel):
    for v in uttag["selection"]["selection"]:
        if v["variableCode"] == variabel:
            return v["valueCodes"]
    return None


def test_bara_kommuner():
    """Riket och länen hade räknat varje invånare tre gånger om de summerats."""
    assert _koder(bygg_befolkningsuttag(META), "Region") == \
        ["0114", "2034", "2039", "2062"]


def test_alderstotalen_utesluts():
    v = _koder(bygg_befolkningsuttag(META), "Alder")
    assert "tot" not in v and "100+" in v and len(v) == 4


def test_civilstand_och_kon_utelamnas():
    """Båda har elimination = true, så SCB summerar över dem. Att räkna upp
    dem hade fyrdubblat respektive fördubblat antalet celler utan att tillföra
    något modellen använder."""
    assert _koder(bygg_befolkningsuttag(META), "Civilstand") is None
    assert _koder(bygg_befolkningsuttag(META), "Kon") is None


def test_folkmangd_inte_folkokning():
    """Tabellen bär bådadera. Utan valet hade uttaget fått två värdekolumner."""
    assert _koder(bygg_befolkningsuttag(META), "ContentsCode") == ["BE0101N1"]


def test_koder_inte_klartext():
    """UseTexts hade gett "Mora" utan kommunkod, och koden är nyckeln mot
    resten av databasen."""
    p = bygg_befolkningsuttag(META)["params"]
    assert p["outputFormat"] == "csv"
    assert p["outputFormatParams"] == "UseCodes"


def test_selektionen_ligger_i_kroppen_inte_i_url_en():
    """Som GET blev URL:en 2 900 tecken med alla kommuner och ettårsklasser
    uppräknade, och IIS svarade 404 -- dess gräns för query-strängar är 2 048
    tecken. Frågesträngen bär därför bara format och språk."""
    p = bygg_befolkningsuttag(META)["params"]
    assert not any("valuecodes" in k.lower() for k in p)
    assert len("&".join(f"{k}={v}" for k, v in p.items())) < 100


def test_senaste_aret_om_inget_anges():
    assert _koder(bygg_befolkningsuttag(META), "Tid") == ["2024"]


def test_valt_ar():
    assert _koder(bygg_befolkningsuttag(META, ar=2023), "Tid") == ["2023"]


def test_ar_utanfor_tabellen_kastar():
    with pytest.raises(ValueError, match="2025"):
        bygg_befolkningsuttag(META, ar=2025)


# ----------------------------------------------------------------------
# Felbeskedet
# ----------------------------------------------------------------------

class _Svar:
    """Minimalt requests.Response-skal."""
    def __init__(self, status, json_data=None, text="", url="https://x/y"):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._json = json_data
        self.text = text
        self.url = url

    def json(self):
        if self._json is None:
            raise ValueError("ingen json")
        return self._json


def test_felet_bar_api_ets_egen_forklaring():
    """PxWebApi svarar med ProblemDetails. raise_for_status kastar bort den,
    och kvar blir "400 Client Error" utan besked om vilken variabel eller
    vilket värde som inte dög."""
    import requests
    svar = _Svar(400, {"title": "Illegal value", "detail": "Alder: 101 finns inte",
                       "status": 400})
    with pytest.raises(requests.HTTPError, match="Alder: 101 finns inte"):
        _kontrollera(svar, "data")


def test_fel_utan_json_bar_kroppen():
    import requests
    with pytest.raises(requests.HTTPError, match="Not Found"):
        _kontrollera(_Svar(404, None, text="<html>404 Not Found</html>"), "data")


def test_ok_passerar():
    assert _kontrollera(_Svar(200, {}), "data") is None


def test_tiden_ligger_i_stub_inte_i_rubriken():
    """Utan styrd placering hamnade Tid i rubriken tillsammans med
    innehållskoden: kolumnen hette "BE0101N1 2024" och året fanns inte som
    egen kolumn. Ett uttag över tjugofem år hade gett tjugofem sådana."""
    plac = bygg_befolkningsuttag(META)["selection"]["placement"]
    assert plac["stub"] == ["Region", "Alder", "Tid"]
    assert plac["heading"] == ["ContentsCode"]
