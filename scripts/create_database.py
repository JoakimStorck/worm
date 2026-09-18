import sys
import os
import locale
 
# Sätt rätt decimalpunkt för WKT
locale.setlocale(locale.LC_NUMERIC, "C")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import schema, loader
from core.log import log


DB_PATH = "data/worm.sqlite3"

def file_exists(path):
    if not os.path.exists(path):
        log(f"Varning: Filen saknas: {path}")
        return False
    return True

# Skapa databasens schema (tabeller)
log("Skapar/uppdaterar databasstruktur...")
schema.create_schema(DB_PATH)

# Ladda SCB-kommuner (CSV om ingen GPKG finns)
mun_csv = "data/scb_municipalities.csv"
if file_exists(mun_csv):
    loader.load_municipalities(mun_csv, db_path=DB_PATH)
else:
    log("OBS: Laddar inte kommuner, ingen CSV hittad.")

# Ladda handelsområden (GPKG)
handels_gpkg = "data/Handelsomraden_2020.gpkg"
if file_exists(handels_gpkg):
    loader.load_commercial_zones_gpkg(handels_gpkg, db_path=DB_PATH)

# Ladda verksamhetsområden (GPKG)
verksamhets_gpkg = "data/Verksamhetsomraden_2020.gpkg"
if file_exists(verksamhets_gpkg):
    loader.load_business_zones_gpkg(verksamhets_gpkg, db_path=DB_PATH)

# Ladda fritidshusområden (GPKG)
fritid_gpkg = "data/Fritidshusomraden_2020.gpkg"
if file_exists(fritid_gpkg):
    loader.load_leisure_house_zones_gpkg(fritid_gpkg, db_path=DB_PATH)

# Ladda småorter (GPKG)
smaort_gpkg = "data/Smaorter_2023.gpkg"
if file_exists(smaort_gpkg):
    loader.load_small_localities_gpkg(smaort_gpkg, db_path=DB_PATH)

# Ladda tätorter (GPKG)
tatort_gpkg = "data/Tatorter_2023.gpkg"
if file_exists(tatort_gpkg):
    loader.load_urban_areas_gpkg(tatort_gpkg, db_path=DB_PATH)

# Ladda DeSO (GPKG, om fil finns)
deso_gpkg = "data/DeSO_2025.gpkg"
if file_exists(deso_gpkg):
    loader.load_deso_gpkg(deso_gpkg, db_path=DB_PATH)

loader.update_deso_population_from_csv("data/scb_population_deso_2024.csv", db_path=DB_PATH)

# Ladda arbetsmarknadsdata på kommunnivå (CSV)
emp_mun_csv = "data/employment_municipality_sni_2020.csv"
if file_exists(emp_mun_csv):
    loader.load_employment_municipality_sni(emp_mun_csv, db_path=DB_PATH)
else:
    log("OBS: Laddar inte arbetsmarknadsdata på kommunnivå, filen saknas.")

# Ladda arbetsmarknadsdata på DeSO-nivå (CSV, om fil finns)
deso_emp_csv = "data/scb_sysselsatta_deso.csv"
if file_exists(deso_emp_csv):
    loader.load_employment_deso_sni(deso_emp_csv, db_path=DB_PATH, year=2023)
else:
    log("OBS: Laddar inte sysselsatta per DeSO, filen saknas.")

# Dagbefolkning per kommun, yrke och bransch (TAB4436): arbetsställenas
# branschandelar (core/bransch.py).
dagbef_csv = "data/Anstallda dagbef yrke bransch kommun.csv"
if file_exists(dagbef_csv):
    from core.database.load_dagbef import load_dagbef_yrke_bransch
    load_dagbef_yrke_bransch(dagbef_csv, db_path=DB_PATH)
else:
    log("OBS: Laddar inte dagbefolkning per yrke och bransch, filen saknas. "
        "Hämta den med: python scripts/fetch_data.py --only \"dagbef yrke bransch\"")

# Utbildningstabellerna för steg 4 (TAB4359, TAB4360, TAB655): marginalerna
# av P(yrke, nivå, inriktning | ålder, kön), docs/utbildningsmodell.md.
from core.database.load_utbildning import FILER as UTB_FILER, load_utbildning
utb_saknas = [f for f, _, _ in UTB_FILER.values() if not file_exists(f)]
if not utb_saknas:
    load_utbildning(db_path=DB_PATH)
else:
    log(f"OBS: Laddar inte utbildningstabellerna, filerna {utb_saknas} saknas. "
        "Hämta dem med: python scripts/fetch_data.py --only \"Anstallda yrke utbildning\" "
        "och --only \"Befolkning utbildning\".")

# Sysselsatta per kommun och utbildningsnivå (TAB6666): kommunens egen
# nivåfördelning för startpopulationens utbildning (6a-ii).
from core.database.load_utbildning import KOMMUN_FIL, load_arbetsmarknad_utbildning
if file_exists(KOMMUN_FIL):
    load_arbetsmarknad_utbildning(db_path=DB_PATH)
else:
    log("OBS: Laddar inte sysselsatta per kommun och utbildningsnivå, filen saknas. "
        "Hämta den med: python scripts/fetch_data.py --only \"Arbetsmarknadsstatus kommun utbildning\"")

# Inträdet (docs/intradet.md): studiedeltagande per ettårsklass (TAB3731) och
# utbildningsflöden per kommun (TAB6928).
from core.database.load_utbildning import FLODE_FIL, STUDIE_FIL, load_intradet
if file_exists(STUDIE_FIL) and file_exists(FLODE_FIL):
    load_intradet(db_path=DB_PATH)
else:
    log("OBS: Laddar inte inträdets tabeller, filerna saknas. Hämta dem med: "
        "python scripts/fetch_data.py --only studiedeltagande och --only Utbildningsfloden")

# Lediga jobb per 100 anställningar och län (TAB6605): skillnaden mellan
# pendlingsmatrisens sysselsatta och modellens positioner (docs/stockarna.md).
lediga_csv = "data/Lediga jobb per anstallning lan.csv"
if file_exists(lediga_csv):
    from core.database.load_lediga_jobb import load_lediga_jobb
    load_lediga_jobb(lediga_csv, db_path=DB_PATH)
else:
    log("OBS: Laddar inte lediga jobb per län, filen saknas. "
        "Hämta den med: python scripts/fetch_data.py --only \"Lediga jobb\"")

# Ladda O*NET-data (yrken och skills)
# O*NET:s råtabeller laddas inte längre. onet_occupations, onet_skills och
# occupation_skill_link lästes bara av skill-PCA:n, som var uppgiftsrummet
# innan inbäddningsgeometrin tog över, och av individual_history för
# yrkestitlar -- titlar som onet_occupation_space redan bär för varje kod
# modellen känner. Med dem borta går beroendet på onet_data/ med, och
# databasen kan byggas ur enbart filerna i data/.

# Uppgiftsrummet SKRIVS INTE HÄR. Tabellen onet_occupation_space ägs av
# scripts/load_task_geometry.py, som är den enda skrivare vars kolumner
# modellen faktiskt läser: scenariobuilder.get_geom_for_onet_code hämtar
# x_occ, y_occ, r_o och r_req. loader.load_onet_occupation_space skrev samma
# tabellnamn med helt andra kolumner (pc1, pc2, cluster, cluster_name, h) och
# 879 rader i stället för 1 016, och gjorde det med if_exists="replace".
# En körning av det här skriptet raderade alltså geometrin, och eftersom
# get_geom_for_onet_code ligger i try/except hade nästa simulering inte
# stannat -- den hade fallit tillbaka på reservvärden och producerat en
# körning som ser riktig ut.
if file_exists(os.path.join("data", "geometry")):
    log("Uppgiftsrummet laddas separat: python scripts/load_task_geometry.py --write")
else:
    log("OBS: data/geometry/ saknas — uppgiftsrummet kan inte byggas.")

# Ladda SCB:s pendlingsmatris. Två uttag duger och laddaren känner båda;
# det bredare och nyare tas först. Utan tabellen saknar
# share_hires_cross_municipality sin referens.
for pendel_csv in ("data/Sysselsatta 15-74 år arbetsställekommun bostadskommun.csv",
                   "data/Förvärvsarbetande 16-74 år pendlare över kommungräns "
                   "efter bostadskommun, arbetsställekommun, kön och år.csv"):
    if file_exists(pendel_csv):
        try:
            from core.database.load_commuting_matrix import load_commuting_matrix
            load_commuting_matrix(pendel_csv, db_path=DB_PATH)
            break
        except Exception as e:
            log(f"Fel vid laddning av pendlingsmatrisen ur {pendel_csv}: {e}")
else:
    log("OBS: Laddar inte commuting, ingen av SCB:s pendlingsfiler finns.")

# Ladda SCB:s arbetsmarknadsstatus per kommun. Referensen modellens
# arbetslöshet per kommun ställs mot i analysis.py.
ams_csv = "data/Arbetsmarknadsstatus Kommun.csv"
if file_exists(ams_csv):
    try:
        from core.database.load_commuting_matrix import load_arbetsmarknadsstatus
        load_arbetsmarknadsstatus(ams_csv, db_path=DB_PATH)
    except Exception as e:
        log(f"Fel vid laddning av arbetsmarknadsstatus: {e}")
else:
    log("OBS: Laddar inte labour_market_status, filen saknas.")

# Ladda SCB:s folkmängd per ettårsklass och kommun (BE0101). Underlaget för
# startpopulationens åldrar. Utan tabellen kastar generate_individuals.
for bef_csv in ("data/Folkmangd kommun alder.csv",
                "data/befolkning_kommun_alder.csv",
                "data/BE0101_folkmangd_alder_kommun.csv"):
    if file_exists(bef_csv):
        try:
            from core.database.load_population_age import load_population_by_age
            load_population_by_age(bef_csv, db_path=DB_PATH)
            break
        except Exception as e:
            log(f"Fel vid laddning av befolkning per ålder ur {bef_csv}: {e}")
else:
    log("OBS: Laddar inte population_by_age, ingen befolkningsfil per ålder "
        "finns. Hämta den med: python scripts/fetch_data.py --only Folkmangd "
        "-- utan den kan individernas ålder inte dras.")

# Ladda SCB:s arbetskraft per åldersklass och kommun (BAS). Underlaget för
# vilka årskullar arbetskraften bor i.
ak_csv = "data/Arbetskraft kommun alder.csv"
if file_exists(ak_csv):
    try:
        from core.database.load_participation import load_labour_force_by_age
        load_labour_force_by_age(ak_csv, db_path=DB_PATH)
    except Exception as e:
        log(f"Fel vid laddning av arbetskraft per ålder ur {ak_csv}: {e}")
else:
    log("OBS: Laddar inte labour_force_by_age, filen saknas. Hämta den med: "
        "python scripts/fetch_data.py --only Arbetskraft")

# Ladda yrkesregistret och skatta yrkesvikter per kommun med IPF.
riks_csv, lan_csv = "data/TAB4347_sv.csv", "data/TAB4441_sv.csv"
if file_exists(riks_csv) and file_exists(lan_csv):
    try:
        from core.database.load_yrkesregister import load_yrkesregister, load_yrkesvikter
        load_yrkesregister(riks_csv, lan_csv, db_path=DB_PATH)
        load_yrkesvikter(db_path=DB_PATH)
    except Exception as e:
        log(f"Fel vid laddning av yrkesregistret: {e}")
else:
    log("OBS: Laddar inte yrkesregistret, filerna saknas.")

# SSYK -> O*NET. Kräver att yrkesregistret och uppgiftsrummet redan är
# laddade, eftersom crosswalken avgränsas till de koder som faktiskt används.
nyckel_xlsx = "data/webb_nyckel_ssyk2012_isco-08_20160905.xlsx"
esco_cw = "data/ONET_(Occupations)_0_updated.csv"
esco_yrken = "data/esco_1.2.1/occupations_sv.csv"
if all(file_exists(f) for f in (nyckel_xlsx, esco_cw, esco_yrken)):
    try:
        from core.database.load_ssyk_onet import load_onet_weights, load_ssyk_onet
        load_ssyk_onet(nyckel_xlsx, esco_cw, esco_yrken, db_path=DB_PATH)
        load_onet_weights(db_path=DB_PATH)
    except Exception as e:
        log(f"Fel vid laddning av SSYK-O*NET-crosswalken: {e}")
else:
    log("OBS: Laddar inte ssyk3_onet_crosswalk, någon källfil saknas.")

# Ladda utbildningsnivåer från SCB (JSON)
edu_json = "data/Utbildningsnivaer_2024.json"
if file_exists(edu_json):
    loader.load_education_level_scb_json(edu_json, db_path=DB_PATH, year=2024)
else:
    log("OBS: Laddar inte utbildningsnivåer, filen saknas.")

# Ladda utbildningsnivåer från SCB (JSON)
sni_onet_path = "data/onet_sni_longform.csv"
if file_exists(sni_onet_path):
    loader.load_sni_onet_link(sni_onet_path, db_path=DB_PATH)
else:
    log(f"Not loading SNI-O*NET cross table, file {sni_onet_path} missing.")


log("Alla laddningar är färdiga.")

