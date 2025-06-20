# worm/scenariobuilder.py

import numpy as np
import pandas as pd
import geopandas as gpd
import time
from shapely import wkt

from core.geography.geoutils import assign_deso_code, random_points_in_polygon
from core.log import log

class ScenarioBuilder:
    DEFAULT_WEIGHT_FIELDS = {
        "business_zones": ["num_workplaces", "num_employed", "population", "area_ha"],
        "commercial_zones": ["num_workplaces", "num_employed", "population", "area_ha"],
        "small_localities": ["num_workplaces", "num_employed", "population", "area_ha"],
        "urban_areas": ["num_workplaces", "num_employed", "population", "area_ha"],
    }

    def __init__(self, conn, cfg_reader, geoworld=None): 
        """
        config: YAML-dict (laddad)
        conn: sqlite3 connection
        cfg_reader: instans av ConfigReader
        """
        self.conn = conn
        self.cfg_reader = cfg_reader  # Kortnamn för enkel access
        self.seed = self.cfg_reader.config.get("seed", None)
        self.rng = np.random.default_rng(self.seed)
        self._sni_cache = {}
        self.geoworld = geoworld

    def print_employer_size_stats(self, employers_df, employer_dist_cfg):
        bins, probs, class_names = self.get_size_distribution_from_config(employer_dist_cfg)
        class_ranges = bins
        counts = {name: 0 for name in class_names}
        for size in employers_df['size']:
            for name, (min_s, max_s) in zip(class_names, class_ranges):
                if min_s <= size <= max_s:
                    counts[name] += 1
                    break
        log("Storleksfördelning (antal arbetsgivare per klass):")
        for name, (min_s, max_s) in zip(class_names, class_ranges):
            log(f"  {name:12}: {counts[name]:5d} st ({min_s}-{max_s} anställda)")

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

    def fetch_sni_distribution(self, municipal_code, year, deso_code=None, sni_source="municipality"):
        from core.database.utils import fetch_with_fallback
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
        self._sni_cache[cache_key] = sni_df
        return sni_df

    def random_points_in_polygon(self, polygon, n_points):
        import geopandas as gpd
        gdf = gpd.GeoSeries([polygon])
        result = gdf.sample_points(n_points)[0]
        if result.geom_type == "Point":
            return [result]
        elif result.geom_type == "MultiPoint":
            return list(result.geoms)
        else:
            raise ValueError(f"Oväntad geometri från sample_points: {result.geom_type}")

    def get_size_distribution_from_config(self, employer_dist_cfg):
        size_cfg = employer_dist_cfg['employer_size_distribution']
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
            probs = [p / total for p in probs]
        return bins, probs, list(size_cfg.keys())

    def generate_employers_with_target_jobs(
        self, 
        year, 
        municipal_code, 
        target_jobs, 
        employer_dist_cfg, 
        sni_source="municipality"
    ):
        allocation_order = employer_dist_cfg['allocation_order']
        layer_configs = employer_dist_cfg['layer_configs']
        layer_gdfs = {}
        for layer in allocation_order:
            try:
                gdf = self.fetch_zones(layer, layer_configs[layer]['weight_field'], municipal_code, year)
                layer_gdfs[layer] = gdf
            except ValueError as e:
                log(f"[VARNING] {e} -- Lager '{layer}' hoppas över för kommun {municipal_code}.")
                continue

        bins, probs, class_names = self.get_size_distribution_from_config(employer_dist_cfg)
        rng = self.rng

        employers = []
        n_jobs = 0
        size_idx = 0

        while n_jobs < target_jobs:
            class_i = rng.choice(len(bins), p=probs)
            size = rng.integers(low=bins[class_i][0], high=bins[class_i][1] + 1)
            all_layers = list(layer_gdfs.keys())
            layer = rng.choice(all_layers)
            gdf = layer_gdfs[layer]
            row = gdf.sample(1, random_state=None).iloc[0]
            pt = self.random_points_in_polygon(row.geometry, 1)[0]
            deso_code = row.get('deso_code', None)

            if sni_source == 'deso' and deso_code is not None:
                sni_dist = self.fetch_sni_distribution(municipal_code, year, deso_code=deso_code, sni_source='deso')
            else:
                sni_dist = self.fetch_sni_distribution(municipal_code, year, sni_source='municipality')
            sni_code = rng.choice(sni_dist['sni_code'], p=sni_dist['prob'])

            employers.append({
                'municipal_code': municipal_code,
                'layer': layer,
                'zone_code': row.get('zone_code', None),
                'x': pt.x,
                'y': pt.y,
                'geometry': pt,
                'size': size,
                'sni_code': sni_code
            })
            n_jobs += size

        overflow = n_jobs - target_jobs
        if overflow > 0:
            employers[-1]['size'] -= overflow

        employers_df = gpd.GeoDataFrame(employers, geometry='geometry')
        log(f"Antal arbetsgivare: {len(employers_df)} (mål: {target_jobs} jobb)")
        log(f"Total antal jobb (summa storlek): {employers_df['size'].sum()}")
        return employers_df

    def generate_jobs_from_employers(self, employers_df):
        """
        Skapar DataFrame med alla jobb. 
        Alla har nödvändiga kolumner för utility-matchning: job_id, chi, xi, x, y.
        """
        jobs = []
        job_id = 0
        for idx, row in employers_df.iterrows():
            geom = row['geometry']
            x, y = geom.x, geom.y
            rng = self.rng
            chi = rng.uniform(0, 1)
            xi = rng.uniform(0, 2 * np.pi)
            for _ in range(int(row['size'])):
                jobs.append({
                    "job_id": f"J{job_id:05d}",
                    "employer_id": row.get('employer_id', idx),     # använd employer_id om det finns, annars index
                    "individual_id" : None,                         # Ingen matchning än
                    "municipal_code": row['municipal_code'],
                    "layer": row['layer'],
                    "zone_code": row['zone_code'],
                    "employer_size": row['size'],
                    "sni_code": row['sni_code'],
                    "geometry": geom,
                    "chi": chi,
                    "xi": xi,
                    "x": x,
                    "y": y,
                })
                job_id += 1

        df = pd.DataFrame(jobs)
        df["deso_code"] = assign_deso_code(df, self.geoworld.deso_zones, x_col="x", y_col="y")

        return df

    def generate_individuals(self, municipal_code, population, workforce_ratio, unemployment_rate):
        """
        Vektoriserad version: individer fördelas över DeSO-zoner enligt folkmängd,
        och koordinater slumpar vi i batch per DeSO.
        """
        rng = self.rng

        n_workforce = int(round(population * workforce_ratio))
        n_not_in_labor_force = population - n_workforce

        # Hämta DeSO med befolkning > 0
        deso_gdf = self.geoworld.deso_zones
        deso_gdf = deso_gdf[(deso_gdf["municipal_code"] == str(municipal_code)) & (deso_gdf["population"] > 0)].reset_index(drop=True)

        if len(deso_gdf) == 0:
            raise ValueError(f"Inga DeSO-zoner med befolkning > 0 hittades för kommun {municipal_code}")

        pop_weights = deso_gdf["population"].values
        pop_probs = pop_weights / pop_weights.sum()

        N = population  # total number of individuals

        # Hur många individer ska skapas i varje DeSO? Multinomial!
        n_per_deso = rng.multinomial(N, pop_probs)
        # Bygg upp alla individer i vektoriserad form
        records = []
        status_list = ["unemployed"] * n_workforce + ["not_in_labor_force"] * n_not_in_labor_force
        rng.shuffle(status_list)  # Slumpa ordningen direkt

        i = 0
        for deso_idx, n_ind in enumerate(n_per_deso):
            if n_ind == 0:
                continue
            deso_row = deso_gdf.iloc[deso_idx]
            # Slumpa n_ind punkter i polygonen
            points = self.random_points_in_polygon(deso_row.geometry, n_ind)
            for pt in points:
                # Vi tar status-listan i ordning
                records.append({
                    'municipal_code': municipal_code,
                    'status': status_list[i],
                    'job_id': None,
                    'deso_code': deso_row['deso_code'],
                    'x': pt.x,
                    'y': pt.y,
                    'geometry': pt
                })
                i += 1

        df = pd.DataFrame(records)
        df["individual_id"] = [f"{municipal_code}_i{ix:06d}" for ix in range(len(df))]
        rng = self.rng

        indiv_defaults = self.cfg_reader.config.get('defaults', {}).get('individuals', {})
        prop_cfg = indiv_defaults.get('propensities', {})

        # För varje propensity:
        for name in ['start_education', 'internal_training', 'quit_job', 'career_break', 'internal_job_change']:
            pblock = prop_cfg.get(name, {})
            mean = pblock.get('mean', 0.1)  # Välj defaultvärde
            std = pblock.get('std', 0.05)
            col = f'propensity_{name}'
            df[col] = np.clip(
                rng.normal(mean, std, size=len(df)), 0, 1
            )

        # Slumpa individens position inom occupation space
        df["chi"] = rng.uniform(0, 1, size=len(df))
        df["xi"] = rng.uniform(0, 2 * np.pi, size=len(df))
        # H för individen
        H_cfg = indiv_defaults.get('initial_H', {})
        H_min = H_cfg.get('min', 0.08)
        H_max = H_cfg.get('max', 0.25)
        df['H'] = rng.uniform(H_min, H_max, size=len(df))

        return df

    def generate(self, year=None):
        t0 = time.time()
        log(f"[TIMER] generate: startat")
        municipalities = self.cfg_reader.config.get("municipalities", [])
        if not municipalities:
            raise ValueError("Inga kommuner angivna i scenariot.")
        if year is None:
            year = self.cfg_reader.config.get("start_year", 2024)

        all_individuals = []
        all_jobs = []
        all_employers = []
        all_events = []

        unemployment_rate = self.cfg_reader.config.get("unemployment_rate", 0.0)

        for municipal_code in municipalities:
            t1 = time.time()
            log(f"\n--- Kommun {municipal_code} ---")
            population = self.cfg_reader.get_population(municipal_code)[0]
            workforce_ratio = self.cfg_reader.get_workforce_ratio(municipal_code)[0]
            local_unemployment_rate = self.cfg_reader.get_unemployment_rate(municipal_code, year)[0]

            # Individer
            t_ind0 = time.time()
            individuals = self.generate_individuals(
                municipal_code,
                population,
                workforce_ratio,
                local_unemployment_rate
            )
            t_ind1 = time.time()
            log(f"[TIMER]  ...generera individer: {t_ind1-t_ind0:.2f} s")

            # Arbetsgivare
            t_emp0 = time.time()
            workforce = int(round(population * workforce_ratio))
            n_unemployed = int(round(workforce * local_unemployment_rate))
            target_jobs = workforce - n_unemployed

            employer_dist_cfg = self.cfg_reader.get_employer_distribution(municipal_code)
            employers = self.generate_employers_with_target_jobs(
                year,
                municipal_code,
                target_jobs,
                employer_dist_cfg
            )
            t_emp1 = time.time()
            log(f"[TIMER]  ...generera arbetsgivare: {t_emp1-t_emp0:.2f} s")

            # Jobb
            t_job0 = time.time()
            jobs = self.generate_jobs_from_employers(employers)
            t_job1 = time.time()
            log(f"[TIMER]  ...generera jobb: {t_job1-t_job0:.2f} s")

            self.print_employer_size_stats(employers, employer_dist_cfg)

            all_individuals.append(individuals)
            all_employers.append(employers)
            all_jobs.append(jobs)
            log(f"[TIMER] Kommun {municipal_code} totalt: {time.time()-t1:.2f} s")

        t2 = time.time()
        all_individuals = pd.concat(all_individuals, ignore_index=True)
        all_jobs = pd.concat(all_jobs, ignore_index=True)
        all_employers = gpd.GeoDataFrame(pd.concat(all_employers, ignore_index=True), geometry='geometry')
        events = pd.DataFrame(columns=["time", "agent_id", "event_type", "params"])
        t3 = time.time()

        log(f"[TIMER] Sammanfogning/efterarbete: {t3-t2:.2f} s")
        log(f"[TIMER] generate totalt {t3-t0:.2f} s")
        return all_individuals, all_jobs, all_employers, events


# --- Slut på ScenarioBuilder ---
