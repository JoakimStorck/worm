import pandas as pd
import sqlite3

def load_municipalities(csv_path, db_path="data/worm.sqlite3"):
    df = pd.read_csv(csv_path, dtype={'municipal_code': str})
    conn = sqlite3.connect(db_path)
    df.to_sql("municipalities", conn, if_exists="replace", index=False)
    conn.close()

def load_urban_areas(csv_path, db_path="data/worm.sqlite3"):
    df = pd.read_csv(csv_path, dtype={'municipal_code': str, 'county_code': str})
    conn = sqlite3.connect(db_path)
    df.to_sql("urban_areas", conn, if_exists="replace", index=False)
    conn.close()

def load_deso(csv_path, db_path="data/worm.sqlite3"):
    df = pd.read_csv(csv_path, dtype={'deso_code': str, 'municipal_code': str})
    conn = sqlite3.connect(db_path)
    df.to_sql("deso", conn, if_exists="replace", index=False)
    conn.close()

def load_employment(csv_path, db_path="data/worm.sqlite3"):
    df = pd.read_csv(csv_path, dtype={'region_code': str, 'sni_code': str})
    conn = sqlite3.connect(db_path)
    df.to_sql("employment", conn, if_exists="replace", index=False)
    conn.close()
