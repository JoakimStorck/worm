import yaml
import numpy as np
import pandas as pd
import sqlite3
import geopandas as gpd
from shapely import wkt
from shapely.geometry import Point

# ------------------------------
# Tids- och parameterfunktioner
# ------------------------------

def interpolate_linear(start, end, start_year, end_year, year):
    if year <= start_year:
        return start
    if year >= end_year:
        return end
    return start + (end - start) * (year - start_year) / (end_year - start_year)

def step_value(changes, default, year):
    val = default
    for change in sorted(changes, key=lambda c: c["year"]):
        if year >= change["year"]:
            val = change["value"]
        else:
            break
    return val

def get_param_value(param, year, default=None):
    if isinstance(param, dict):
        if "by_year" in param:
            years = sorted(map(int, param["by_year"].keys()))
            values = [param["by_year"][str(y)] for y in years]
            if year <= years[0]:
                return values[0]
            if year >= years[-1]:
                return values[-1]
            for i in range(1, len(years)):
                if years[i-1] <= year < years[i]:
                    return interpolate_linear(values[i-1], values[i], years[i-1], years[i], year)
        elif "curve" in param:
            if param["curve"] == "linear":
                return interpolate_linear(param["start"], param["end"], param["start_year"], param["end_year"], year)
            elif param["curve"] == "step":
                return step_value(param["changes"], default, year)
        else:
            return param.get("constant", default)
    return param if param is not None else default

# ------------------------------
# ScenarioBuilder
# ------------------------------

class ScenarioBuilder:
    def __init__(self, config_path, db_path=None, geoworld=None):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        self.geoworld = geoworld
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path) if db_path else None

        self.seed = self.config.get("seed", None)
        self.rng = np.random.default_rng(self.seed)
        self.start_year = self.config.get("start_year", 2024)
        self.end_year = self.config.get("end_year", 2024)

    def get_yearly_params(self, year):
        n_workers = int(get_param_value(self.config.get("n_workers"), year, default=0))
        n_jobs = int(get_param_value(self.config.get("n_jobs"), year, default=0))
        municipalities = self.config.get("municipalities", [])
        education_levels = self.config.get("education_levels", {})
        sex_ratio = float(get_param_value(self.config.get("sex_ratio"), year, default=0.5))
        age_range = self.config.get("age_range", [20, 64])
        occupation_distribution = self.config.get("occupation_distribution", "random")
        # Lägg till fler parametrar här vid behov
        params = {
            "n_workers": n_workers,
            "n_jobs": n_jobs,
            "municipalities": municipalities,
            "education_levels": education_levels,
            "sex_ratio": sex_ratio,
            "age_range": age_range,
            "occupation_distribution": occupation_distribution,
        }
        return params

    # -----------------------------------------
    # Flexibel arbetsgivargenerering med lager
    # -----------------------------------------

    def fetch_zones(self, layer_name, weight_field, municipal_code, year=None):
        # Kolla om 'year'-kolumn finns i tabellen
        cursor = self.conn.execute(f"PRAGMA table_info({layer_name})")
        columns = [row[1] for row in cursor.fetchall()]
        has_year = 'year' in columns

        # Bygg grundläggande SQL
        sql_base = f"SELECT * FROM {layer_name} WHERE municipal_code = ?"

        # Om 'year' finns: välj den största (senaste) årgången automatiskt
        if has_year:
            # Hämta senaste år för denna kommun
            cursor = self.conn.execute(f"SELECT MAX(year) FROM {layer_name} WHERE municipal_code = ?", (municipal_code,))
            latest_year = cursor.fetchone()[0]
            if latest_year is None:
                raise ValueError(f"Inga zoner hittades i lager '{layer_name}' för kommun {municipal_code} (ingen årgång alls)")
            # Läs zonerna för den årgången
            sql = sql_base + " AND year = ?"
            params = (municipal_code, latest_year)
            df = pd.read_sql(sql, self.conn, params=params)
        else:
            # Om ingen årskolumn finns, ta alla zoner för kommunen
            df = pd.read_sql(sql_base, self.conn, params=(municipal_code,))

        if df.empty:
            raise ValueError(f"Inga zoner hittades i lager '{layer_name}' för kommun {municipal_code} (oavsett år)")
    
        df = pd.read_sql(sql, self.conn, params=params)
        if 'geom_wkt' not in df.columns:
            raise ValueError(f"Kolumnen 'geom_wkt' saknas i {layer_name}")
        df['geometry'] = df['geom_wkt'].apply(wkt.loads)
        gdf = gpd.GeoDataFrame(df, geometry='geometry')
        gdf['layer'] = layer_name
        gdf['weight_field'] = gdf[weight_field]
        return gdf


    def fetch_sni_distribution(self, municipal_code, year, sni_source="municipality"):
        if sni_source == 'municipality':
            sni = pd.read_sql("""
                SELECT sni_code, workplaces FROM employment_municipality_sni
                WHERE municipal_code = ? AND year = ?
            """, self.conn, params=(municipal_code, year))
            total = sni['workplaces'].sum()
            sni['prob'] = sni['workplaces'] / total if total > 0 else 1.0/len(sni)
            return sni
        # Kan byggas ut med fler källor (DeSO/zon)
        raise NotImplementedError(f"SNI source '{sni_source}' not implemented.")

    def get_size_distribution(self, config=None):
        # Kan specificeras i YAML eller default
        if config and "size_distribution" in config:
            # Låt användaren ange egna bins/probs om så önskas
            return config["size_distribution"]
        return {
            'bins': [1, 5, 10, 20, 50, 100, 250, 500],
            'probs': [0.5, 0.3, 0.1, 0.05, 0.03, 0.015, 0.004, 0.001]
        }

    def random_point_in_polygon(self, polygon):
        minx, miny, maxx, maxy = polygon.bounds
        for _ in range(100):
            x = self.rng.uniform(minx, maxx)
            y = self.rng.uniform(miny, maxy)
            p = Point(x, y)
            if polygon.contains(p):
                return p
        return polygon.centroid

    def generate_employers(self, year=None):
        year = year if year else self.config.get("year", self.start_year)
        municipalities = self.config.get("municipalities", [])
        # Loop över kommuner (t.ex. för batch/scenario)
        all_employers = []
        for municipal_code in municipalities:
            employer_cfg = self.config['employer_distribution']
            layers_cfg = employer_cfg['layers'] if 'layers' in employer_cfg else [employer_cfg]
            # 1. Läs in zoner från samtliga lager
            all_zones = []
            total_weight = 0
            for layer_cfg in layers_cfg:
                layer_name = layer_cfg['name'] if 'name' in layer_cfg else layer_cfg['layer']
                weight_field = layer_cfg.get('weight_field', 'num_workplaces')
                gdf = self.fetch_zones(layer_name, weight_field, municipal_code, year)
                all_zones.append(gdf)
                total_weight += gdf[weight_field].sum()
            all_zones_gdf = pd.concat(all_zones, ignore_index=True)
            all_zones_gdf['prob'] = all_zones_gdf['weight_field'] / total_weight

            # 2. Antal arbetsgivare (totalt eller auto)
            n_employers = employer_cfg.get('n_employers', 'auto')
            if n_employers == 'auto':
                n_employers = int(total_weight)
            # Override per zon
            zone_overrides = employer_cfg.get('zone_overrides', {})

            # Fyll NaN i viktfält med 0 (alternativ: släng raderna helt)
            all_zones_gdf['weight_field'] = all_zones_gdf['weight_field'].fillna(0)

            # Räkna om total_weight EFTER du fyllt NaN till 0!
            total_weight = all_zones_gdf['weight_field'].sum()
            if total_weight == 0:
                raise ValueError("Summan av weight_field är 0 efter hantering av NaN – kan inte fördela arbetsgivare proportionellt!")

            # Beräkna prob på nytt
            all_zones_gdf['prob'] = all_zones_gdf['weight_field'] / total_weight

            # Sätt eventuella återstående NaN (kan bli så om weight_field är 0 och total_weight=0)
            all_zones_gdf['prob'] = all_zones_gdf['prob'].fillna(0)

            # print("DEBUG: total_weight:", total_weight)
            # print("DEBUG: all_zones_gdf[['zone_code', 'weight_field']]")
            # print(all_zones_gdf[['zone_code', 'weight_field']])
            # print("DEBUG: sum(weight_field):", all_zones_gdf['weight_field'].sum())
            # print("DEBUG: prob:", all_zones_gdf['prob'])
            # print("DEBUG: n_employers:", n_employers)

            n_per_zone = (all_zones_gdf['prob'] * n_employers).round().astype(int)
            for zone_code, n in zone_overrides.items():
                mask = all_zones_gdf['zone_code'] == zone_code
                n_per_zone[mask] = n

            # 3. Hämta SNI- och storleksfördelning
            sni_source = employer_cfg.get('sni_source', 'municipality')
            sni = self.fetch_sni_distribution(municipal_code, year, sni_source)
            size_dist = self.get_size_distribution(employer_cfg)

            # 4. Skapa arbetsgivare i DataFrame
            employers = []
            for idx, row in all_zones_gdf.iterrows():
                n_zone = n_per_zone.iloc[idx]
                for _ in range(n_zone):
                    sni_code = self.rng.choice(sni['sni_code'], p=sni['prob'])
                    size = self.rng.choice(size_dist['bins'], p=size_dist['probs'])
                    point = self.random_point_in_polygon(row.geometry)
                    employers.append({
                        'municipal_code': municipal_code,
                        'layer': row['layer'],
                        'zone_code': row['zone_code'],
                        'geometry': point,
                        'sni_code': sni_code,
                        'size': size
                    })
            employer_gdf = gpd.GeoDataFrame(employers, geometry='geometry')
            all_employers.append(employer_gdf)
        return pd.concat(all_employers, ignore_index=True) if all_employers else gpd.GeoDataFrame()

    # ------------- (Exempel på utbyggbar struktur för arbetare och jobb) -------------

    def generate_workers(self, year, n_workers, municipalities, education_levels, sex_ratio):
        sexes = self.rng.choice(["F", "M"], size=n_workers, p=[sex_ratio, 1-sex_ratio])
        education = self.rng.choice(
            ["low", "medium", "high"],
            size=n_workers,
            p=[
                education_levels.get("low", 0.3),
                education_levels.get("medium", 0.5),
                education_levels.get("high", 0.2)
            ]
        )
        workers = pd.DataFrame({
            "worker_id": [f"W{i:05d}" for i in range(n_workers)],
            "municipal_code": self.rng.choice(municipalities, n_workers),
            "sex": sexes,
            "education_level": education,
        })
        return workers

    def generate_jobs(self, year, n_jobs, municipalities):
        jobs = pd.DataFrame({
            "job_id": [f"J{i:05d}" for i in range(n_jobs)],
            "municipal_code": self.rng.choice(municipalities, n_jobs),
            # Här kan du lägga till onet_code, sni_code etc.
        })
        return jobs

    def generate(self, year=None):
        year = year if year else self.config.get("year", self.start_year)
        params = self.get_yearly_params(year)
        # 1. Arbetsgivare
        employers = self.generate_employers(year=year)
        # 2. Workers & Jobs (kan göras spatiala/realistiska med vidareutveckling)
        workers = self.generate_workers(
            year, params["n_workers"], params["municipalities"], params["education_levels"], params["sex_ratio"]
        )
        jobs = self.generate_jobs(year, params["n_jobs"], params["municipalities"])
        # 3. Dummy event queue (kan byggas ut)
        events = pd.DataFrame(columns=["time", "agent_id", "event_type", "params"])
        return workers, jobs, employers, events

# --------------- EXEMPEL PÅ ANVÄNDNING ---------------

if __name__ == "__main__":
    builder = ScenarioBuilder("scenarios/scenario_falun_baseline.yml", db_path="worm.db")
    workers, jobs, employers, events = builder.generate()
    print("Workers:", workers.head())
    print("Jobs:", jobs.head())
    print("Employers:", employers.head())
