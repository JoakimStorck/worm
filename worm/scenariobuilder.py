# scenariobuilder.py

import yaml
import numpy as np
import pandas as pd
import sqlite3
import geopandas as gpd
from shapely import wkt
from shapely.geometry import Point
from worm.database.utils import fetch_with_fallback

import time

class ScenarioBuilder:
    def __init__(self, config_path, db_path=None, geoworld=None):
        with open(config_path, "r") as f:
            self.config = yaml.safe_load(f)
        self.geoworld = geoworld
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path) if db_path else None
        self._sni_cache = {}

        self.seed = self.config.get("seed", None)
        self.rng = np.random.default_rng(self.seed)
        self.start_year = self.config.get("start_year", 2024)
        self.end_year = self.config.get("end_year", 2024)
        self.size_distribution_by_sni = self.load_size_distributions()

    # --- Allmän parameter- och interpoleringslogik ---
    @staticmethod
    def interpolate_linear(start, end, start_year, end_year, year):
        if year <= start_year:
            return start
        if year >= end_year:
            return end
        return start + (end - start) * (year - start_year) / (end_year - start_year)

    @staticmethod
    def step_value(changes, default, year):
        val = default
        for change in sorted(changes, key=lambda c: c["year"]):
            if year >= change["year"]:
                val = change["value"]
            else:
                break
        return val

    @classmethod
    def get_param_value(cls, param, year, default=None):
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
                        return cls.interpolate_linear(values[i-1], values[i], years[i-1], years[i], year)
            elif "curve" in param:
                if param["curve"] == "linear":
                    return cls.interpolate_linear(param["start"], param["end"], param["start_year"], param["end_year"], year)
                elif param["curve"] == "step":
                    return cls.step_value(param["changes"], default, year)
            else:
                return param.get("constant", default)
        return param if param is not None else default

    def get_yearly_params(self, year):
        n_workers = int(self.get_param_value(self.config.get("n_workers"), year, default=0))
        n_jobs = int(self.get_param_value(self.config.get("n_jobs"), year, default=0))
        municipalities = self.config.get("municipalities", [])
        education_levels = self.config.get("education_levels", {})
        sex_ratio = float(self.get_param_value(self.config.get("sex_ratio"), year, default=0.5))
        age_range = self.config.get("age_range", [20, 64])
        occupation_distribution = self.config.get("occupation_distribution", "random")
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

    # --- Storleksfördelning per SNI/bransch ---
    def load_size_distributions(self):
        # TODO: Ladda från fil, databas eller byggs på här
        # Exempel: SNI-kod: bins/probs
        return {
            "10": {"bins": [1, 5, 10, 20], "probs": [0.5, 0.3, 0.15, 0.05]},
            "47": {"bins": [1, 3, 7, 15], "probs": [0.7, 0.2, 0.08, 0.02]},
            "default": {"bins": [1, 5, 10, 20], "probs": [0.5, 0.3, 0.15, 0.05]},
        }

    def get_size_distribution(self, sni_code=None):
        if sni_code and sni_code in self.size_distribution_by_sni:
            return self.size_distribution_by_sni[sni_code]
        return self.size_distribution_by_sni["default"]

    # --- Zoner (lager), spatial logik ---
    def fetch_zones(self, layer_name, weight_field, municipal_code, year=None):
        cursor = self.conn.execute(f"PRAGMA table_info({layer_name})")
        columns = [row[1] for row in cursor.fetchall()]
        code_col = None
        if 'municipal_code' in columns:
            code_col = 'municipal_code'
        elif 'municipality_code' in columns:
            code_col = 'municipality_code'

        sql = f"SELECT * FROM {layer_name}"
        params = []
        filters = []
        if code_col:
            filters.append(f"{code_col} = ?")
            params.append(municipal_code)
        if 'year' in columns:
            years = pd.read_sql(
                f"SELECT DISTINCT year FROM {layer_name}" + (f" WHERE {code_col} = ?" if code_col else ""),
                self.conn, params=params
            )
            if not years.empty:
                latest_year = years['year'].max()
                filters.append("year = ?")
                params.append(latest_year)
        if filters:
            sql += " WHERE " + " AND ".join(filters)
        df = pd.read_sql(sql, self.conn, params=params)
        if df.empty:
            raise ValueError(f"Inga zoner hittades i lager '{layer_name}' (filter: {filters})")
        if 'geom_wkt' not in df.columns:
            raise ValueError(f"Kolumnen 'geom_wkt' saknas i {layer_name}")
        df['geometry'] = df['geom_wkt'].apply(wkt.loads)
        gdf = gpd.GeoDataFrame(df, geometry='geometry')
        gdf['layer'] = layer_name
        gdf['weight_field'] = gdf[weight_field].fillna(0)
        return gdf

    # --- SNI-fördelning: DeSO eller kommunnivå beroende på lager ---
    def fetch_sni_distribution(self, municipal_code, year, deso_code=None, sni_source="municipality"):
        # Skapa cache-nyckel
        cache_key = (deso_code, year) if deso_code else (municipal_code, year)
        if cache_key in self._sni_cache:
            return self._sni_cache[cache_key]
        if deso_code:
            # SNI på DeSO-nivå
            sni_df, used_year = fetch_with_fallback(
                self.conn,
                table="employment_deso_sni",
                filters={'deso_code': deso_code},
                year_col='year',
                desired_year=year,
                columns="sni_code, employed"
            )
            total = sni_df['employed'].sum()
            if total > 0:
                sni_df['prob'] = sni_df['employed'] / total
            else:
                sni_df['prob'] = 1.0 / len(sni_df)
            if used_year != year:
                print(f"Varning: DeSO-SNI saknas för {deso_code} år {year}. Fallback till år {used_year}.")
            return sni_df
        else:
            # Kommunnivå
            sni_df, used_year = fetch_with_fallback(
                self.conn,
                table="employment_municipality_sni",
                filters={'municipal_code': municipal_code},
                year_col='year',
                desired_year=year,
                columns="sni_code, workplaces"
            )
            total = sni_df['workplaces'].sum()
            if total > 0:
                sni_df['prob'] = sni_df['workplaces'] / total
            else:
                sni_df['prob'] = 1.0 / len(sni_df)
            if used_year != year:
                print(f"Varning: SNI-data saknas för {municipal_code} år {year}. Fallback till år {used_year}.")
            return sni_df

    # --- Spatial join mot DeSO ---
    def spatial_join_zones_to_deso(self, gdf):
        # Spatial join: hitta deso_code för varje zon (polygon-in-polygon)
        deso_gdf = pd.read_sql("SELECT deso_code, geom_wkt FROM deso", self.conn)
        deso_gdf['geometry'] = deso_gdf['geom_wkt'].apply(wkt.loads)
        deso_gdf = gpd.GeoDataFrame(deso_gdf, geometry='geometry')
        return gpd.sjoin(gdf, deso_gdf[['deso_code', 'geometry']], how='left', predicate='intersects')

    import geopandas as gpd

    def random_points_in_polygon(self, polygon, n_points):
        # polygon är ett shapely-objekt
        gdf = gpd.GeoSeries([polygon])
        # Detta är snabbt och fungerar även för svåra former
        multipoint = gdf.sample_points(n_points)[0]  # returns MultiPoint
        points = list(multipoint.geoms)
        return points


    import time

    def generate_employers(self, year=None):
        t0 = time.time()
        year = year if year else self.config.get("year", self.start_year)
        municipalities = self.config.get("municipalities", [])
        all_employers = []

        # Summeringsvariabler
        sum_fetch_sni = 0.0
        sum_points = 0.0
        sum_size = 0.0
        sum_zon = 0.0

        for municipal_code in municipalities:
            employer_cfg = self.config['employer_distribution']
            layers_cfg = employer_cfg['layers'] if 'layers' in employer_cfg else [employer_cfg]
            all_zones = []
            total_weight = 0
            deso_layers = {"urban_areas", "small_localities", "business_zones"}
            use_deso = any((l['name'] if 'name' in l else l['layer']) in deso_layers for l in layers_cfg)
            for layer_cfg in layers_cfg:
                layer_name = layer_cfg['name'] if 'name' in layer_cfg else layer_cfg['layer']
                weight_field = layer_cfg.get('weight_field', 'num_workplaces')
                gdf = self.fetch_zones(layer_name, weight_field, municipal_code, year)
                if use_deso and 'deso_code' not in gdf.columns:
                    gdf = self.spatial_join_zones_to_deso(gdf)
                all_zones.append(gdf)
                total_weight += gdf[weight_field].sum()
            all_zones_gdf = pd.concat(all_zones, ignore_index=True)
            all_zones_gdf['weight_field'] = all_zones_gdf['weight_field'].fillna(0)
            total_weight = all_zones_gdf['weight_field'].sum()
            if total_weight == 0:
                raise ValueError("Summan av weight_field är 0 – kan inte fördela arbetsgivare proportionellt! Kontrollera data.")
            all_zones_gdf['prob'] = all_zones_gdf['weight_field'] / total_weight
            all_zones_gdf['prob'] = all_zones_gdf['prob'].fillna(0)

            n_employers = employer_cfg.get('n_employers', 'auto')
            if n_employers == 'auto':
                n_employers = int(total_weight)
            zone_overrides = employer_cfg.get('zone_overrides', {})
            n_per_zone = (all_zones_gdf['prob'] * n_employers).round().astype(int)
            for zone_code, n in zone_overrides.items():
                mask = all_zones_gdf['zone_code'] == zone_code
                n_per_zone[mask] = n

            employers = []
            for idx, row in all_zones_gdf.iterrows():
                t_zon_start = time.time()
                n_zone = n_per_zone.iloc[idx]
                if n_zone == 0:
                    continue
                deso_code = row.get('deso_code') if use_deso else None

                t_fetch_sni0 = time.time()
                sni_dist = self.fetch_sni_distribution(municipal_code, year, deso_code if use_deso else None)
                t_fetch_sni1 = time.time()
                fetch_sni_time = t_fetch_sni1 - t_fetch_sni0
                sum_fetch_sni += fetch_sni_time

                t_points0 = time.time()
                points = self.random_points_in_polygon(row.geometry, n_zone)
                t_points1 = time.time()
                points_time = t_points1 - t_points0
                sum_points += points_time

                t_size0 = time.time()
                sni_codes = self.rng.choice(sni_dist['sni_code'], size=n_zone, p=sni_dist['prob'])

                # Cache storleksfördelning per SNI-kod för att undvika upprepade anrop
                size_dist_cache = {}
                sizes = []
                for sni in sni_codes:
                    if sni not in size_dist_cache:
                        size_dist_cache[sni] = self.get_size_distribution(sni)
                    dist = size_dist_cache[sni]
                    sizes.append(self.rng.choice(dist['bins'], p=dist['probs']))

                #sizes = [self.rng.choice(self.get_size_distribution(sni)['bins'], p=self.get_size_distribution(sni)['probs']) for sni in sni_codes]
                t_size1 = time.time()
                size_time = t_size1 - t_size0
                sum_size += size_time

                for point, sni_code, size in zip(points, sni_codes, sizes):
                    employers.append({
                        'municipal_code': municipal_code,
                        'layer': row['layer'],
                        'zone_code': row['zone_code'],
                        'deso_code': deso_code,
                        'geometry': point,
                        'sni_code': sni_code,
                        'size': size
                    })
                t_zon_slut = time.time()
                zon_time = t_zon_slut - t_zon_start
                sum_zon += zon_time

                print(f"[TIMER] zon {idx}: total {zon_time:.2f}s | fetch_sni {fetch_sni_time:.2f}s | points {points_time:.2f}s | size {size_time:.2f}s")
            employer_gdf = gpd.GeoDataFrame(employers, geometry='geometry')
            all_employers.append(employer_gdf)
        t1 = time.time()
        print(f"[TIMER] generate_employers totalt {t1-t0:.2f} s")
        print(f"[TIMER] SUMMA zoner: {sum_zon:.2f} s | fetch_sni: {sum_fetch_sni:.2f} s | points: {sum_points:.2f} s | size: {sum_size:.2f} s")
        return pd.concat(all_employers, ignore_index=True) if all_employers else gpd.GeoDataFrame()

    # --- Arbetare och jobb: samma logik som tidigare ---
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
        })
        return jobs

    def generate(self, year=None):
        t0 = time.time()
        print(f"[TIMER] generate: startat")
        year = year if year else self.config.get("year", self.start_year)
        params = self.get_yearly_params(year)
        t1 = time.time()
        employers = self.generate_employers(year=year)
        t2 = time.time()
        print(f"[TIMER] generate_employers tog {t2-t1:.2f} s")
        workers = self.generate_workers(
            year, params["n_workers"], params["municipalities"], params["education_levels"], params["sex_ratio"]
        )
        jobs = self.generate_jobs(year, params["n_jobs"], params["municipalities"])
        events = pd.DataFrame(columns=["time", "agent_id", "event_type", "params"])
        t3 = time.time()
        print(f"[TIMER] generate totalt {t3-t0:.2f} s")
        return workers, jobs, employers, events

# --- Slut på ScenarioBuilder ---
