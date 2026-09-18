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

    # SCB:s folkmängd per ettårsklass och kommun (BE0101). Ålderspyramiden som
    # startpopulationens åldrar dras ur. Ettårsklasser och inte intervall:
    # pensionsavgången sker vid en bestämd ålder, och ett femårsintervall hade
    # tvingat fram en fördelning inom intervallet som filen redan innehåller.
    # Åldern 100 bär SCB:s klass "100+ år" och är därför ingen ren ettårsklass;
    # den ligger utanför arbetsför ålder och påverkar inget annat än totalen.
    c.execute("""
        CREATE TABLE IF NOT EXISTS population_by_age (
            municipal_code TEXT,
            year INTEGER,
            age INTEGER,
            n_total INTEGER,
            PRIMARY KEY (municipal_code, year, age)
        )
    """)

    # SCB:s arbetsmarknadsstatus per åldersklass och kommun (BAS, slutlig
    # årsstatistik). Underlaget för hur arbetskraften fördelar sig över
    # åldrarna. RÅDATA: klasserna lagras som SCB redovisar dem, både
    # femårsgrupperna och de överlappande aggregaten 16-64, 16-65 och 16-66.
    # Aggregaten är inte redundanta här -- differenserna mellan dem är det
    # enda sättet att få arbetskraften vid 65 respektive 66 år, och just de
    # åldrarna avgör hur många som lämnar vid riktåldern.
    #
    # in_labour_force är sysselsatta plus arbetslösa, total är befolkningen i
    # samma klass, båda ur samma tabell: deltagandet ska räknas mot SCB:s egen
    # avgränsning och inte mot population_by_age, som avgränsar annorlunda.
    c.execute("""
        CREATE TABLE IF NOT EXISTS labour_force_by_age (
            municipal_code TEXT,
            year INTEGER,
            age_group TEXT,
            in_labour_force INTEGER,
            total INTEGER,
            PRIMARY KEY (municipal_code, year, age_group)
        )
    """)

    # SCB:s pendlingsflöden mellan kommuner. Referensen
    # share_hires_cross_municipality ställs mot, och den enda kalibreringen av
    # commute_cost_per_km. Diagonalen ingår: andelen som pendlar över gräns
    # behöver en nämnare, och nämnaren är alla sysselsatta med bostad i
    # kommunen.
    c.execute("""
        CREATE TABLE IF NOT EXISTS commuting (
            home_municipality TEXT,
            work_municipality TEXT,
            year INTEGER,
            employed INTEGER,
            PRIMARY KEY (home_municipality, work_municipality, year)
        )
    """)

    # SCB:s arbetsmarknadsstatus per kommun. Referensen modellens arbetslöshet
    # per kommun ställs mot. Åldern är 20-65 år i SCB:s uttag medan modellen
    # räknar 15-74, så rangordningen och spridningen är det jämförbara, inte
    # nivån.
    c.execute("""
        CREATE TABLE IF NOT EXISTS labour_market_status (
            municipal_code TEXT PRIMARY KEY,
            employed INTEGER,
            unemployed INTEGER,
            u_rate REAL
        )
    """)

    # Yrkesregistret. occupation_by_industry är rikets yrke x näringsgren x
    # storleksklass; occupation_by_county länens nattbefolkning per yrke.
    # occupation_weights_ssyk_by_municipality är IPF-skattningen ur de två plus
    # kommunernas branschmix. Koderna är SSYK3 och inte O*NET: tabellen byter
    # namn till occupation_weights_by_municipality först när crosswalken
    # SSYK -> ISCO-08 -> SOC -> O*NET finns.
    # Dagbefolkning per kommun, yrke och bransch (TAB4436, core/database/load_dagbef.py)
    c.execute("""
        CREATE TABLE IF NOT EXISTS employment_workplace_occupation_sni (
            municipal_code TEXT, ssyk_code TEXT, sni_code TEXT, sex TEXT,
            year INTEGER, employed INTEGER
        )
    """)
    # Lediga jobb per 100 anställningar och län (TAB6605, core/database/load_lediga_jobb.py)
    c.execute("""
        CREATE TABLE IF NOT EXISTS vacancy_rate_county (
            county_code TEXT, vacancy_type TEXT, quarter TEXT,
            per_100 REAL, margin REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS occupation_by_industry (
            ssyk_code TEXT, sni_code TEXT, size_class TEXT, employed INTEGER
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS occupation_by_county (
            county_code TEXT, ssyk_code TEXT, employed INTEGER
        )
    """)

    # SSYK -> O*NET. ssyk_isco_key är ren avskrift av SCB:s nyckel och ändras
    # bara när SCB publicerar en ny. ssyk3_onet_crosswalk är härledd och bär
    # fyra likformighetsantaganden, dokumenterade i load_ssyk_onet. De ligger
    # i skilda tabeller för att SCB:s uppgift ska gå att skilja från vår
    # approximation.
    c.execute("""
        CREATE TABLE IF NOT EXISTS ssyk_isco_key (
            ssyk4 TEXT, isco4 TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS ssyk3_onet_crosswalk (
            occupation_code TEXT, onet_code TEXT, share REAL
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

    

    # onet_occupation_space definieras INTE här. Tabellen skapas av
    # scripts/load_task_geometry.py med to_sql, och dess kolumner är
    # geometrins (x_occ, y_occ, r_o, r_req, w_rel, pi_rel). Den definition som
    # stod här beskrev skill-PCA:ns kolumner och stämde inte med något som
    # längre skrivs.

    # Cross table for SNI-codes to O*NET occupations, that occur in that industry
    c.execute("""
        CREATE TABLE IF NOT EXISTS sni_onet_link (
            sni_code TEXT,
            onet_code TEXT,
            freq REAL,
            PRIMARY KEY (sni_code, onet_code)
        )
    """)
    # Tabell för utbildningsnivå per kommun, år, nivå, kön (eller summerat om du föredrar)
    c.execute("""
        CREATE TABLE IF NOT EXISTS education_level_municipality (
            municipal_code TEXT,
            year INTEGER,
            education_level_code TEXT,   -- t.ex. '1'–'7', 'US'
            education_level_label TEXT,  -- t.ex. 'Förgymnasial <9 år', etc.
            n_male INTEGER,
            n_female INTEGER,
            n_total INTEGER,
            PRIMARY KEY (municipal_code, year, education_level_code)
        )
    """)


    conn.commit()
    conn.close()
