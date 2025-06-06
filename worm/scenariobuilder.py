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
    # Här mappas lager mot typiska weight_fields (prövas i turordning)
    DEFAULT_WEIGHT_FIELDS = {
        "business_zones": ["num_workplaces", "num_employed", "population", "area_ha"],
        "commercial_zones": ["num_workplaces", "num_employed", "population", "area_ha"],
        "small_localities": ["num_workplaces", "num_employed", "population", "area_ha"],
        "urban_areas": ["num_workplaces", "num_employed", "population", "area_ha"],
        # "rural": ["area_ha"]  # Hanteras separat, inte explicit tabell
    }

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

    # --- Allmän parameterhantering och interpolation ---
    # (Ingen förändring mot tidigare. Behåll om du använder yearly-parametrar)
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
        return {
            "n_workers": n_workers,
            "n_jobs": n_jobs,
            "municipalities": municipalities,
            "education_levels": education_levels,
            "sex_ratio": sex_ratio,
            "age_range": age_range,
            "occupation_distribution": occupation_distribution,
        }

    def get_size_distribution_from_config(self):
        """
        Bygger bins/probs-listor från employer_size_distribution i config.
        bins: [(min_size, max_size), ...]
        probs: [ratio, ...] summerar till 1.
        """
        size_cfg = self.config['employer_distribution']['employer_size_distribution']
        bins = []
        probs = []
        for klass in size_cfg.values():
            min_size = klass.get('min_size', 1)
            max_size = klass['max_size']
            ratio = klass['ratio']
            bins.append((min_size, max_size))
            probs.append(ratio)
        total = sum(probs)
        if not np.isclose(total, 1.0):
            probs = [p / total for p in probs]  # Normalisera
        return bins, probs


    # --- Lager och spatial logik ---
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
        if weight_field not in gdf.columns:
            gdf[weight_field] = 0
        gdf['weight_field'] = gdf[weight_field].fillna(0)
        return gdf


    def pick_weight_field(self, gdf, layer_name):
        """Returnera första weight_field i gdf enligt DEFAULT_WEIGHT_FIELDS för lager."""
        for candidate in self.DEFAULT_WEIGHT_FIELDS.get(layer_name, []):
            if candidate in gdf.columns:
                return candidate
        raise ValueError(f"Inget weight_field funnet för {layer_name}")

    # --- SNI-fördelning ---
    def fetch_sni_distribution(self, municipal_code, year, deso_code=None, sni_source="municipality"):
        # Skapa cache-nyckel
        cache_key = (deso_code, year) if deso_code else (municipal_code, year)
        if cache_key in self._sni_cache:
            return self._sni_cache[cache_key]
        if deso_code:
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
        else:
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
        self._sni_cache[cache_key] = sni_df
        return sni_df

    # --- Random punkter inom polygon (snabb GeoPandas) ---
    def random_points_in_polygon(self, polygon, n_points):
        gdf = gpd.GeoSeries([polygon])
        result = gdf.sample_points(n_points)[0]  # Kan vara Point eller MultiPoint
        if result.geom_type == "Point":
            return [result]
        elif result.geom_type == "MultiPoint":
            return list(result.geoms)
        else:
            raise ValueError(f"Oväntad geometri från sample_points: {result.geom_type}")


    # --- Totalt antal arbetsställen för kommunen ---
    def get_total_workplaces_for_municipality(self, municipal_code, year):
        filters = {"municipal_code": municipal_code}
        df, fallback_year = fetch_with_fallback(
            self.conn,
            table="employment_municipality_sni",
            filters=filters,
            year_col="year",
            desired_year=year,
            columns="workplaces"
        )
        total_workplaces = df['workplaces'].sum()
        if total_workplaces == 0:
            raise ValueError(f"Inga arbetsställen hittades för kommun {municipal_code}, år {fallback_year} (ursprungligen {year})")
        return int(total_workplaces), fallback_year

    def generate_employers(self, year=None):
        t0 = time.time()
        year = year or self.config.get("year", self.start_year)
        municipal_code = self.config['municipalities'][0]
        population = self.config.get("population")
        emp_dist_cfg = self.config['employer_distribution']

        # 1. Antal arbetsgivare
        n_employers = emp_dist_cfg.get('n_employers', 'auto')
        if n_employers == 'auto':
            ratio = emp_dist_cfg.get('employer_ratio_per_population', 0.09)
            n_employers = int(population * ratio)
        else:
            n_employers = int(n_employers)

        # 2. Storleksklasser från config och generera storlekar
        bins, probs = self.get_size_distribution_from_config()
        size_cfg = self.config['employer_distribution']['employer_size_distribution']

        # Fördela arbetsgivare på klasser
        class_indices = self.rng.choice(len(bins), size=n_employers, p=probs)
        sizes_list = [self.rng.integers(low=bins[i][0], high=bins[i][1] + 1) for i in class_indices]

        # Statistik per klass (före zonallokering)
        class_names = list(size_cfg.keys())
        class_ranges = [(klass.get('min_size', 1), klass['max_size']) for klass in size_cfg.values()]
        counts = {name: 0 for name in class_names}
        for size in sizes_list:
            for name, (min_s, max_s) in zip(class_names, class_ranges):
                if min_s <= size <= max_s:
                    counts[name] += 1
                    break

        print("Storleksfördelning (antal arbetsgivare per klass):")
        for name, (min_s, max_s) in zip(class_names, class_ranges):
            print(f"  {name:12}: {counts[name]:5d} st ({min_s}-{max_s} anställda)")

        # 3. Hämta lagerdata
        allocation_order = emp_dist_cfg['allocation_order']
        layer_configs = emp_dist_cfg['layer_configs']
        layer_gdfs = {}
        for layer in allocation_order:
            gdf = self.fetch_zones(layer, layer_configs[layer]['weight_field'], municipal_code, year)
            layer_gdfs[layer] = gdf

        # 4. Allokera arbetsgivare till zoner
        remaining = n_employers
        allocation = {}
        for layer in allocation_order:
            gdf = layer_gdfs[layer]
            weight_field = layer_configs[layer]['weight_field']
            gdf[weight_field] = gdf[weight_field].fillna(0)
            total_weight = gdf[weight_field].sum()
            if total_weight == 0:
                allocation[layer] = [0] * len(gdf)
                continue
            n_this_layer = min(remaining, int(total_weight))
            probs_z = gdf[weight_field] / total_weight
            n_per_zone = (probs_z * n_this_layer).round().astype(int)
            allocation[layer] = n_per_zone
            remaining -= n_per_zone.sum()
            if remaining <= 0:
                break

        # 5. Placera arbetsgivare, tilldela storlek och SNI
        employers = []
        sni_source = emp_dist_cfg.get('sni_source', 'municipality')
        size_idx = 0
        for layer in allocation_order:
            gdf = layer_gdfs[layer]
            n_per_zone = allocation[layer]
            for idx, row in gdf.iterrows():
                n_zone = n_per_zone.iloc[idx] if hasattr(n_per_zone, "iloc") else n_per_zone[idx]
                if n_zone == 0:
                    continue
                points = self.random_points_in_polygon(row.geometry, n_zone)
                deso_code = row.get('deso_code', None)
                if sni_source == 'deso' and deso_code is not None:
                    sni_dist = self.fetch_sni_distribution(municipal_code, year, deso_code=deso_code, sni_source='deso')
                else:
                    sni_dist = self.fetch_sni_distribution(municipal_code, year, sni_source='municipality')
                sni_codes = self.rng.choice(sni_dist['sni_code'], size=n_zone, p=sni_dist['prob'])
                # Tilldela storlekar från sizes_list (redan dragen, ingen ny sampling!)
                zone_sizes = sizes_list[size_idx:size_idx + n_zone]
                size_idx += n_zone
                for point, sni_code, size in zip(points, sni_codes, zone_sizes):
                    employers.append({
                        'municipal_code': municipal_code,
                        'layer': layer,
                        'zone_code': row.get('zone_code', None),
                        'geometry': point,
                        'size': size,
                        'sni_code': sni_code
                    })

        t1 = time.time()
        print(f"[TIMER] generate_employers totalt {t1-t0:.2f} s")
        employers_df = gpd.GeoDataFrame(employers, geometry='geometry')
        print(f"Antal arbetsgivare: {len(employers_df)}")
        print(f"Total antal jobb (summa storlek): {employers_df['size'].sum()}")
        return employers_df

    # --- Arbetare och jobb ---
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

    def generate_jobs_from_employers(self, employers_df):
        jobs = []
        job_id = 0
        for idx, row in employers_df.iterrows():
            for i in range(int(row['size'])):
                jobs.append({
                    "job_id": f"J{job_id:05d}",
                    "employer_id": idx,  # eller row['employer_id'] om du har det
                    "municipal_code": row['municipal_code'],
                    "layer": row['layer'],
                    "zone_code": row['zone_code'],
                    "sni_code": row['sni_code'],
                    "geometry": row['geometry'],
                    # lägg till andra fält om du vill
                })
                job_id += 1
        return pd.DataFrame(jobs)


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
        jobs = self.generate_jobs_from_employers(employers)
        t3 = time.time()
        print(f"[TIMER] generate_jobs_from_employers tog {t3-t2:.2f} s")
        events = pd.DataFrame(columns=["time", "agent_id", "event_type", "params"])
        t4 = time.time()
        print(f"[TIMER] generate totalt {t4-t0:.2f} s")
        return workers, jobs, employers, events

# --- Slut på ScenarioBuilder ---
