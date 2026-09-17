"""
fetch_data.py
-------------
Hämtar WORM:s källdata från rätt internetkällor till data/ och onet_data/.
Manifestdrivet: varje målfil har en källtyp. Kör sedan scripts/create_database.py
för att bygga data/worm.sqlite3 ur de hämtade filerna.

Källtyper
---------
  onet_zip   : hela O*NET-databasen som ZIP, extrahera utvalda .txt  (FUNGERAR DIREKT)
  scb_px     : SCB-statistiktabell via PxWebApi v2 (GET, fråga i URL:en)
  scb_geo    : SCB öppen geodata, direkt GPKG-URL eller WFS           (FYLL I url / lager)
  derived    : produceras av modellen/create_database.py             (HÄMTAS EJ)

Beroenden: requests  (pip install requests)
Geodata via WFS kan dessutom kräva att GeoServer-instansen stödjer GPKG-output;
annars ladda GeoJSON och konvertera, eller använd den statiska GPKG-länken.
"""
import os
import re
import io
import json
import zipfile
import requests

ONET_DIR = "onet_data"
DATA_DIR = "data"

# Aktuell O*NET-release (pappret använde 30.1; senaste är 30.3). Mönster: db_<major>_<minor>_text.zip
ONET_DB_VERSION = "30_3"
ONET_ZIP_URL = f"https://www.onetcenter.org/dl_files/database/db_{ONET_DB_VERSION}_text.zip"

# PxWebApi v2, som SCB släppte i statistikdatabasen i oktober 2025 och som
# ersätter v1. Uttagen görs med GET och hela frågan ligger i URL:en. Gränserna
# är 150 000 celler per uttag och 30 anrop per tio sekunder, räknat per
# IP-adress -- alltså delade med kollegor på samma arbetsplats.
#
# Tabellerna nås via ett stabilt id (TABnnnn) i stället för v1:s ämnesstig
# (BE/BE0101/BE0101A/BefolkningNy). Stigen ändrades när databasen omstrukturerades;
# id:t gör det inte. Specifikationen: github.com/PxTools/PxApiSpecs (PxAPI-2.yml).
SCB_API2_BASE = "https://statistikdatabasen.scb.se/api/v2"

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

    # --- SCB statistik via PxWebApi v2 ------------------------------------
    # En post behöver "table_query" (eller ett låst "table_id") och ett
    # "query_fn" som bygger frågan ur tabellens metadata.
    # Folkmängd per ettårsklass och kommun. Ålderspyramiden som
    # startpopulationens åldrar dras ur (core/database/load_population_age.py).
    #
    # Frågan byggs ur tabellens EGEN metadata, inte ur en handskriven
    # värdemängd: metadatan listar kommunkoderna och ettårsklasserna rakt av.
    #
    # Tabellen slutar vid 2024. Statistiken för 2025 och framåt ligger i
    # BefolkningCKM, som är röjandeskyddad med Cell Key Method: cellvärdena är
    # störda, och SCB påpekar att osäkerheten adderas när värden summeras.
    # Uppstarten tar därför 2024 ur den ostörda tabellen, som dessutom bär
    # hela historiken 1968-2024 som befolkningsbanan behöver.
    {
        "type": "scb_px",
        "dest": os.path.join(DATA_DIR, "Folkmangd kommun alder.csv"),
        # Tabell-id:t är verifierat i en körning: sökningen gav TAB638, och
        # metadatan för det id:t har rätt dimensioner. Låst här sparar det ett
        # anrop och gör uttaget oberoende av hur sökningen rankar träffar.
        # Slutar id:t gälla ger API:et 404, och då tar "table_query" vid om
        # raden nedan tas bort.
        "table_id": "TAB638",
        "table_query": "Folkmängden efter region, civilstånd, ålder och kön",
        "query_fn": "befolkning_per_alder",
        "query_args": {"ar": "2024"},
    },
    # Arbetskraft och befolkning per åldersklass och kommun (BAS, slutlig
    # årsstatistik). Underlaget för vilka årskullar arbetskraften bor i.
    # TAB2921 är verifierad i en körning: rätt dimensioner, år 2020-2024.
    # Den preliminära årstabellen (TAB5655) täcker även 2025 men har samma
    # åldersindelning, så den ger inget mer för det här ändamålet.
    {
        "type": "scb_px",
        "dest": os.path.join(DATA_DIR, "Arbetskraft kommun alder.csv"),
        "table_id": "TAB2921",
        "table_query": "Arbetsmarknadsstatus efter region, kön, ålder och "
                       "födelseregion. Slutlig statistik",
        "query_fn": "arbetskraft_per_alder",
        "query_args": {"ar": "2024"},
    },
    # Stubbar – fyll i "table_query" och en "query_fn" i QUERY_BUILDERS:
    {"type": "scb_px", "dest": os.path.join(DATA_DIR, "employment_municipality_sni_2020.csv"),
     "table_query": None},
    {"type": "scb_px", "dest": os.path.join(DATA_DIR, "scb_sysselsatta_deso.csv"),
     "table_query": None},
    {"type": "scb_px", "dest": os.path.join(DATA_DIR, "scb_population_deso_2024.csv"),
     "table_query": None},

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


def _som_utf8(r):
    """Svarets kropp som UTF-8.

    Statistikdatabasens CSV kommer i latin-1 när svaret bär klartext.
    Befolkningsuttaget märktes inte av det: med enbart koder innehåller filen
    inga å, ä eller ö och är därmed giltig UTF-8 av en slump.

    Provningsordningen kan inte vändas. En UTF-8-fil avkodad som latin-1 ger
    INGET fel utan tyst fel text, medan en latin-1-fil avkodad som UTF-8
    alltid ger UnicodeDecodeError. Att pröva UTF-8 först kan alltså aldrig
    förstöra en fil som redan är UTF-8; motsatt ordning kan.
    """
    try:
        r.content.decode("utf-8")
        return r.content
    except UnicodeDecodeError:
        pass
    for kodning in (r.encoding, "cp1252", "iso-8859-1"):
        if not kodning or kodning.lower().replace("_", "-") == "utf-8":
            continue
        try:
            text = r.content.decode(kodning)
        except (UnicodeDecodeError, LookupError):
            continue
        print(f"  (svaret var {kodning}, skrivs som utf-8)")
        return text.encode("utf-8")
    raise ValueError("Kan inte avkoda svaret: varken utf-8, "
                     f"{r.encoding} eller latin-1")


def _kontrollera(r, vad):
    """Höjer fel med API:ets egen förklaring, inte bara statuskoden.

    PxWebApi v2 svarar på fel med ProblemDetails: en JSON med title och detail
    som säger vad som var fel med uttaget. requests raise_for_status kastar
    bort den, och kvar blir "400 Client Error" utan besked om vilken variabel
    eller vilket värde som inte dög.
    """
    if r.ok:
        return
    besked = ""
    try:
        d = r.json()
        besked = " | ".join(str(d[k]) for k in ("title", "detail", "status")
                            if d.get(k))
    except Exception:
        besked = r.text[:300].replace("\n", " ")
    raise requests.HTTPError(f"{r.status_code} vid {vad}: {besked or '(tom kropp)'} "
                             f"[{r.url[:200]}]", response=r)


def valj_tabell(svar, ar, krav=("region", "ålder")):
    """Tabell-id ur ett /tables-svar.

    Sökningen ger flera träffar -- folkmängd finns per månad, per distrikt,
    efter födelseland och så vidare. En träff duger bara om den har alla
    variabler vi behöver och täcker året. Blir det inte exakt en kvar kastas
    ett fel som listar kandidaterna, så att id:t kan låsas i manifestet i
    stället för att sökningen gissar åt oss.
    """
    kandidater = []
    for t in svar.get("tables", []):
        namn = [str(n).lower() for n in t.get("variableNames", [])]
        if not all(any(k in n for n in namn) for k in krav):
            continue
        forsta, sista = str(t.get("firstPeriod", "")), str(t.get("lastPeriod", ""))
        if forsta and sista and not (forsta <= str(ar) <= sista):
            continue
        if t.get("discontinued"):
            continue
        kandidater.append(t)
    if len(kandidater) == 1:
        return kandidater[0]["id"]
    lista = "; ".join(f"{t['id']}: {t.get('label') or t.get('description')}"
                      for t in kandidater) or "inga"
    raise ValueError(f"sökningen gav {len(kandidater)} tabeller som täcker {ar} "
                     f"med {krav} ({lista}). Lås en av dem med \"table_id\" i "
                     "manifestet.")


def bygg_befolkningsuttag(meta, ar=None):
    """Frågesträngen för folkmängd per kommun och ettårsklass, ur tabellens
    metadata (json-stat2 från /tables/{id}/metadata).

    KOMMUNERNA. Region-dimensionen blandar riket ("00"), länen (tvåsiffriga)
    och kommunerna (fyrsiffriga) i samma kategorilista. Hämtas allt med "*"
    kommer alla tre nivåerna med, och summeras de av misstag räknas varje
    invånare tre gånger.

    ÅLDRARNA. Kategorin "tot" ligger i samma lista som ettårsklasserna.

    CIVILSTÅND OCH KÖN utelämnas. Båda har elimination = true, alltså
    summerar SCB över dem. Modellen använder ingendera.

    KODER, INTE KLARTEXT. outputFormatParams=UseCodes ger "2062" i stället för
    "Mora". Läsaren behöver kommunkoden som nyckel mot resten av databasen.

    Returnerar frågesträngens parametrar och selektionen som POST-kropp. Som
    GET blev URL:en 2 900 tecken med 290 kommunkoder och 101 ettårsklasser
    uppräknade, och API:et svarade 404: IIS avvisar query-strängar över 2 048
    tecken, och gör det med den koden i stället för med 414. Selektionen
    ligger därför i kroppen, vilket specifikationen har en POST-variant för.
    Historikuttaget, som räknar upp fler år, hade träffat samma vägg.
    """
    dim = meta.get("dimension", {})
    def kategorier(namn):
        return list(dim.get(namn, {}).get("category", {}).get("index", {}).keys())

    kommuner = [k for k in kategorier("Region") if len(k) == 4 and k.isdigit()]
    aldrar = [a for a in kategorier("Alder") if a != "tot"]
    tider = kategorier("Tid")
    if not kommuner or not aldrar:
        raise ValueError("metadatan saknar kommuner eller ettårsklasser")
    tid = str(ar) if ar is not None else (tider[-1] if tider else None)
    if tider and tid not in tider:
        raise ValueError(f"året {tid} finns inte i tabellen "
                         f"({tider[0]}-{tider[-1]})")
    val = [{"variableCode": "Region", "valueCodes": kommuner},
           {"variableCode": "Alder", "valueCodes": aldrar},
           {"variableCode": "Tid", "valueCodes": [tid]}]
    innehall = kategorier("ContentsCode")
    if innehall:
        # Tabellen bär både folkmängd och folkökning. Utan valet får uttaget
        # bådadera, och läsaren hade tagit folkökningen för folkmängd i den
        # kolumn den råkar hamna.
        val.append({"variableCode": "ContentsCode", "valueCodes": [innehall[0]]})
    return {"params": {"lang": "sv", "outputFormat": "csv",
                       "outputFormatParams": "UseCodes"},
            "selection": {"selection": val,
                          # PLACERINGEN STYRS, annars hamnar Tid i rubriken
                          # tillsammans med innehållskoden: kolumnen hette
                          # "BE0101N1 2024" och året fanns inte som egen
                          # kolumn. Med Tid i stub blir formatet långt och
                          # förutsägbart -- en rad per kommun, ålder och år --
                          # vilket också är vad historikuttaget behöver när
                          # det räknar upp tjugofem år.
                          "placement": {"stub": ["Region", "Alder", "Tid"],
                                        "heading": ["ContentsCode"]}}}


def bygg_arbetskraftsuttag(meta, ar=None):
    """Arbetskraft och befolkning per åldersklass och kommun (BAS).

    KLASSERNA OCH AGGREGATEN. Femårsgrupperna räcker inte: ingen BAS-tabell
    bryter ut 65 och 66 som egna klasser, och de åldrarna avgör hur många som
    lämnar vid riktåldern. Aggregaten 16-64, 16-65 och 16-66 hämtas därför
    med, eftersom differenserna mellan dem ger just de två årskullarna. Att de
    överlappar femårsgrupperna är avsikten, inte ett misstag.

    TOTALERNA VÄLJS. Kön har värdet "1+2" och födelseregion "tot". Att hämta
    delarna och summera dem hade gett samma tal med sex gånger så många
    celler, och med röjandeskyddets avvikelse mellan total och delsumma
    ovanpå.

    TVÅ INNEHÅLL. Arbetskraften är täljaren och antal totalt är nämnaren, och
    båda ska komma ur samma tabell: deltagandet räknas mot SCB:s egen
    avgränsning, inte mot befolkningspyramiden, som avgränsar annorlunda.
    Rubrikerna måste därför säga vilken kolumn som är vilken, vilket
    UseCodesAndTexts ger. Med enbart UseCodes blir de två kolumnerna namngivna
    med koder som "000001OZ", och en förväxling skulle göra deltagandet till
    sin egen invers utan att något klagar.
    """
    dim = meta.get("dimension", {})

    def kategorier(namn):
        return list(dim.get(namn, {}).get("category", {}).get("index", {}).keys())

    def etikett(namn, kod):
        return dim.get(namn, {}).get("category", {}).get("label", {}).get(kod, "")

    kommuner = [k for k in kategorier("Region") if len(k) == 4 and k.isdigit()]
    klasser = [a for a in kategorier("Alder")
               if re.match(r"^0?\d{2}-\d{2}$", a) and a not in ("15-19", "15-74")]
    behovs = {"16-64", "16-65", "16-66"}
    if not kommuner or not behovs <= set(klasser):
        raise ValueError(f"metadatan saknar kommuner eller aggregaten {sorted(behovs)}")
    tider = kategorier("Tid")
    tid = str(ar) if ar is not None else (tider[-1] if tider else None)
    if tider and tid not in tider:
        raise ValueError(f"året {tid} finns inte i tabellen ({tider[0]}-{tider[-1]})")

    innehall = []
    for kod in kategorier("ContentsCode"):
        namn = etikett("ContentsCode", kod).lower()
        if "arbetskraften" in namn or namn == "antal totalt":
            innehall.append(kod)
    if len(innehall) != 2:
        raise ValueError("hittar inte både arbetskraften och antal totalt bland "
                         f"innehållen: {[etikett('ContentsCode', k) for k in kategorier('ContentsCode')]}")

    val = [{"variableCode": "Region", "valueCodes": kommuner},
           {"variableCode": "Alder", "valueCodes": klasser},
           {"variableCode": "ContentsCode", "valueCodes": innehall},
           {"variableCode": "Tid", "valueCodes": [tid]}]
    for namn, total in (("Kon", "1+2"), ("Fodelseregion", "tot")):
        if total in kategorier(namn):
            val.append({"variableCode": namn, "valueCodes": [total]})
    return {"params": {"lang": "sv", "outputFormat": "csv",
                       "outputFormatParams": "UseCodesAndTexts"},
            "selection": {"selection": val,
                          "placement": {"stub": ["Region", "Alder", "Tid"],
                                        "heading": ["ContentsCode"]}}}


QUERY_BUILDERS = {"befolkning_per_alder": bygg_befolkningsuttag,
                  "arbetskraft_per_alder": bygg_arbetskraftsuttag}


def fetch_scb_px(item):
    """Hämtar en tabell ur statistikdatabasen med PxWebApi v2.

    Tre GET: sök fram tabell-id (om det inte är låst i manifestet), hämta
    tabellens metadata, hämta data med frågan som byggts ur metadatan.
    """
    if not item.get("table_id") and not item.get("table_query"):
        print(f"[SCB] HOPPAR ÖVER {item['dest']} – fyll i \"table_query\" och \"query_fn\".")
        return
    os.makedirs(os.path.dirname(item["dest"]), exist_ok=True)
    ar = item.get("query_args", {}).get("ar")
    tabell = item.get("table_id")
    if not tabell:
        fraga = item["table_query"]
        print(f"[SCB] söker tabell: {fraga}")
        r = requests.get(f"{SCB_API2_BASE}/tables",
                         params={"query": fraga, "lang": "sv", "pageSize": 50},
                         timeout=60)
        _kontrollera(r, "tabellsökning")
        tabell = valj_tabell(r.json(), ar)
        print(f"  tabell {tabell}")

    r = requests.get(f"{SCB_API2_BASE}/tables/{tabell}/metadata",
                     params={"lang": "sv"}, timeout=60)
    _kontrollera(r, "metadata")
    uttag = QUERY_BUILDERS[item["query_fn"]](r.json(), ar=ar)

    url = f"{SCB_API2_BASE}/tables/{tabell}/data"
    print(f"[SCB] POST {url}")
    r = requests.post(url, params=uttag["params"], json=uttag["selection"],
                      timeout=300)
    _kontrollera(r, "data")
    with open(item["dest"], "wb") as f:
        f.write(_som_utf8(r))
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
