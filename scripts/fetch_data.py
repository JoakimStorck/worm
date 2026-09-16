"""
fetch_data.py
-------------
Hämtar WORM:s källdata från rätt internetkällor till data/ och onet_data/.
Manifestdrivet: varje målfil har en källtyp. Kör sedan scripts/create_database.py
för att bygga data/worm.sqlite3 ur de hämtade filerna.

Källtyper
---------
  onet_zip   : hela O*NET-databasen som ZIP, extrahera utvalda .txt  (FUNGERAR DIREKT)
  scb_px     : SCB-statistiktabell via PxWebApi v1 (POST JSON-fråga)  (FYLL I tabell + query)
  scb_geo    : SCB öppen geodata, direkt GPKG-URL eller WFS           (FYLL I url / lager)
  derived    : produceras av modellen/create_database.py             (HÄMTAS EJ)

Beroenden: requests  (pip install requests)
Geodata via WFS kan dessutom kräva att GeoServer-instansen stödjer GPKG-output;
annars ladda GeoJSON och konvertera, eller använd den statiska GPKG-länken.
"""
import os
import io
import json
import zipfile
import requests

ONET_DIR = "onet_data"
DATA_DIR = "data"

# Aktuell O*NET-release (pappret använde 30.1; senaste är 30.3). Mönster: db_<major>_<minor>_text.zip
ONET_DB_VERSION = "30_3"
ONET_ZIP_URL = f"https://www.onetcenter.org/dl_files/database/db_{ONET_DB_VERSION}_text.zip"

# PxWebApi v1 (fungerar t.o.m. årsskiftet 2026/2027). Migrera senare till v2:
#   https://statistikdatabasen.scb.se/api/v2/  (se SCB:s v1->v2-konverterare)
SCB_PX_BASE = "https://api.scb.se/OV0104/v1/doris/sv/ssd"

# SCB:s WFS för öppen geodata (lagernamn fås ur GetCapabilities):
#   https://geodata.scb.se/geoserver/stat/wfs?service=WFS&version=2.0.0&request=GetCapabilities
SCB_WFS = "https://geodata.scb.se/geoserver/stat/wfs"


# ---------------------------------------------------------------------------
# Manifest: målfil -> källspecifikation
# Fyll i TODO-fälten med dina egna tabell-ID/urval (från SCB-gränssnittet) och
# de aktuella GPKG-länkarna från respektive SCB-datasetsida.
# ---------------------------------------------------------------------------
MANIFEST = [
    # --- O*NET (fungerar direkt) -------------------------------------------
    {"type": "onet_zip", "members": ["Occupation Data.txt", "Skills.txt"], "dest": ONET_DIR},

    # --- SCB statistik via PxWebApi (fyll i path + query) ------------------
    # Exempel, fullt ifyllt: kommunbefolkning (tabell BE0101 BefolkningNy).
    # 'path' är tabellvägen efter .../ssd/ ; 'query' är SCB:s JSON-fråga.
    {
        "type": "scb_px",
        "dest": os.path.join(DATA_DIR, "scb_population_example.csv"),
        "path": "BE/BE0101/BE0101A/BefolkningNy",
        "query": {
            "query": [
                {"code": "ContentsCode", "selection": {"filter": "item", "values": ["BE0101N1"]}},
                {"code": "Tid", "selection": {"filter": "item", "values": ["2024"]}},
            ],
            "response": {"format": "csv"},
        },
    },
    # Folkmängd per ettårsklass och kommun. Ålderspyramiden som
    # startpopulationens åldrar dras ur (core/database/load_population_age.py).
    #
    # Frågan byggs ur tabellens EGEN metadata av bygg_befolkningsfraga(), inte
    # ur en handskriven värdemängd. Ett tidigare utkast gissade
    # "vs:RegionKommun07EjAggr"; namnet gick inte att verifiera, och en
    # felaktig värdemängd ger 400 utan att säga vilken. Metadatan listar
    # koderna rakt av, så gissningen behövs inte.
    #
    # BefolkningNy slutar vid 2024. Statistiken för 2025 och framåt ligger i
    # BefolkningCKM, som är röjandeskyddad med Cell Key Method: cellvärdena är
    # störda, och SCB påpekar att osäkerheten adderas när värden summeras.
    # Uppstarten tar därför 2024 ur den ostörda tabellen, som dessutom bär
    # hela historiken 1968-2024 som befolkningsbanan behöver.
    {
        "type": "scb_px",
        "dest": os.path.join(DATA_DIR, "Folkmangd kommun alder.csv"),
        "path": "BE/BE0101/BE0101A/BefolkningNy",
        "query_fn": "befolkning_per_alder",
        "query_args": {"ar": "2024"},
    },
    # Stubbar – ersätt path/query med dina egna uttag (tom query = hela tabellen):
    {"type": "scb_px", "dest": os.path.join(DATA_DIR, "employment_municipality_sni_2020.csv"),
     "path": "TODO/AM/...", "query": {"query": [], "response": {"format": "csv"}}},
    {"type": "scb_px", "dest": os.path.join(DATA_DIR, "scb_sysselsatta_deso.csv"),
     "path": "TODO/AM/...", "query": {"query": [], "response": {"format": "csv"}}},
    {"type": "scb_px", "dest": os.path.join(DATA_DIR, "scb_population_deso_2024.csv"),
     "path": "TODO/BE/...", "query": {"query": [], "response": {"format": "csv"}}},

    # --- SCB geodata (direkt GPKG-URL eller WFS) ---------------------------
    # Föredra den statiska GPKG-länken från datasetsidan om du har den:
    {"type": "scb_geo", "dest": os.path.join(DATA_DIR, "DeSO_2025.gpkg"),
     "url": "TODO_DESO_GPKG_URL", "wfs_layer": "stat:DeSO.2025"},
    {"type": "scb_geo", "dest": os.path.join(DATA_DIR, "Tatorter_2023.gpkg"),
     "url": "TODO_TATORT_GPKG_URL", "wfs_layer": "stat:Tatort.2023"},
    {"type": "scb_geo", "dest": os.path.join(DATA_DIR, "Smaorter_2023.gpkg"),
     "url": "TODO_SMAORT_GPKG_URL", "wfs_layer": "stat:Smaort.2023"},
    {"type": "scb_geo", "dest": os.path.join(DATA_DIR, "Handelsomraden_2020.gpkg"),
     "url": "TODO_HANDEL_GPKG_URL", "wfs_layer": None},
    {"type": "scb_geo", "dest": os.path.join(DATA_DIR, "Verksamhetsomraden_2020.gpkg"),
     "url": "TODO_VERKSAMHET_GPKG_URL", "wfs_layer": None},
    {"type": "scb_geo", "dest": os.path.join(DATA_DIR, "Fritidshusomraden_2020.gpkg"),
     "url": "TODO_FRITIDSHUS_GPKG_URL", "wfs_layer": None},

    # SCB:s statistikdatabas, pendling mellan kommuner. Referensen för
    # share_hires_cross_municipality och för commute_cost_per_km.
    {"type": "scb_manual",
     "dest": os.path.join(DATA_DIR,
                          "Sysselsatta 15-74 år arbetsställekommun bostadskommun.csv"),
     "url": "https://www.statistikdatabasen.scb.se/ (Arbetsmarknad > "
            "Registerbaserad arbetsmarknadsstatistik > pendling)",
     "note": "Uttag med bostadskommun som rad och arbetsställekommun som "
             "kolumn, samtliga kommuner, kön totalt. Diagonalen måste ingå."},

    # --- Härledda filer: hämtas EJ, genereras av modellen ------------------
    {"type": "external_project", "dest": os.path.join(DATA_DIR, "geometry"),
     "note": "Uppgiftsrummet kommer INTE härifrån. Fyra CSV-filer plus "
             "radial_scale.json kopieras från geometry-of-works valda körning "
             "(openai text-embedding-3-large d3072 v30_1) och läses in med "
             "scripts/load_task_geometry.py --write. De går inte att hämta: "
             "de måste köras om i det projektet."},
    {"type": "derived", "note": "worm.sqlite3 byggs av scripts/create_database.py ur filerna ovan."},
]


# ---------------------------------------------------------------------------
# Hämtare per källtyp
# ---------------------------------------------------------------------------
def fetch_onet_zip(item):
    os.makedirs(item["dest"], exist_ok=True)
    print(f"[O*NET] hämtar {ONET_ZIP_URL}")
    r = requests.get(ONET_ZIP_URL, timeout=120)
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    # Filerna ligger under en toppmapp i zipen, t.ex. "db_30_3_text/Skills.txt"
    names = z.namelist()
    for member in item["members"]:
        match = next((n for n in names if n.endswith("/" + member) or n == member), None)
        if not match:
            print(f"  SAKNAS i zip: {member}")
            continue
        out = os.path.join(item["dest"], member)
        with z.open(match) as src, open(out, "wb") as dst:
            dst.write(src.read())
        print(f"  -> {out}")


def bygg_befolkningsfraga(meta, ar=None):
    """JSON-frågan för folkmängd per kommun och ettårsklass, ur tabellens
    metadata.

    Tre saker avgörs av metadatan i stället för att skrivas för hand.

    KOMMUNERNA. Region-listan blandar riket ("00"), länen (tvåsiffriga) och
    kommunerna (fyrsiffriga) i samma platta värdemängd. Hämtas allt med "*"
    kommer alla tre nivåerna med, och summeras de av misstag räknas varje
    invånare tre gånger. Läsaren skyddar mot det genom att kräva fyra siffror,
    men uttaget ska inte innehålla dem från början.

    ÅLDRARNA. Kategorin "tot" ligger i samma lista som ettårsklasserna och
    utesluts här.

    CIVILSTÅND OCH KÖN. Båda har elimination = true, alltså summerar SCB över
    dem när de utelämnas. Att räkna upp dem hade fyrdubblat respektive
    fördubblat antalet celler utan att tillföra något: modellen använder
    varken civilstånd eller kön.

    Storleken blir 290 kommuner * 101 ettårsklasser = 29 290 celler för ett
    år, med marginal till API:ets tak. Ett helt historikuttag måste däremot
    delas upp, ett år per fråga.
    """
    var = {v["code"]: v for v in meta["variables"]}
    kommuner = [k for k in var["Region"]["values"] if len(k) == 4 and k.isdigit()]
    aldrar = [a for a in var["Alder"]["values"] if a != "tot"]
    if not kommuner or not aldrar:
        raise ValueError("metadatan saknar kommuner eller ettårsklasser")
    tider = var["Tid"]["values"]
    tid = str(ar) if ar is not None else tider[-1]
    if tid not in tider:
        raise ValueError(f"året {tid} finns inte i tabellen "
                         f"({tider[0]}-{tider[-1]})")
    return {
        "query": [
            {"code": "Region", "selection": {"filter": "item", "values": kommuner}},
            {"code": "Alder", "selection": {"filter": "item", "values": aldrar}},
            {"code": "ContentsCode", "selection": {"filter": "item",
                                                   "values": ["BE0101N1"]}},
            {"code": "Tid", "selection": {"filter": "item", "values": [tid]}},
        ],
        # CSV3 OCH INTE CSV. Formatet csv ger variablernas KLARTEXTER, alltså
        # "Mora" utan kommunkod, och läsaren kräver fyra siffror: filen hade
        # gett noll rader. csv3 ger koderna, en rad per cell, med variabel-
        # namnen och tabellens id i rubrikraden.
        "response": {"format": "csv3"},
    }


QUERY_BUILDERS = {"befolkning_per_alder": bygg_befolkningsfraga}


def fetch_scb_px(item):
    if item["path"].startswith("TODO"):
        print(f"[SCB-px] HOPPAR ÖVER {item['dest']} – fyll i 'path' och 'query'.")
        return
    os.makedirs(os.path.dirname(item["dest"]), exist_ok=True)
    url = f"{SCB_PX_BASE}/{item['path']}"
    query = item.get("query")
    if query is None:
        # Frågan byggs ur tabellens metadata: GET på samma URL ger variabler
        # och deras värden.
        byggare = QUERY_BUILDERS[item["query_fn"]]
        print(f"[SCB-px] GET {url} (metadata)")
        m = requests.get(url, timeout=60)
        m.raise_for_status()
        query = byggare(m.json(), **item.get("query_args", {}))
    print(f"[SCB-px] POST {url}")
    r = requests.post(url, json=query, timeout=120)
    r.raise_for_status()
    with open(item["dest"], "wb") as f:
        f.write(r.content)
    print(f"  -> {item['dest']} ({len(r.content)} bytes)")


def fetch_scb_geo(item):
    os.makedirs(os.path.dirname(item["dest"]), exist_ok=True)
    url = item.get("url", "")
    if url and not url.startswith("TODO"):
        print(f"[SCB-geo] hämtar {url}")
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        with open(item["dest"], "wb") as f:
            f.write(r.content)
        print(f"  -> {item['dest']} ({len(r.content)} bytes)")
        return
    layer = item.get("wfs_layer")
    if layer:
        params = {
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": layer, "outputFormat": "application/geopackage+sqlite3",
        }
        print(f"[SCB-geo] WFS GetFeature {layer} (verifiera outputFormat mot GetCapabilities)")
        r = requests.get(SCB_WFS, params=params, timeout=300)
        if r.ok and r.content[:4] == b"SQLi":   # GPKG = SQLite-header
            with open(item["dest"], "wb") as f:
                f.write(r.content)
            print(f"  -> {item['dest']} ({len(r.content)} bytes)")
        else:
            print(f"  WFS gav inte GPKG (status {r.status_code}). Använd statisk GPKG-länk i 'url'.")
    else:
        print(f"[SCB-geo] HOPPAR ÖVER {item['dest']} – ingen 'url' och inget 'wfs_layer'.")


def main(bara=None):
    """Hämtar manifestet. `bara` är en delsträng som matchas mot målfilen:
    utan den hämtas allt, inklusive O*NET-zippen på flera hundra megabyte."""
    for item in MANIFEST:
        t = item["type"]
        mal = str(item.get("dest", ""))
        if bara and bara.lower() not in mal.lower():
            continue
        try:
            if t == "onet_zip":
                fetch_onet_zip(item)
            elif t == "scb_px":
                fetch_scb_px(item)
            elif t == "scb_geo":
                fetch_scb_geo(item)
            elif t == "derived":
                print(f"[härledd] {item['note']}")
        except Exception as e:
            print(f"  FEL ({t}): {e}")
    print("\nKlart. Kör därefter:  python scripts/create_database.py")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", help="hämta bara poster vars målfil innehåller "
                                   "denna delsträng, t.ex. --only Folkmangd")
    main(ap.parse_args().only)
