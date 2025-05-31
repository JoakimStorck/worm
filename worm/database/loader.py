import geopandas as gpd
import pandas as pd
import re
import sqlite3
import locale

locale.setlocale(locale.LC_NUMERIC, "C")

def load_municipalities(csv_path, db_path="data/worm.sqlite3"):
    df = pd.read_csv(csv_path, dtype={'municipal_code': str})
    conn = sqlite3.connect(db_path)
    df.to_sql("municipalities", conn, if_exists="replace", index=False)
    conn.close()

def load_municipalities_gpkg(gpkg_path, db_path="data/worm.sqlite3"):
    gdf = gpd.read_file(gpkg_path)
    print("Municipalities - columns:", gdf.columns)
    # Exempel: ["municipal_code", "municipality", "county_code", "county", "population", "area_ha", "area_km2", "geometry"]
    # Skapa WKT-kolumn
    gdf["geom_wkt"] = gdf.geometry.to_wkt()
    # Välj kolumner (justera om fältnamn skiljer sig)
    cols = ["municipal_code", "municipality", "county_code", "county", "population", "area_ha", "area_km2", "geom_wkt"]
    gdf = gdf[cols]
    conn = sqlite3.connect(db_path)
    gdf.to_sql("municipalities", conn, if_exists="replace", index=False)
    conn.close()

def load_urban_areas_gpkg(gpkg_path, db_path="data/worm.sqlite3"):
    gdf = gpd.read_file(gpkg_path)
    print("Urban areas - columns:", gdf.columns)
    gdf["geom_wkt"] = gdf.geometry.to_wkt()
    cols = ["object_id", "uuid", "urban_area_id", "urban_area", "municipal_code", "municipality", "county_code", "county", "area_ha", "area_km2", "population", "year", "valid_from", "valid_to", "geom_wkt"]
    gdf = gdf[[c for c in cols if c in gdf.columns]]
    conn = sqlite3.connect(db_path)
    gdf.to_sql("urban_areas", conn, if_exists="replace", index=False)
    conn.close()

def load_small_localities_gpkg(gpkg_path, db_path="data/worm.sqlite3"):
    gdf = gpd.read_file(gpkg_path)
    print("Small localities - columns:", gdf.columns)
    gdf["geom_wkt"] = gdf.geometry.to_wkt()
    cols = ["object_id", "uuid", "small_locality_id", "municipal_code", "municipality", "county_code", "county", "area_ha", "area_km2", "population", "year", "geom_wkt"]
    gdf = gdf[[c for c in cols if c in gdf.columns]]
    conn = sqlite3.connect(db_path)
    gdf.to_sql("small_localities", conn, if_exists="replace", index=False)
    conn.close()

def load_commercial_zones_gpkg(gpkg_path, db_path="data/worm.sqlite3"):
    gdf = gpd.read_file(gpkg_path)
    print("Commercial zones - columns:", gdf.columns)
    # Justera kolumner enligt din Handelsomraden_2020.gpkg
    gdf["id"] = gdf["ho_kod"].astype(str)
    gdf["name"] = gdf["kommunnamn"] + " - " + gdf.index.astype(str)
    gdf["municipal_code"] = gdf["kommunkod"].astype(str)
    gdf["geom_wkt"] = gdf.geometry.to_wkt()
    cols = ["id", "name", "municipal_code", "geom_wkt"]
    gdf = gdf[cols]
    conn = sqlite3.connect(db_path)
    gdf.to_sql("commercial_zones", conn, if_exists="replace", index=False)
    conn.close()

def load_business_zones_gpkg(gpkg_path, db_path="data/worm.sqlite3"):
    gdf = gpd.read_file(gpkg_path)
    print("Business zones - columns:", gdf.columns)
    gdf["id"] = gdf["vo_kod"].astype(str) if "vo_kod" in gdf.columns else gdf.index.astype(str)
    gdf["name"] = gdf["kommunnamn"] + " - " + gdf.index.astype(str) if "kommunnamn" in gdf.columns else "Business zone " + gdf.index.astype(str)
    gdf["municipal_code"] = gdf["kommunkod"].astype(str) if "kommunkod" in gdf.columns else None
    gdf["geom_wkt"] = gdf.geometry.to_wkt()
    cols = ["id", "name", "municipal_code", "geom_wkt"]
    gdf = gdf[cols]
    conn = sqlite3.connect(db_path)
    gdf.to_sql("business_zones", conn, if_exists="replace", index=False)
    conn.close()

def load_leisure_house_zones_gpkg(gpkg_path, db_path="data/worm.sqlite3"):
    gdf = gpd.read_file(gpkg_path)
    print("Leisure house zones - columns:", gdf.columns)
    gdf["id"] = gdf["fo_kod"].astype(str) if "fo_kod" in gdf.columns else gdf.index.astype(str)
    gdf["name"] = gdf["kommunnamn"] + " - " + gdf.index.astype(str) if "kommunnamn" in gdf.columns else "Leisure house zone " + gdf.index.astype(str)
    gdf["municipal_code"] = gdf["kommunkod"].astype(str) if "kommunkod" in gdf.columns else None
    gdf["geom_wkt"] = gdf.geometry.to_wkt()
    cols = ["id", "name", "municipal_code", "geom_wkt"]
    gdf = gdf[cols]
    conn = sqlite3.connect(db_path)
    gdf.to_sql("leisure_house_zones", conn, if_exists="replace", index=False)
    conn.close()

def load_deso_gpkg(gpkg_path, db_path="data/worm.sqlite3"):
    gdf = gpd.read_file(gpkg_path)
    print("DeSO - columns:", gdf.columns)
    # Vanliga SCB-fält: "deso", "kommun", "kommunkod", "lan", "lankod", "area_ha", "area_km2", "geometry"
    # Du kan behöva justera denna mappning efter dina faktiska kolumner!
    gdf["object_id"] = gdf.index.astype(int)
    gdf["object_identity"] = gdf["deso"] if "deso" in gdf.columns else None
    gdf["deso_code"] = gdf["deso"] if "deso" in gdf.columns else None
    gdf["municipal_code"] = gdf["kommunkod"].astype(str) if "kommunkod" in gdf.columns else None
    gdf["municipality"] = gdf["kommun"] if "kommun" in gdf.columns else None
    gdf["county_code"] = gdf["lankod"].astype(str) if "lankod" in gdf.columns else None
    gdf["county"] = gdf["lan"] if "lan" in gdf.columns else None
    gdf["area_ha"] = gdf["area_ha"] if "area_ha" in gdf.columns else None
    gdf["area_km2"] = gdf["area_km2"] if "area_km2" in gdf.columns else (gdf["area_ha"]/100 if "area_ha" in gdf.columns else None)
    gdf["population"] = gdf["befolkning"] if "befolkning" in gdf.columns else None
    gdf["version"] = gdf["version"] if "version" in gdf.columns else None
    gdf["geom_wkt"] = gdf.geometry.to_wkt()
    cols = [
        "object_id", "object_identity", "deso_code", "municipal_code", "municipality", "county_code", "county",
        "version", "area_ha", "area_km2", "population", "geom_wkt"
    ]
    gdf = gdf[[c for c in cols if c in gdf.columns]]
    conn = sqlite3.connect(db_path)
    gdf.to_sql("deso", conn, if_exists="replace", index=False)
    conn.close()
    print(f"{len(gdf)} DeSO-zoner inlästa och sparade i databasen.")

def extract_sni_code(s):
    if not isinstance(s, str):
        return ""
    m = re.match(r"^([A-U\+\d]+)", s.strip())
    return m.group(1) if m else s.strip()

def extract_sni_description(s):
    if not isinstance(s, str):
        return ""
    parts = s.strip().split(" ", 1)
    return parts[1] if len(parts) > 1 else ""

def load_employment_deso_sni(csv_file, db_path="data/worm.sqlite3", year=2023):
    # Läs in med rätt encoding
    df = pd.read_csv(csv_file, sep=";", skiprows=2, encoding="latin1")
    df["sni_code"] = df["näringsgren SNI 2007"].apply(extract_sni_code)
    df["sni_description"] = df["näringsgren SNI 2007"].apply(extract_sni_description)
    df["year"] = year

    # Hantera sysselsatta (kan heta "sysselsatta" eller året som kolumn)
    if str(year) in df.columns:
        df["employed"] = df[str(year)]
    elif "sysselsatta" in df.columns:
        df["employed"] = df["sysselsatta"]
    else:
        raise Exception("Can't find employment column!")

    # Ta ut relevanta kolumner
    df_out = df[["region", "year", "sni_code", "sni_description", "employed"]]
    df_out = df_out.rename(columns={"region": "deso_code"})

    # Ta bort dubletter
    df_out = df_out.drop_duplicates(subset=["deso_code", "year", "sni_code"])

    # Skriv till SQLite
    conn = sqlite3.connect(db_path)
    df_out.to_sql("employment_deso_sni", conn, if_exists="append", index=False)
    conn.close()

def load_employment_municipality_sni(csv_file, db_path="data/worm.sqlite3", year=2020):
    df = pd.read_csv(csv_file, encoding="utf-8")
    # Kolumn-mappning om du har svenska kolumner
    if "Region" in df.columns:
        df = df.rename(columns={
            "Region": "municipal_code",
            "SNI2007": "sni_code",
            "Year": "year",
            "Antal_Anstallda": "employed",
            "Antal_Arbetsstallen": "workplaces"
        })
    # Lägg till år om det saknas
    if "year" not in df.columns:
        df["year"] = year

    outcols = ["municipal_code", "year", "sni_code", "employed", "workplaces"]
    for col in outcols:
        if col not in df.columns:
            df[col] = None

    df = df[outcols]

    # Skriv till SQLite
    conn = sqlite3.connect(db_path)
    df.to_sql("employment_municipality_sni", conn, if_exists="replace", index=False)
    conn.close()


