import pandas as pd
import re
import sqlite3

def load_municipalities(csv_path, db_path="data/worm.sqlite3"):
    df = pd.read_csv(csv_path, dtype={'municipal_code': str})
    conn = sqlite3.connect(db_path)
    df.to_sql("municipalities", conn, if_exists="replace", index=False)
    conn.close()

def load_urban_areas(csv_path, db_path="data/worm.sqlite3", encoding="latin1"):
    df = pd.read_csv(csv_path, dtype={'municipal_code': str, 'county_code': str}, encoding=encoding)
    conn = sqlite3.connect(db_path)
    df.to_sql("urban_areas", conn, if_exists="replace", index=False)
    conn.close()

def load_small_localities(csv_path, db_path="data/worm.sqlite3"):
    df = pd.read_csv(csv_path, dtype={'municipal_code': str, 'county_code': str})
    # Om kolumn saknas – skapa den
    if 'area_km2' not in df.columns and 'area_ha' in df.columns:
        df["area_km2"] = df["area_ha"] / 100.0
    conn = sqlite3.connect(db_path)
    df.to_sql("small_localities", conn, if_exists="replace", index=False)
    conn.close()

def load_deso(csv_path, db_path="data/worm.sqlite3"):
    df = pd.read_csv(csv_path, dtype={'deso_code': str, 'municipal_code': str})
    conn = sqlite3.connect(db_path)
    df.to_sql("deso", conn, if_exists="replace", index=False)
    conn.close()

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


