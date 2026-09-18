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
    # Anställda i riket efter yrke (SSYK 2012, 3 siffror), utbildningsinriktning
    # (SUN 2020), ålder och kön. Underlaget för utbildningscirkelns position och
    # radie: vilka yrken de utbildade faktiskt arbetar i
    # (docs/utbildningsmodell.md, "Utbildningen som cirkel").
    #
    # TRE SIFFROR, INTE FYRA. TAB4446 har samma dimensioner på fyrsiffrig SSYK,
    # men databasens egen yrkesindelning
    # (occupation_weights_ssyk_by_municipality) är tresiffrig med samma 149
    # koder. Det fyrsiffriga uttaget hade behövt aggregeras ned igen.
    {
        "type": "scb_px",
        "dest": os.path.join(DATA_DIR, "Anstallda yrke utbildningsinriktning.csv"),
        "table_id": "TAB4359",
        "table_query": "Anställda i riket efter yrke (3-siffrig SSYK 2012), "
                       "utbildningsinriktning (SUN 2020), ålder och kön",
        "query_fn": "yrke_per_utbildningsinriktning",
        "query_args": {"ar": "2024"},
    },

    # Tvillingen till TAB4359: yrke gånger utbildningsNIVÅ, samma anställda.
    # Tillsammans med TAB655 underlaget för P(yrke, nivå, inriktning | ålder,
    # kön) (docs/utbildningsmodell.md, steg 4).
    {
        "type": "scb_px",
        "dest": os.path.join(DATA_DIR, "Anstallda yrke utbildningsniva.csv"),
        "table_id": "TAB4360",
        "query_fn": "yrke_per_utbildningsniva",
        "query_args": {"ar": "2024"},
    },
    # Befolkningen per utbildningsnivå och inriktning (TAB655): den tredje
    # marginalen och kohortandelarna för inträdet (6b).
    {
        "type": "scb_px",
        "dest": os.path.join(DATA_DIR, "Befolkning utbildningsniva inriktning.csv"),
        "table_id": "TAB655",
        "query_fn": "befolkning_per_utbildning",
        "query_args": {"ar": "2024"},
    },

    # Sysselsatta och arbetslösa 20-65 år per kommun och utbildningsnivå (BAS,
    # TAB6666, november): kommunens egen nivåfördelning för startpopulationen.
    {
        "type": "scb_px",
        "dest": os.path.join(DATA_DIR, "Arbetsmarknadsstatus kommun utbildningsniva.csv"),
        "table_id": "TAB6666",
        "query_fn": "arbetsmarknad_per_utbildning",
        "query_args": {"ar": "2024"},
    },

    # Anställda med arbetsplats i kommunen (DAGBEFOLKNING) efter yrke (SSYK3),
    # näringsgren (SNI 2007, grov nivå) och kön. Arbetsställenas bransch per
    # kommun, som i dag tas ur invånarnas bransch (employment_deso_sni,
    # nattbefolkning), och kommunens P(yrke | bransch), som i dag tas ur
    # riket (core/bransch.py). Finare SNI än grov nivå publiceras inte korsat
    # med yrke i någon tabell.
    {
        "type": "scb_px",
        "dest": os.path.join(DATA_DIR, "Anstallda dagbef yrke bransch kommun.csv"),
        "table_id": "TAB4436",
        "query_fn": "dagbef_yrke_bransch",
        "query_args": {"ar": "2024"},
    },

    # Lediga jobb per 100 anställningar och län, hela ekonomin (TAB6605,
    # 2024K2 och framåt). Skillnaden mellan pendlingsmatrisens sysselsatta och
    # modellens positioner (docs/stockarna.md). Den äldre serien (TAB4300-
    # TAB4305, till 2024K1) täcker bara näringslivet.
    {
        "type": "scb_px",
        "dest": os.path.join(DATA_DIR, "Lediga jobb per anstallning lan.csv"),
        "table_id": "TAB6605",
        "query_fn": "lediga_jobb_per_lan",
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


def bygg_yrkesutfallsuttag(meta, ar=None):
    """Anställda per yrke, utbildningsinriktning, ålder och kön (TAB4359).

    ETT ÅR I TAGET. Tabellen har 149 yrken × 10 inriktningar × 10 åldersklasser
    × 2 kön = 29 800 celler per år. Alla fem åren ger 149 000, vilket ligger
    under uttagsgränsen 150 000 med 1 200 cellers marginal -- alltså inom
    gränsen men utan utrymme för att SCB lägger till en åldersklass eller ett
    yrke. Året väljs därför explicit.

    ÅLDRARNA HÄMTAS ALLA, inte bara 25-29 som cirkelns position ska tas ur.
    Skillnaden mellan åldersklassernas centroider ÄR driften bort från
    utbildningen, och den går inte att mäta ur den klass man tar positionen ur.

    KÖNEN HÅLLS ISÄR. Yrkesutfallet per inriktning skiljer sig kraftigt mellan
    män och kvinnor inom samma inriktning, och modellen bär redan kön.
    Summering till totalen kan läsaren göra; det omvända går inte.

    KODER UTAN TEXT. Tabellen har ett enda innehåll (Antal), så den förväxling
    mellan två värdekolumner som tvingade arbetskraftsuttaget till
    UseCodesAndTexts finns inte här. Klartexten skulle dessutom skrivas in i
    VARJE cell och göra filen flera gånger större utan att läsaren blev av med
    ett enda uppslag: yrkes- och inriktningsnamnen står i metadatan.

    INGA TOTALRADER ATT FILTRERA. Yrkesdimensionens 149 koder är 148
    tresiffriga plus "0002" (yrke okänt), och inriktningens tio är 0-8 plus "9"
    (okänd utbildningsinriktning). Ingendera är en summa över de andra -- de är
    egna restposter. Läsaren ska alltså SUMMERA, inte filtrera, och måste själv
    avgöra vad den gör med de två okändklasserna.
    """
    dim = meta.get("dimension", {})

    def kategorier(namn):
        return list(dim.get(namn, {}).get("category", {}).get("index", {}).keys())

    yrken = kategorier("Yrke2012")
    inriktningar = kategorier("UtbinriktnSUN2020")
    aldrar = kategorier("Alder")
    if not (yrken and inriktningar and aldrar):
        raise ValueError("metadatan saknar yrke, utbildningsinriktning eller ålder")
    tider = kategorier("Tid")
    tid = str(ar) if ar is not None else (tider[-1] if tider else None)
    if tider and tid not in tider:
        raise ValueError(f"året {tid} finns inte i tabellen "
                         f"({tider[0]}-{tider[-1]})")

    val = [{"variableCode": "Yrke2012", "valueCodes": yrken},
           {"variableCode": "UtbinriktnSUN2020", "valueCodes": inriktningar},
           {"variableCode": "Alder", "valueCodes": aldrar},
           {"variableCode": "Kon", "valueCodes": kategorier("Kon")},
           {"variableCode": "Tid", "valueCodes": [tid]}]
    innehall = kategorier("ContentsCode")
    if innehall:
        val.append({"variableCode": "ContentsCode", "valueCodes": [innehall[0]]})
    return {"params": {"lang": "sv", "outputFormat": "csv",
                       "outputFormatParams": "UseCodes"},
            "selection": {"selection": val,
                          "placement": {"stub": ["Yrke2012", "UtbinriktnSUN2020",
                                                 "Alder", "Kon", "Tid"],
                                        "heading": ["ContentsCode"]}}}


UTTAGSGRANS = 150_000


def bygg_dagbef_yrke_bransch_uttag(meta, ar=None):
    """Anställda med arbetsplats i regionen (dagbef) per yrke, bransch och kön
    (TAB4436), ett år, uppdelat i flera uttag.

    FÖR STORT FÖR ETT UTTAG. 314 regioner × 149 yrken × 16 branscher × 2 kön
    är 1,5 miljoner celler per år, tio gånger uttagsgränsen. Regionerna delas
    därför i omgångar som var och en ryms under gränsen, och fetch_scb_px
    skriver dem till samma fil med rubriken en gång.

    ALLA REGIONER, inte scenariots kommuner. Modellen ska fungera för valfri
    kommunkombination, så filen täcker riket, länen, kommunerna och
    restposterna ("län okänt", "kommun okänd"). Läsaren väljer.

    KÖNEN HÅLLS ISÄR, som i TAB4359-uttaget: summering kan läsaren göra, det
    omvända går inte.

    KODER UTAN TEXT. Ett enda innehåll (Antal), och klartexten skulle skrivas
    i varje cell.

    FILEN, SOM DEN SER UT (2024, hämtad 2026-09-18). Rubriken är
    Region,Yrke2012,SNI2007,Kon,Tid,000006XZ -- värdekolumnen heter efter
    innehållskoden, inte efter året. 1 497 152 datarader, en per cell.
    INGA TOTALRADER: regionerna är en hierarki -- 00 riket, tvåsiffriga län,
    fyrsiffriga kommuner, 99 län okänt, 9999 kommun okänd -- och riket, summan
    av länen och summan av de fyrsiffriga koderna är alla 5 006 642. Läsaren
    VÄLJER nivå och summerar inte över nivåer. Restposter: yrke 0002 (okänt)
    och SNI 00 (okänd verksamhet). Branschgrupperna är desamma som i
    occupation_by_industry (A, B+C, D+E, ..., M+N, R+S+T+U).
    """
    dim = meta.get("dimension", {})

    def kategorier(namn):
        return list(dim.get(namn, {}).get("category", {}).get("index", {}).keys())

    regioner = kategorier("Region")
    yrken = kategorier("Yrke2012")
    branscher = kategorier("SNI2007")
    kon = kategorier("Kon")
    if not (regioner and yrken and branscher and kon):
        raise ValueError("metadatan saknar region, yrke, bransch eller kön")
    tider = kategorier("Tid")
    tid = str(ar) if ar is not None else (tider[-1] if tider else None)
    if tider and tid not in tider:
        raise ValueError(f"året {tid} finns inte i tabellen "
                         f"({tider[0]}-{tider[-1]})")
    per_region = len(yrken) * len(branscher) * len(kon)
    steg = UTTAGSGRANS // per_region
    if steg < 1:
        raise ValueError(f"en region ger {per_region} celler, över gränsen {UTTAGSGRANS}")
    innehall = kategorier("ContentsCode")
    uttag = []
    for i in range(0, len(regioner), steg):
        val = [{"variableCode": "Region", "valueCodes": regioner[i:i + steg]},
               {"variableCode": "Yrke2012", "valueCodes": yrken},
               {"variableCode": "SNI2007", "valueCodes": branscher},
               {"variableCode": "Kon", "valueCodes": kon},
               {"variableCode": "Tid", "valueCodes": [tid]}]
        if innehall:
            val.append({"variableCode": "ContentsCode", "valueCodes": [innehall[0]]})
        uttag.append({"selection": val,
                      "placement": {"stub": ["Region", "Yrke2012", "SNI2007", "Kon", "Tid"],
                                    "heading": ["ContentsCode"]}})
    return {"params": {"lang": "sv", "outputFormat": "csv",
                       "outputFormatParams": "UseCodes"},
            "selections": uttag}



def bygg_lediga_jobb_uttag(meta, ar=None):
    """Lediga jobb per 100 anställningar, hela ekonomin, per län (TAB6605).

    ALLA KVARTAL, inte ett år. Modellen har ingen säsong, och ett enskilt läns
    kvartal har en osäkerhetsmarginal på upp till 0,8 procentenheter kring en
    nivå omkring 2. Konsumenten tar medlet (docs/stockarna.md). ar ignoreras.

    LÄNEN VÄLJS. Regionerna blandar riket, län, riksområden och NUTS2; bara
    länen, tvåsiffriga koder utom 00, hämtas. Båda typerna (totalt och med
    omgående tillträde) och båda innehållen (värdet och dess
    osäkerhetsmarginal) hämtas; tabellen är liten.
    """
    dim = meta.get("dimension", {})

    def kategorier(namn):
        return list(dim.get(namn, {}).get("category", {}).get("index", {}).keys())

    lan = [k for k in kategorier("AARegion") if re.fullmatch(r"\d{2}", k) and k != "00"]
    if not lan or not kategorier("LedJobbTyp") or not kategorier("Tid"):
        raise ValueError("metadatan saknar län, typ av lediga jobb eller kvartal")
    val = [{"variableCode": "LedJobbTyp", "valueCodes": kategorier("LedJobbTyp")},
           {"variableCode": "AARegion", "valueCodes": lan},
           {"variableCode": "ContentsCode", "valueCodes": kategorier("ContentsCode")},
           {"variableCode": "Tid", "valueCodes": kategorier("Tid")}]
    return {"params": {"lang": "sv", "outputFormat": "csv",
                       "outputFormatParams": "UseCodesAndTexts"},
            "selection": {"selection": val}}



def _utbildningsuttag(meta, ar, dimensioner):
    """Gemensam form för utbildningstabellerna i steg 4 (TAB4359, TAB4360,
    TAB655): alla kategorier i dimensionerna, ett år, ett innehåll, bara
    koder. Samma skäl som för TAB4359 ovan: ett innehåll ger ingen risk för
    förväxlade värdekolumner, och klartext i varje cell hade bara gjort filen
    större."""
    dim = meta.get("dimension", {})

    def kategorier(namn):
        return list(dim.get(namn, {}).get("category", {}).get("index", {}).keys())

    saknas = [d for d in dimensioner if not kategorier(d)]
    if saknas:
        raise ValueError(f"metadatan saknar dimensionerna {saknas}")
    tider = kategorier("Tid")
    tid = str(ar) if ar is not None else (tider[-1] if tider else None)
    if tider and tid not in tider:
        raise ValueError(f"året {tid} finns inte i tabellen ({tider[0]}-{tider[-1]})")
    val = [{"variableCode": d, "valueCodes": kategorier(d)} for d in dimensioner]
    val.append({"variableCode": "Tid", "valueCodes": [tid]})
    innehall = kategorier("ContentsCode")
    if len(innehall) != 1:
        raise ValueError(f"väntade ett innehåll, fick {innehall}")
    val.append({"variableCode": "ContentsCode", "valueCodes": innehall})
    return {"params": {"lang": "sv", "outputFormat": "csv",
                       "outputFormatParams": "UseCodes"},
            "selection": {"selection": val,
                          "placement": {"stub": list(dimensioner) + ["Tid"],
                                        "heading": ["ContentsCode"]}}}


def bygg_yrke_utbildningsniva_uttag(meta, ar=None):
    """Anställda per yrke, utbildningsnivå (SUN 2020), ålder och kön (TAB4360).

    Tvillingen till TAB4359: samma anställda, samma yrken, åldrar och kön,
    med nivån i stället för inriktningen. Yrkestotalerna ska vara identiska
    i de två, och det prövas när databasen byggs (docs/utbildningsmodell.md,
    "Data för dragningen"). Nivåns åtta värden är 1-7 plus US (uppgift
    saknas), en restpost och ingen total."""
    return _utbildningsuttag(meta, ar, ["Yrke2012", "UtbNivaSun2020", "Alder", "Kon"])


def bygg_befolkning_utbildning_uttag(meta, ar=None):
    """Befolkningen 16-74 år per kön, ålder, nationell bakgrund, utbildningsnivå
    och utbildningsinriktning (TAB655).

    Den tredje marginalen, nivå gånger inriktning, och kohortandelarna för
    inträdet. HELA BEFOLKNINGEN och TIOÅRSKLASSER, inte anställda i
    femårsklasser som TAB4359 och TAB4360; skillnaden ska synas i läsaren,
    inte jämnas ut. Nationell bakgrund hålls isär: en fjärdedel av 25-34-
    åringarna är födda utomlands, och deras nivåer och okända uppgifter
    skiljer sig."""
    return _utbildningsuttag(meta, ar, ["Kon", "Alder", "NationellBakgrund",
                                        "UtbildningsNiva", "UtbinriktnSUN2020"])



def bygg_arbetsmarknad_utbildning_uttag(meta, ar=None):
    """Sysselsatta och arbetslösa 20-65 år per kommun och utbildningsnivå, BAS
    (TAB6666, preliminär månadsstatistik), november.

    Den fjärde marginalen i startpopulationens utbildning (6a-ii): rikets
    nivåfördelning givet yrke och ålder överskattar utbildningen i
    glesbygden -- Ovansiljans sysselsatta har 20,5 procent eftergymnasial
    utbildning om minst tre år mot 27,4 i modellen före rättelsen. NOVEMBER,
    som resten av BAS-underlaget. ar anger året; månaden är 11. Nivåerna är
    grupperade (21 förgymnasial, 61 eftergymnasial minst tre år inklusive
    forskarutbildning). Kommunerna väljs; län och riket tas inte med."""
    dim = meta.get("dimension", {})

    def kategorier(namn):
        return list(dim.get(namn, {}).get("category", {}).get("index", {}).keys())

    kommuner = [k for k in kategorier("Region") if re.fullmatch(r"\d{4}", k)]
    tid = f"{ar}M11"
    if tid not in kategorier("Tid"):
        raise ValueError(f"{tid} finns inte i tabellen")
    innehall = {"0000088H", "0000088A"}
    if not innehall <= set(kategorier("ContentsCode")):
        raise ValueError("sysselsatta eller arbetslösa saknas bland innehållen")
    val = [{"variableCode": "Region", "valueCodes": kommuner},
           {"variableCode": "Kon", "valueCodes": ["1+2"]},
           {"variableCode": "Alder", "valueCodes": ["20-65"]},
           {"variableCode": "UtbildningsNiva", "valueCodes": kategorier("UtbildningsNiva")},
           {"variableCode": "Fodelseregion", "valueCodes": ["tot"]},
           {"variableCode": "ContentsCode", "valueCodes": sorted(innehall)},
           {"variableCode": "Tid", "valueCodes": [tid]}]
    return {"params": {"lang": "sv", "outputFormat": "csv",
                       "outputFormatParams": "UseCodesAndTexts"},
            "selection": {"selection": val}}


QUERY_BUILDERS = {"befolkning_per_alder": bygg_befolkningsuttag,
                  "arbetskraft_per_alder": bygg_arbetskraftsuttag,
                  "yrke_per_utbildningsinriktning": bygg_yrkesutfallsuttag,
                  "dagbef_yrke_bransch": bygg_dagbef_yrke_bransch_uttag,
                  "lediga_jobb_per_lan": bygg_lediga_jobb_uttag,
                  "yrke_per_utbildningsniva": bygg_yrke_utbildningsniva_uttag,
                  "befolkning_per_utbildning": bygg_befolkning_utbildning_uttag,
                  "arbetsmarknad_per_utbildning": bygg_arbetsmarknad_utbildning_uttag}


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
    # Ett uttag som överstiger gränsen delas av byggaren i flera. De skrivs
    # till samma fil, och rubrikraden tas bara ur det första; annars står den
    # mitt i filen som en datarad.
    delar = uttag.get("selections") or [uttag["selection"]]
    with open(item["dest"], "wb") as f:
        for n, sel in enumerate(delar, 1):
            print(f"[SCB] POST {url}" + (f" ({n}/{len(delar)})" if len(delar) > 1 else ""))
            r = requests.post(url, params=uttag["params"], json=sel, timeout=300)
            _kontrollera(r, "data")
            kropp = _som_utf8(r)
            if n > 1:
                kropp = kropp.split(b"\n", 1)[1] if b"\n" in kropp else b""
            f.write(kropp)
    print(f"  -> {item['dest']} ({os.path.getsize(item['dest'])} bytes)")


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
