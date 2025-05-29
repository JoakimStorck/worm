import sqlite3

def create_schema(db_path="data/worm.sqlite3"):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    c = conn.cursor()
    # Table: municipalities
    c.execute("""
        CREATE TABLE IF NOT EXISTS municipalities (
            municipal_code TEXT PRIMARY KEY,
            municipality TEXT,
            county_code TEXT,
            county TEXT,
            population INTEGER,
            area_ha REAL,
            area_km2 REAL,
            geom_wkt TEXT
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
            area_ha REAL,
            area_km2 REAL,
            population INTEGER,
            year INTEGER,
            valid_from TEXT,
            valid_to TEXT,
            geom_wkt TEXT,
            FOREIGN KEY (municipal_code) REFERENCES municipalities(municipal_code)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS small_localities (
            object_id INTEGER PRIMARY KEY,
            uuid TEXT,
            small_locality_id TEXT,
            municipal_code TEXT,
            municipality TEXT,
            county_code TEXT,
            county TEXT,
            area_ha REAL,
            area_km2 REAL,
            population INTEGER,
            year INTEGER,
            geom_wkt TEXT,
            FOREIGN KEY (municipal_code) REFERENCES municipalities(municipal_code)
        )
    ''')  
    # Table: deso
    c.execute("""
        CREATE TABLE IF NOT EXISTS deso (
            object_id INTEGER PRIMARY KEY,
            object_identity TEXT,
            deso_code TEXT,
            regso_code TEXT,
            county_code TEXT,
            municipal_code TEXT,
            municipality TEXT,
            version TEXT,
            area_ha REAL,
            area_km2 REAL,
            population INTEGER,
            geom_wkt TEXT,
            FOREIGN KEY (municipal_code) REFERENCES municipalities(municipal_code)
        )
    """)
    # SNI-baserad sysselsättning
    c.execute("""
        CREATE TABLE IF NOT EXISTS employment_deso_sni (
            deso_code TEXT,
            year INTEGER,
            sni_code TEXT,
            age_group TEXT,
            employed INTEGER,
            workplaces INTEGER,
            PRIMARY KEY (deso_code, year, sni_code, age_group)
        )
        """)

    # Arbetsmarknadsstatus
    c.execute("""
        CREATE TABLE IF NOT EXISTS employment_deso_status (
            deso_code TEXT,
            year INTEGER,
            age_group TEXT,
            employed INTEGER,
            unemployed INTEGER,
            outside_labor_force INTEGER,
            PRIMARY KEY (deso_code, year, age_group)
        )
    """)
    conn.commit()
    conn.close()

