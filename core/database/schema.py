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
    # Table: urban areas
    c.execute("""
        CREATE TABLE IF NOT EXISTS urban_areas (
            object_id TEXT PRIMARY KEY,
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
    """)
    # Table: small localities
    c.execute("""
        CREATE TABLE IF NOT EXISTS small_localities (
            object_id TEXT PRIMARY KEY,
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
    """)
    # Table: deso
    c.execute("""
        CREATE TABLE IF NOT EXISTS deso (
            object_id TEXT PRIMARY KEY,
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
    # Table: commercial zones
    c.execute("""
        CREATE TABLE IF NOT EXISTS commercial_zones (
            id TEXT PRIMARY KEY,
            uuid TEXT,
            zone_code TEXT,
            municipal_code TEXT,
            municipality TEXT,
            county_code TEXT,
            county TEXT,
            num_employed INTEGER,
            num_workplaces INTEGER,
            num_subzones INTEGER,
            area_ha REAL,
            year INTEGER,
            valid_from TEXT,
            valid_to TEXT,
            geom_wkt TEXT
        )
    """)
    # Table: business zones
    c.execute("""
        CREATE TABLE IF NOT EXISTS business_zones (
            id TEXT PRIMARY KEY,
            uuid TEXT,
            zone_code TEXT,
            municipal_code TEXT,
            municipality TEXT,
            county_code TEXT,
            county TEXT,
            zone_type TEXT,
            num_employed INTEGER,
            num_workplaces INTEGER,
            main_industry TEXT,
            area_ha REAL,
            year INTEGER,
            valid_from TEXT,
            valid_to TEXT,
            geom_wkt TEXT
        )
    """)

    # SNI-based employment per municipality
    c.execute("""
        CREATE TABLE IF NOT EXISTS employment_municipality_sni (
            municipal_code TEXT,
            year INTEGER,
            sni_code TEXT,
            employed INTEGER,
            workplaces INTEGER,
            PRIMARY KEY (municipal_code, year, sni_code)
        )
    """)
    # SNI-based employment per DeSO
    c.execute("""
        CREATE TABLE IF NOT EXISTS employment_deso_sni (
            deso_code TEXT,
            year INTEGER,
            sni_code TEXT,
            sni_description TEXT,
            employed INTEGER,
            PRIMARY KEY (deso_code, year, sni_code)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS onet_occupations (
            onet_code TEXT PRIMARY KEY,
            title TEXT,
            description TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS onet_skills (
            skill_id TEXT PRIMARY KEY,
            skill_name TEXT,
            domain TEXT,
            category TEXT,
            description TEXT
        )
    """)
    

    c.execute("""
        CREATE TABLE IF NOT EXISTS occupation_skill_link (
            onet_code TEXT,
            skill_id TEXT,
            scale_id TEXT,
            data_value REAL,
            FOREIGN KEY (onet_code) REFERENCES onet_occupations(onet_code),
            FOREIGN KEY (skill_id) REFERENCES onet_skills(skill_id)
        )
    """)

    # Table for O*NET occupation space clustering
    c.execute("""
        CREATE TABLE IF NOT EXISTS onet_occupation_space (
            onet_code TEXT,
            n_clusters INTEGER,
            title TEXT,
            pc1 REAL,
            pc2 REAL,
            cluster INTEGER,
            cluster_name TEXT,
            chi REAL,
            xi REAL,
            h REAL,
            PRIMARY KEY (onet_code, n_clusters),
            FOREIGN KEY (onet_code) REFERENCES onet_occupations(onet_code)
        )
    """)


    conn.commit()
    conn.close()
