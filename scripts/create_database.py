import sys
import os
import locale

# Sätt rätt decimalpunkt för WKT
locale.setlocale(locale.LC_NUMERIC, "C")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worm.database import schema, loader

DB_PATH = "data/worm.sqlite3"

def file_exists(path):
    if not os.path.exists(path):
        print(f"Varning: Filen saknas: {path}")
        return False
    return True

# Skapa databasens schema (tabeller)
print("Skapar/uppdaterar databasstruktur...")
schema.create_schema(DB_PATH)

# Ladda SCB-kommuner (CSV om ingen GPKG finns)
mun_csv = "data/scb_municipalities.csv"
if file_exists(mun_csv):
    loader.load_municipalities(mun_csv, db_path=DB_PATH)
else:
    print("OBS: Laddar inte kommuner, ingen CSV hittad.")

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

# Ladda arbetsmarknadsdata på kommunnivå (CSV)
emp_mun_csv = "data/arbetsmarknadsstruktur_2020.csv"
if file_exists(emp_mun_csv):
    loader.load_employment_municipality_sni(emp_mun_csv, db_path=DB_PATH)

# (Här kan du lägga till fler datakällor om du vill.)

print("Alla laddningar är färdiga.")

