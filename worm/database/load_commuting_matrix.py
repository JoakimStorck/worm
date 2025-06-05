import pandas as pd
import sqlite3
import re

def load_commuting_matrix(csv_path, db_path="data/worm.sqlite3", year=2020):
    # 1. Läs in filen (ofta semi-colon som separator)
    df = pd.read_csv(csv_path, sep=";", encoding="utf-8", dtype=str)
    df = df.fillna(0)
    
    # 2. Extrahera hemkommun-kod (från radetikett)
    df = df.rename(columns={df.columns[0]: "home_municipality"})
    df["home_municipal_code"] = df["home_municipality"].str.extract(r"(\d{4})")

    # 3. Extrahera arbetskommun-kod (från kolumnnamn)
    col_map = {}
    for col in df.columns[1:]:
        code = re.match(r"(\d{4})", col)
        if code:
            col_map[col] = code.group(1)
    df_long = df.melt(id_vars=["home_municipality", "home_municipal_code"], 
                      value_vars=list(col_map.keys()), 
                      var_name="work_municipality", value_name="employed")
    df_long["work_municipal_code"] = df_long["work_municipality"].map(col_map)
    df_long["employed"] = df_long["employed"].astype(int)
    df_long["year"] = year

    # 4. Behåll bara kommunkoder och relevanta kolumner
    df_final = df_long[["home_municipal_code", "work_municipal_code", "employed", "year"]]
    df_final = df_final.rename(columns={
        "home_municipal_code": "home_municipality",
        "work_municipal_code": "work_municipality"
    })

    # 5. Skriv till SQLite
    conn = sqlite3.connect(db_path)
    df_final.to_sql("commuting", conn, if_exists="replace", index=False)
    conn.close()

    print(f"{len(df_final)} commuting flows loaded to SQLite.")

# Använd så här:
# load_commuting_matrix("data/Sysselsatta 15-74 år arbetsställekommun bostadskommun.csv")
