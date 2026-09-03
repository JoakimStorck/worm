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

    # --- Härledda filer: hämtas EJ, genereras av modellen ------------------
    {"type": "derived", "note": "onet_occupation_space-*.csv byggs av loader.load_onet_occupation_space (skill-PCA)."},
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


def fetch_scb_px(item):
    if item["path"].startswith("TODO"):
        print(f"[SCB-px] HOPPAR ÖVER {item['dest']} – fyll i 'path' och 'query'.")
        return
    os.makedirs(os.path.dirname(item["dest"]), exist_ok=True)
    url = f"{SCB_PX_BASE}/{item['path']}"
    print(f"[SCB-px] POST {url}")
    r = requests.post(url, json=item["query"], timeout=120)
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


def main():
    for item in MANIFEST:
        t = item["type"]
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
    main()
