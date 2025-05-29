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
    c.execute('''
        CREATE TABLE IF NOT EXISTS urban_areas (
            object_id INTEGER PRIMARY KEY,
            uuid TEXT,
            urban_area_id TEXT,
            urban_area TEXT,
            municipal_code TEXT,
            municipality TEXT,
            county_code TEXT,
            county TEXT,
            area_ha INTEGER,
            population INTEGER,
            year INTEGER,
            valid_from TEXT,
            valid_to TEXT,
            geom_wkt TEXT
        )
    ''')
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

