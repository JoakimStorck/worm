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

    # Skapa WKT-polygon
    gdf["geom_wkt"] = gdf.geometry.to_wkt()
    # Skapa/kopiera rätt kolumner
    gdf["object_id"] = gdf["objectid"] if "objectid" in gdf.columns else gdf.index.astype(str)
    gdf["uuid"] = gdf["uuid"] if "uuid" in gdf.columns else None
    gdf["urban_area_id"] = gdf["tatortskod"] if "tatortskod" in gdf.columns else None
    gdf["urban_area"] = gdf["tatort"] if "tatort" in gdf.columns else None
    gdf["municipal_code"] = gdf["kommun"] if "kommun" in gdf.columns else None
    gdf["municipality"] = gdf["kommunnamn"] if "kommunnamn" in gdf.columns else None
    gdf["county_code"] = gdf["lan"] if "lan" in gdf.columns else None
    gdf["county"] = gdf["lannamn"] if "lannamn" in gdf.columns else None
    gdf["area_ha"] = gdf["area_ha"] if "area_ha" in gdf.columns else None
    gdf["area_km2"] = gdf["area_ha"]/100 if "area_ha" in gdf.columns else None
    gdf["population"] = gdf["bef"] if "bef" in gdf.columns else None
    gdf["year"] = gdf["ar"] if "ar" in gdf.columns else None
    gdf["valid_from"] = gdf["validfrom"] if "validfrom" in gdf.columns else None
    gdf["valid_to"] = gdf["validto"] if "validto" in gdf.columns else None

    # Rätt kolumnordning enligt schema.py
    cols = [
        "object_id", "uuid", "urban_area_id", "urban_area", "municipal_code", "municipality",
        "county_code", "county", "area_ha", "area_km2", "population", "year",
        "valid_from", "valid_to", "geom_wkt"
    ]
    gdf = gdf[[c for c in cols if c in gdf.columns]]

    conn = sqlite3.connect(db_path)
    gdf.to_sql("urban_areas", conn, if_exists="replace", index=False)
    conn.close()
    print(f"{len(gdf)} urban areas loaded and saved to database.")


def load_small_localities_gpkg(gpkg_path, db_path="data/worm.sqlite3"):
    gdf = gpd.read_file(gpkg_path)
    print("Small localities - columns:", gdf.columns)
    gdf["geom_wkt"] = gdf.geometry.to_wkt()

    # Mappa och skapa alla kolumner du vill ha i SQL
    gdf["object_id"] = gdf["objectid"] if "objectid" in gdf.columns else gdf.index.astype(str)
    gdf["uuid"] = gdf["uuid"] if "uuid" in gdf.columns else None
    gdf["small_locality_id"] = gdf["smaort"] if "smaort" in gdf.columns else None
    gdf["municipal_code"] = gdf["kommun"] if "kommun" in gdf.columns else None
    gdf["municipality"] = gdf["kommunnamn"] if "kommunnamn" in gdf.columns else None
    gdf["county_code"] = gdf["lan"] if "lan" in gdf.columns else None
    gdf["county"] = gdf["lannamn"] if "lannamn" in gdf.columns else None
    gdf["area_ha"] = gdf["area_ha"] if "area_ha" in gdf.columns else None
    gdf["area_km2"] = gdf["area_ha"]/100 if "area_ha" in gdf.columns else None
    gdf["population"] = gdf["bef"] if "bef" in gdf.columns else None
    gdf["year"] = gdf["ar"] if "ar" in gdf.columns else None
    gdf["valid_from"] = gdf["validfrom"] if "validfrom" in gdf.columns else None
    gdf["valid_to"] = gdf["validto"] if "validto" in gdf.columns else None

    cols = [
        "object_id", "uuid", "small_locality_id", "municipal_code", "municipality",
        "county_code", "county", "area_ha", "area_km2", "population", "year",
        "valid_from", "valid_to", "geom_wkt"
    ]
    gdf = gdf[[c for c in cols if c in gdf.columns]]

    conn = sqlite3.connect(db_path)
    gdf.to_sql("small_localities", conn, if_exists="replace", index=False)
    conn.close()
    print(f"{len(gdf)} small localities loaded and saved to database.")

def load_commercial_zones_gpkg(gpkg_path, db_path="data/worm.sqlite3"):
    import geopandas as gpd
    import pandas as pd
    import sqlite3

    gdf = gpd.read_file(gpkg_path)
    print("Commercial zones - columns:", gdf.columns)
    gdf["geom_wkt"] = gdf.geometry.to_wkt()

    # Säkerställ att kommunkod är STRÄNG
    gdf["kommunkod"] = gdf["kommunkod"].astype(str)

    # Ladda kommunregister och säkerställ sträng
    conn = sqlite3.connect(db_path)
    municipalities = pd.read_sql("SELECT municipal_code, municipality FROM municipalities", conn)
    municipalities["municipal_code"] = municipalities["municipal_code"].astype(str)
    conn.close()

    # Lägg in kommunnamn via merge
    gdf = gdf.merge(municipalities, how="left", left_on="kommunkod", right_on="municipal_code")
    print("Efter merge:", gdf[["kommunkod", "municipality"]].head(5))

    # Skapa rätt kolumner
    gdf["id"] = gdf["ho_kod"].astype(str)
    gdf["zone_code"] = gdf["ho_kod"].astype(str)
    gdf["municipal_code"] = gdf["kommunkod"].astype(str)
    # gdf["municipality"] är nu från merge
    gdf["county_code"] = gdf["lankod"].astype(str)
    gdf["county"] = None  # Fyll om det finns länsnamn
    gdf["num_employed"] = gdf["anst_handel"]
    gdf["num_workplaces"] = gdf["arbst_handel"]
    gdf["num_subzones"] = gdf["antal_omr"]
    gdf["area_ha"] = gdf["area_ha"]
    gdf["year"] = gdf["ar"]
    gdf["valid_from"] = gdf["validfrom"]
    gdf["valid_to"] = gdf["validto"]

    # Kolumnordning enligt schema
    cols = [
        "id", "uuid", "zone_code", "municipal_code", "municipality", "county_code", "county",
        "num_employed", "num_workplaces", "num_subzones", "area_ha", "year",
        "valid_from", "valid_to", "geom_wkt"
    ]
    for c in cols:
        if c not in gdf.columns:
            gdf[c] = None
    gdf = gdf[cols]

    # Spara till SQLite
    conn = sqlite3.connect(db_path)
    gdf.to_sql("commercial_zones", conn, if_exists="replace", index=False)
    conn.close()
    print(f"{len(gdf)} commercial zones loaded and saved to database.")


def load_business_zones_gpkg(gpkg_path, db_path="data/worm.sqlite3"):
    gdf = gpd.read_file(gpkg_path)
    print("Business zones - columns:", gdf.columns)
    gdf["geom_wkt"] = gdf.geometry.to_wkt()

    # Säkerställ STRÄNG och ledande nollor
    gdf["kommunkod"] = gdf["kommunkod"].astype(str).str.zfill(4)

    # Ladda kommunregister och säkerställ sträng + ledande nollor
    conn = sqlite3.connect(db_path)
    municipalities = pd.read_sql("SELECT municipal_code, municipality FROM municipalities", conn)
    municipalities["municipal_code"] = municipalities["municipal_code"].astype(str).str.zfill(4)
    conn.close()

    # DEBUG: Skriv ut Faluns kod och namn i båda tabeller innan merge
    print("\n=== DEBUG: Falun i gdf ===")
    print(gdf[gdf["kommunkod"] == "2080"][["kommunkod", "vo_kod", "geometry"]].head(3))
    print("\n=== DEBUG: Falun i municipalities ===")
    print(municipalities[municipalities["municipal_code"] == "2080"])

    gdf = gdf.merge(municipalities, how="left", left_on="kommunkod", right_on="municipal_code")

    # Efter merge: Skriv ut första rader samt alla rader för Falun
    print("\nEfter merge, första 5 rader:")
    print(gdf[["kommunkod", "municipality", "municipal_code"]].head(5))

    print("\nEfter merge, Falun:")
    print(gdf[gdf["kommunkod"] == "2080"][["kommunkod", "municipality", "municipal_code", "vo_kod"]].head(10))

    gdf["id"] = gdf["vo_kod"].astype(str)
    gdf["zone_code"] = gdf["vo_kod"].astype(str)
    gdf["municipal_code"] = gdf["kommunkod"].astype(str)
    gdf["county_code"] = gdf["lankod"].astype(str)
    gdf["county"] = None
    gdf["zone_type"] = gdf["omradestyp"] if "omradestyp" in gdf.columns else None
    gdf["num_employed"] = gdf["anstallda"]
    gdf["num_workplaces"] = gdf["arbetsstallen"]
    gdf["main_industry"] = gdf["storstabransch"] if "storstabransch" in gdf.columns else None
    gdf["area_ha"] = gdf["area_ha"]
    gdf["year"] = gdf["ar"]
    gdf["valid_from"] = gdf["validfrom"]
    gdf["valid_to"] = gdf["validto"]

    cols = [
        "id", "uuid", "zone_code", "municipal_code", "municipality", "county_code", "county",
        "zone_type", "num_employed", "num_workplaces", "main_industry",
        "area_ha", "year", "valid_from", "valid_to", "geom_wkt"
    ]
    for c in cols:
        if c not in gdf.columns:
            gdf[c] = None
    gdf = gdf[cols]

    conn = sqlite3.connect(db_path)
    gdf.to_sql("business_zones", conn, if_exists="replace", index=False)
    conn.close()
    print(f"{len(gdf)} business zones loaded and saved to database.")

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

    # Skapa eller mappa alla kolumner enligt databasens schema
    gdf["object_id"] = gdf["objectid"] if "objectid" in gdf.columns else gdf.index.astype(str)
    gdf["object_identity"] = gdf["objektidentitet"] if "objektidentitet" in gdf.columns else None
    gdf["deso_code"] = gdf["desokod"] if "desokod" in gdf.columns else None
    gdf["regso_code"] = gdf["regsokod"] if "regsokod" in gdf.columns else None
    gdf["county_code"] = gdf["lanskod"] if "lanskod" in gdf.columns else None
    gdf["municipal_code"] = gdf["kommunkod"] if "kommunkod" in gdf.columns else None
    gdf["municipality"] = gdf["kommunnamn"] if "kommunnamn" in gdf.columns else None
    gdf["version"] = gdf["version"] if "version" in gdf.columns else None

    # Area, population m.fl. finns ej i filen, men skapas som tomma fält för konsistens
    gdf["area_ha"] = None
    gdf["area_km2"] = None
    gdf["population"] = None

    # Skapa WKT-polygon
    gdf["geom_wkt"] = gdf.geometry.to_wkt()

    # Rätt kolumnordning
    cols = [
        "object_id", "object_identity", "deso_code", "regso_code", "county_code", "municipal_code",
        "municipality", "version", "area_ha", "area_km2", "population", "geom_wkt"
    ]
    gdf = gdf[cols]

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

def load_onet_occupations(occupation_path, db_path="data/worm.sqlite3"):
    df = pd.read_csv(occupation_path, sep='\t', encoding='utf-8')
    for col in ["O*NET-SOC Code", "Title", "Description"]:
        if col not in df.columns:
            df[col] = ""
    df = df.rename(columns={
        "O*NET-SOC Code": "onet_code",
        "Title": "title",
        "Description": "description"
    })[["onet_code", "title", "description"]]
    conn = sqlite3.connect(db_path)
    df.to_sql("onet_occupations", conn, if_exists="replace", index=False)
    conn.close()
    print(f"Loaded {len(df)} occupations into onet_occupations.")

def load_onet_skills(skills_path, db_path="data/worm.sqlite3"):
    df = pd.read_csv(skills_path, sep='\t', encoding='utf-8')
    # Skapa tomma kolumner om de saknas
    for col in ["Element ID", "Element Name", "Domain Source", "Element Type", "Description"]:
        if col not in df.columns:
            df[col] = ""
    skills = df[["Element ID", "Element Name", "Domain Source", "Element Type", "Description"]].drop_duplicates()
    skills = skills.rename(columns={
        "Element ID": "skill_id",
        "Element Name": "skill_name",
        "Domain Source": "domain",
        "Element Type": "category",
        "Description": "description"
    })[["skill_id", "skill_name", "domain", "category", "description"]]
    conn = sqlite3.connect(db_path)
    skills.to_sql("onet_skills", conn, if_exists="replace", index=False)
    conn.close()
    print(f"Loaded {len(skills)} skills into onet_skills.")

def load_occupation_skill_link(skills_path, db_path="data/worm.sqlite3"):
    df = pd.read_csv(skills_path, sep='\t', encoding='utf-8')
    for col in ["O*NET-SOC Code", "Element ID", "Scale ID", "Data Value"]:
        if col not in df.columns:
            df[col] = ""
    link = df[["O*NET-SOC Code", "Element ID", "Scale ID", "Data Value"]].copy()
    link = link.rename(columns={
        "O*NET-SOC Code": "onet_code",
        "Element ID": "skill_id",
        "Scale ID": "scale_id",
        "Data Value": "data_value"
    })[["onet_code", "skill_id", "scale_id", "data_value"]]
    conn = sqlite3.connect(db_path)
    link.to_sql("occupation_skill_link", conn, if_exists="replace", index=False)
    conn.close()
    print(f"Loaded {len(link)} rows into occupation_skill_link.")
