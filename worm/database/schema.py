import sqlite3

def create_schema(db_path="data/worm.sqlite3"):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # Table: municipalities
    c.execute("""
    CREATE TABLE IF NOT EXISTS municipalities (
        municipal_code TEXT PRIMARY KEY,
        name TEXT,
        area_km2 REAL,
        population INTEGER,
        education_share REAL
    )
    """)
    # Table: deso
    c.execute("""
    CREATE TABLE IF NOT EXISTS deso (
        deso_code TEXT PRIMARY KEY,
        municipal_code TEXT,
        area_km2 REAL,
        population INTEGER,
        FOREIGN KEY (municipal_code) REFERENCES municipalities(municipal_code)
    )
    """)
    # Table: employment
    c.execute("""
    CREATE TABLE IF NOT EXISTS employment (
        region_code TEXT,
        sni_code TEXT,
        year INTEGER,
        employed INTEGER,
        workplaces INTEGER,
        PRIMARY KEY (region_code, sni_code, year)
    )
    """)
    conn.commit()
    conn.close()

def create_municipalities_table(db_path="data/worm.sqlite3"):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS municipalities (
        municipal_code TEXT PRIMARY KEY,
        name TEXT,
        population INTEGER
        -- Lägg till fler kolumner här vid behov, t.ex. area_km2, population_25_64, num_higher_educated_25_64
    )
    """)
    conn.commit()
    conn.close()
