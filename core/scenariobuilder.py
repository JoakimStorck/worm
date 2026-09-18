# worm/scenariobuilder.py

import numpy as np
import pandas as pd
import geopandas as gpd
import time
from shapely import wkt
import sqlite3

from core.database.utils import kommunkod
from core.geography.geoutils import assign_deso_code, random_points_in_polygon
from core.log import log
from core.participation import profil
from core.occupations.utils import sample_from_centers_jitter, sample_centers_xy_jitter

def _lagervikter(layer_gdfs, municipal_code=None):
    """Sannolikheter för lager och zon ur kolumnen weight_field.

    Returnerar (lager_namn, lager_p, zon_vikt): lagrets andel av kommunens
    sammanlagda vikt, och inom varje lager zonernas andel av lagrets vikt.

    Ett lager utan viktunderlag faller tillbaka på likformigt INOM lagret men
    får bara sin zonandel av lagervalet -- inte en fjärdedel bara för att det
    finns. Skillnaden syns i småorter: de är många och små, och med likformigt
    lagerval fick de lika stor andel av arbetsgivarna som tätorterna.
    """
    namn, vikt, zon = [], [], {}
    for lager, gdf in layer_gdfs.items():
        if gdf is None or not len(gdf):
            continue
        w = pd.to_numeric(gdf.get("weight_field"), errors="coerce")
        w = (w if w is not None else pd.Series(dtype=float)).fillna(0.0).clip(lower=0.0)
        if len(w) != len(gdf) or w.sum() <= 0:
            w = pd.Series(1.0, index=gdf.index)
            log(f"[VARNING] Lager '{lager}' saknar viktunderlag i kommun "
                f"{municipal_code} -- likformigt inom lagret.")
        namn.append(lager)
        vikt.append(float(w.sum()))
        zon[lager] = (w / w.sum()).to_numpy()
    if not namn:
        raise ValueError(f"Inga zonlager med geometri för kommun {municipal_code}")
    p = np.array(vikt, dtype=float)
    return namn, p / p.sum(), zon


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

        self.onet_space_df = self.load_onet_occupation_space_table()


    def _branschstruktur(self, max_storlek):
        from core.bransch import Branschstruktur
        nyckel = int(max_storlek) if max_storlek is not None else None
        if getattr(self, "_bransch_cache", (None, None))[0] != nyckel:
            self._bransch_cache = (nyckel, Branschstruktur(self.conn, max_storlek))
        return self._bransch_cache[1]

    def print_employer_size_stats(self, employers_df, employer_dist_cfg):
        from core.bransch import STORLEKSKLASSER, storleksklass
        klass = employers_df['size'].map(storleksklass)
        log("Arbetsställen per storleksklass (antal, andel av jobben):")
        jobb = employers_df['size'].sum()
        for namn, _, _ in STORLEKSKLASSER:
            i = klass == namn
            log(f"  {namn:16}: {int(i.sum()):5d} st  {employers_df.loc[i, 'size'].sum() / jobb:6.1%}")
        andel = employers_df.groupby('sni_code')['size'].sum() / jobb
        log("Jobb per bransch: " + "  ".join(f"{k} {v:.1%}" for k, v in andel.items()))

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
            # TOTALEN ÄR INTE EN NÄRINGSGREN. Med den kvar i urvalet skulle
            # hälften av arbetsgivarna dras till en kod som betyder "alla
            # branscher". Före rättningen av extract_sni_code bar totalen
            # dessutom koden A, och drogs alltså som jordbruk.
            sni_df = sni_df[sni_df['sni_code'].astype(str).str.upper() != "TOTAL"]
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
            sni_df = sni_df[sni_df['sni_code'].astype(str).str.upper() != "TOTAL"]
            total = sni_df['workplaces'].sum()
            if total > 0:
                sni_df['prob'] = sni_df['workplaces'] / total
            else:
                sni_df['prob'] = 1.0 / len(sni_df)
        self._sni_cache[cache_key] = sni_df
        return sni_df

    def random_points_in_polygon(self, polygon, n_points):
        """Punkter i en polygon, ur scenariots egen generator.

        UTAN rng SÅS INTE sample_points AV NÅGOT. Den läser systementropi och
        ignorerar np.random.seed: samma frö gav två olika punktmängder, och
        därmed olika koordinater för arbetsgivare och individer i varje
        körning. Modellen var inte reproducerbar ur sitt frö, och skillnaden
        var mätbar -- två körningar på samma commit och frö gav 1 376 mot
        1 364 arbetslösa år ett. Allt som hänger på avstånd hängde på
        systemklockan: pendling, matchning, vakansernas ålder.

        self.rng är sådd ur scenariots seed och delas med övrig generering,
        så ordningen mellan anropen är en del av strömmen -- som den ska vara.
        """
        import geopandas as gpd
        gdf = gpd.GeoSeries([polygon])
        result = gdf.sample_points(n_points, rng=self.rng)[0]
        if result.geom_type == "Point":
            return [result]
        elif result.geom_type == "MultiPoint":
            return list(result.geoms)
        else:
            raise ValueError(f"Oväntad geometri från sample_points: {result.geom_type}")

    def generate_employers_with_target_jobs(
        self,
        year,
        municipal_code,
        target_jobs,
        employer_dist_cfg,
    ):
        # BRANSCH OCH STORLEK UR DATA (core/bransch.py), inte ur scenariots
        # storleksklasser och en bransch dragen per arbetsställe.
        if "employer_size_distribution" in employer_dist_cfg:
            raise ValueError(
                "employer_distribution.employer_size_distribution används inte "
                "längre: storleken dras givet branschen ur yrkesregistret "
                "(core/bransch.py). Ta bort blocket och ange workplace_max_size, "
                "som stänger storleksklassen 100+.")
        struktur = self._branschstruktur(employer_dist_cfg.get("workplace_max_size"))
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

        rng = self.rng

        # VIKTERNA ANVÄNDS NU. fetch_zones normaliserade redan varje lagers
        # viktfält -- num_workplaces för verksamhets- och handelsområden,
        # population för tätorter -- till kolumnen weight_field, men slingan
        # drog med gdf.sample(1), alltså likformigt: en DeSO med 2 000
        # anställda hade samma sannolikhet som en med fem. Hela
        # layer_configs-blocket i scenariofilen var därmed verkningslöst.
        #
        # LAGRET VÄLJS OCKSÅ VIKTAT, efter lagrets sammanlagda vikt i
        # kommunen. Förut gav rng.choice(all_layers) 25 procent åt vardera av
        # fyra lager, så småorter fick lika stor andel av arbetsgivarna som
        # tätorter. allocation_order ser ut som en prioritetsordning men är en
        # lista att välja ur, och likformigt val gör ordningen betydelselös.
        #
        # Det spelar roll för pendlingen: var arbetsgivarna ligger INOM
        # kommunen avgör avstånden, och medianpendlingen är det enda vi kan
        # pröva mot SCB innan jobbantalen per kommun är rätt.
        lager_namn, lager_p, zon_vikt = _lagervikter(layer_gdfs, municipal_code)

        employers = []
        for sni_code, size in struktur.dra_arbetsstallen(municipal_code, target_jobs, rng):
            layer = lager_namn[rng.choice(len(lager_namn), p=lager_p)]
            gdf = layer_gdfs[layer]
            row = gdf.iloc[rng.choice(len(gdf), p=zon_vikt[layer])]
            pt = self.random_points_in_polygon(row.geometry, 1)[0]
            employers.append({
                'employer_id': f"{municipal_code}_e{len(employers):06d}",
                'municipal_code': municipal_code,
                'layer': layer,
                'zone_code': row.get('zone_code', None),
                'x': pt.x,
                'y': pt.y,
                'geometry': pt,
                'size': size,
                'sni_code': sni_code
            })

        employers_df = gpd.GeoDataFrame(employers, geometry='geometry')
        log(f"Antal arbetsgivare: {len(employers_df)} (mål: {target_jobs} jobb)")
        log(f"Total antal jobb (summa storlek): {employers_df['size'].sum()}")
        return employers_df

    def get_onet_codes_with_freq_for_sni(self, sni_code, db_path="data/worm.sqlite3"):
        """
        Returnerar en lista av tupler: (onet_code, freq) för alla O*NET-yrkeskoder knutna till en given SNI-kod.
        """
        c = self.conn.cursor()
        c.execute(
            "SELECT onet_code, freq FROM sni_onet_link WHERE sni_code = ?",
            (sni_code,)
        )
        result = c.fetchall()  # [(onet_code1, freq1), (onet_code2, freq2), ...]

        return result

    def get_chi_xi_for_onet_code(self, onet_code, db_path="data/worm.sqlite3"):
        """
        Returnerar (chi, xi) för given onet_code.
        """
        c = self.conn.cursor()
        c.execute(
            "SELECT chi, xi FROM onet_occupation_space WHERE onet_code = ?",
            (onet_code,)
        )
        row = c.fetchone()

        if row:
            return row[0], row[1]
        else:
            return None, None  # Hantera ej funnen kod

    def get_geom_for_onet_code(self, onet_code):
        """(x_occ, y_occ, r_o, chi, xi) ur cachen (familje/global-fallback finns i tabellen)."""
        try:
            r = self.onet_space_df.loc[onet_code]
            w = r["w_rel"] if "w_rel" in r.index else np.nan
            rq = r["r_req"] if "r_req" in r.index else np.nan
            return (float(r["x_occ"]), float(r["y_occ"]), float(r["r_o"]),
                    float(r["chi"]), float(r["xi"]), str(r["geom_source"]),
                    float(w) if pd.notna(w) else 1.0,
                    float(rq) if pd.notna(rq) else np.nan)
        except KeyError:
            return None, None, None, None, None, None, None, None

    def load_onet_occupation_space_table(self, db_path="data/worm.sqlite3"):
        import sqlite3
        import pandas as pd
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT * FROM onet_occupation_space", conn)
        conn.close()
        return df.set_index("onet_code")


    # ------------------------------------------------------------------
    # Yrkeskälla: 'sni' (SNI-fördelning x sni_onet_link, default) eller
    # 'register' (tabellen occupation_weights_by_municipality, t.ex. ur
    # SCB:s yrkesregister eller höstprojektets per-kommun-geometri).
    # Kolumnen onet_code betyder "yrkeskod i det system geometritabellen
    # deklarerar" (code_system) -- inte nödvändigtvis O*NET-SOC.
    # ------------------------------------------------------------------
    def occupation_source(self):
        return str(self.cfg_reader.config.get("simulation", {})
                   .get("occupation_source", "sni")).lower()

    def _register_profile(self, municipal_code, year=None):
        """Yrkesprofil ur occupation_weights_by_municipality. Kolumner: onet_code, freq, prob.
        Koder som saknas i geometritabellen släpps med varning.

        INGEN TYST RESERV. Frågan krävde en kolumn year, som tabellen inte har
        sedan den började byggas ur yrkesregistret (60c64f3). Felet sväljdes,
        profilen blev tom, och byggaren föll tillbaka på SNI med en rad i
        loggen. Startens individer och jobb kom därför ur SNI-vägen, medan
        nya jobb under körningen kom ur registret (World._occupation_profile).
        Start och körning hade olika yrkesstruktur: för Mora har de två
        profilerna 26 procent av massan gemensamt. year läses nu bara om
        kolumnen finns, och saknas tabellen eller kommunen kastas ett fel med
        besked om hur underlaget byggs."""
        key = ("register", str(municipal_code), year)
        if not hasattr(self, "_reg_cache"):
            self._reg_cache = {}
        if key in self._reg_cache:
            return self._reg_cache[key]
        bygg = ("Tabellen byggs av scripts/create_database.py ur yrkesregistret "
                "(data/TAB4347_sv.csv, data/TAB4441_sv.csv) och SSYK-O*NET-"
                "crosswalken; hämta filerna med scripts/fetch_data.py. Alternativt "
                "occupation_source: sni i scenariot.")
        finns = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND "
            "name='occupation_weights_by_municipality'").fetchone()
        if finns is None:
            raise ValueError("occupation_source: register kräver tabellen "
                             "occupation_weights_by_municipality, som saknas. " + bygg)
        df = pd.read_sql("SELECT * FROM occupation_weights_by_municipality "
                         "WHERE municipal_code = ?", self.conn,
                         params=(str(municipal_code),))
        if df.empty:
            raise ValueError(f"occupation_weights_by_municipality saknar kommun "
                             f"{municipal_code}. " + bygg)
        if year is not None and "year" in df.columns and df["year"].notna().any():
            yrs = df["year"].dropna().astype(int)
            use = int(yrs[yrs <= int(year)].max()) if (yrs <= int(year)).any() else int(yrs.min())
            df = df[df["year"].astype(int) == use]
        known = set(self.onet_space_df.index)
        unknown = df.loc[~df["onet_code"].isin(known), "onet_code"]
        if len(unknown):
            print(f"[register] {len(unknown)} yrkeskoder saknar geometri och släpps "
                  f"(kommun {municipal_code}), t.ex. {list(unknown[:3])}")
            df = df[df["onet_code"].isin(known)]
        prof = (df.groupby("onet_code")["weight"].sum().rename("freq").reset_index()
                  .sort_values("freq", ascending=False).reset_index(drop=True))
        prof["prob"] = prof["freq"] / prof["freq"].sum() if prof["freq"].sum() > 0 else 0.0
        self._reg_cache[key] = prof
        return prof

    def municipality_occupational_profile(self, municipal_code, year):
        if self.occupation_source() == "register":
            return self._register_profile(municipal_code, year)
        return self._sni_occupational_profile(municipal_code, year)

    def _sni_occupational_profile(self, municipal_code, year):
        """
        Returnerar en DataFrame med alla O*NET-yrken och deras totala frekvens (prob) för en kommun och ett år.
        Kombinerar kommunens SNI-struktur och kopplingen SNI→O*NET.
        Kolumner: onet_code, freq, prob
        """
        # 1. Hämta kommunens SNI-fördelning (med probabilitet)
        sni_dist = self.fetch_sni_distribution(municipal_code, year)
        all_onet = []

        # 2. Gå igenom alla SNI, vikta dess sannolikhet med kopplad O*NET-fördelning
        for _, sni_row in sni_dist.iterrows():
            sni_code = sni_row['sni_code']
            sni_prob = sni_row['prob']
            # Hämtar lista av (onet_code, freq) för SNI
            onet_links = self.get_onet_codes_with_freq_for_sni(sni_code)
            if not onet_links:
                continue  # Ingen SNI→O*NET-länk
            total_freq = sum(freq for _, freq in onet_links)
            for onet_code, freq in onet_links:
                # Multiplicera SNI-fördelningen med O*NET-fördelningen (normaliserad inom SNI)
                freq_norm = freq / total_freq if total_freq > 0 else 1.0 / len(onet_links)
                all_onet.append({
                    "onet_code": onet_code,
                    "sni_code": sni_code,
                    "freq": sni_prob * freq_norm  # Joint sannolikhet
                })

        # 3. Summera över alla SNI (gruppera O*NET)
        onet_df = pd.DataFrame(all_onet)
        profile = (
            onet_df.groupby("onet_code")["freq"].sum()
            .reset_index()
            .sort_values("freq", ascending=False)
            .reset_index(drop=True)
        )

        # 4. Gör om till sannolikhet (prob)
        profile["prob"] = profile["freq"] / profile["freq"].sum()

        return profile  # Kolumner: onet_code, freq, prob

    def generate_jobs_from_employers(self, employers_df):
        """
        Skapar DataFrame med alla jobb.
        Alla har nödvändiga kolumner för utility-matchning: job_id, chi, xi, x, y.
        Lägger även in medianposition i occ-space för varje arbetsgivare.
        """
        jobs = []
        # Räknaren måste vara global över kommuner: metoden anropas en gång per
        # kommun, och en lokal nollställning gav samma job_id i flera kommuner.
        # Dubbletter fick update_after_matching att falla med InvalidIndexError.
        if not hasattr(self, "_job_seq"):
            self._job_seq = 0
        if not hasattr(self, "_profil"):
            from core.bransch import Kommunprofil
            self._profil = Kommunprofil(self.conn)
        profil = self._profil

        # ARBETSGIVAREFFEKTEN. Pi_j = Pi_o * exp(eta_j). Utan den betalar varje
        # arbetsgivare i ett yrke exakt samma lön, och i jobb med r_j ~ 0 är
        # p = q**0 = 1 för ALLA, så hela den kvartilen får identisk lön: 34.8
        # procent av anställningarna där låg på exakt samma punkt. Det är den
        # enda kanal som varierar där exponenten släcker allt annat, och utan
        # den flyttar theta bara atomen från 0.85 till 1.00.
        #
        # AKM-dekompositioner hittar konsekvent en arbetsgivarkomponent kring
        # 10-20 procent av variansen i log lön. Formen har två delar med var
        # sitt empiriskt stöd: en storlekspremie, som finns i data vi redan har
        # (employer_size), och en residual per arbetsgivare. Båda ska
        # kalibreras mot SCB:s lönestrukturstatistik per näringsgren och
        # storleksklass; defaultvärdena är storleksordningar, inte skattningar.
        # eta rör PRISET och inte positionen, så jobben ligger kvar på yrkets
        # centroid och u_R-jämförbarheten består.
        # ScenarioBuilder har cfg_reader.config, inte self.config. Det tidigare
        # 'if hasattr(self, "config") else {}' var alltid falskt, så sim blev
        # tomt, eta_sd blev 0.0 och VARJE arbetsgivare fick eta = 0. Samma
        # klass av tyst nolla som except Exception i _geom_lookup: fallbacken
        # slog till varje gång och ingenting larmade. Beviset låg i data,
        # variationskoefficienten för w_field inom yrke var 0.000 över
        # 78 yrken.
        sim = self.cfg_reader.config.get('simulation', {})
        eta_sd = float(sim.get('employer_wage_sd', 0.0))
        eta_size = float(sim.get('employer_size_premium', 0.0))
        eta_by_employer = {}
        for idx, row in employers_df.iterrows():
            eid = row.get('employer_id', idx)
            e = eta_size * np.log(max(float(row['size']), 1.0) / 10.0)
            if eta_sd > 0:
                e += float(self.rng.normal(0.0, eta_sd))
            eta_by_employer[eid] = e

        # KOMMUNENS PROFIL, EN POOL PER KOMMUN OCH BRANSCH (core/bransch.py).
        # Branschens arbetsställen delar på kommunens yrken ur TAB4436, så att
        # summan är kommunens profil exakt; kärnyrket sätter varje
        # arbetsställes riktning. occupation_source gäller bara invånarna.
        fordelat = {}
        for (kommun, sni), grupp in employers_df.groupby(['municipal_code', 'sni_code'], sort=False):
            for idx, (karna, ssyk_lista) in zip(
                    grupp.index, profil.fordela(kommun, sni, grupp['size'].tolist(), self.rng)):
                fordelat[idx] = (karna, ssyk_lista)

        for idx, row in employers_df.iterrows():
            geom = row['geometry']
            x, y = geom.x, geom.y
            realiserade = {}            # arbetsställets svenska yrken -> O*NET
            karna, ssyk_lista = fordelat[idx]
            for ssyk_code in ssyk_lista:
                sni = row['sni_code']
                onet_code = profil.onet(ssyk_code, self.rng, realiserade)

                x_occ, y_occ, r_o, chi, xi, geom_source, wage, r_req = self.get_geom_for_onet_code(onet_code)
                eta = float(eta_by_employer.get(row.get('employer_id', idx), 0.0))
                wage = wage * np.exp(eta)

                jobs.append({
                    "job_id": f"J{self._job_seq:07d}",
                    "employer_id": row.get('employer_id', idx),
                    "individual_id" : None,
                    "municipal_code": row['municipal_code'],
                    "layer": row['layer'],
                    "zone_code": row['zone_code'],
                    "employer_size": row['size'],
                    "sni_code": sni,
                    "ssyk_code": ssyk_code,
                    "core_ssyk": karna,
                    "onet_code": onet_code,
                    "geometry": geom,
                    "x": x,
                    "y": y,
                    "chi": chi,
                    "xi": xi,
                    "x_occ": x_occ,
                    "y_occ": y_occ,
                    "r_o": r_o,
                    "geom_source": geom_source,
                    "wage": wage,
                    "wage_eta": eta,
                    "r_req": r_req,
                })
                self._job_seq += 1

        df = pd.DataFrame(jobs)
        df["deso_code"] = assign_deso_code(df, self.geoworld.deso_zones, x_col="x", y_col="y")

        # --- Median av occ-space för arbetsgivare ---
        occ_stats = df.groupby('employer_id').agg(
            x_occ=('x_occ', 'mean'),
            y_occ=('y_occ', 'mean'),
        )
        employers_df = employers_df.set_index('employer_id').join(occ_stats, how='left').reset_index()
        employers_df['chi'] = np.hypot(employers_df['x_occ'], employers_df['y_occ'])
        employers_df['xi']  = np.arctan2(employers_df['y_occ'], employers_df['x_occ']) % (2 * np.pi)

        return df, employers_df

    def get_education_props(self, municipal_code, year):
        """Andelen av befolkningen per SUN-nivå 1-7.

        NIVÅERNA HÅLLS ISÄR. Tabellen bär SCB:s sjugradiga skala, och de tre
        klasserna low/medium/high som funktionen tidigare returnerade slog
        ihop 1+2, 3+4 och 5+6+7. Strängarna skrevs sedan i individtabellen,
        och init_competence gjorde int(float("high")) -- ett ValueError som
        fångas och sätter nivån till noll. INGEN individ i startpopulationen
        fick därför sin utbildningscirkel: alla hade bara grundskolan vid
        origo, oavsett vad databasen sa.

        Klassernas cirklar skiljer sig dessutom kraftigt inom varje klump.
        EDU_RADIUS2 går från 0.8 vid nivå 2 till 0.25 vid nivå 6 och massan
        från 0.6 till 3.5, så "high" som en enda nivå hade valt godtyckligt
        bland tre mycket olika cirklar.

        Koden 'US', uppgift saknas, utesluts: den är ingen nivå utan ett
        bortfall, och att fördela den kräver ett antagande som inte hör
        hemma i en läsfunktion.
        """
        df = pd.read_sql("""
            SELECT education_level_code, n_total
            FROM education_level_municipality
            WHERE municipal_code = ? AND year = ?
        """, self.conn, params=(str(municipal_code), year))
        df = df[df["education_level_code"].astype(str).str.fullmatch(r"[1-7]")]
        if df.empty:
            raise ValueError(
                f"education_level_municipality saknar nivåer 1-7 för kommun "
                f"{municipal_code} år {year}")
        n = df.groupby("education_level_code")["n_total"].sum()
        return (n / n.sum()).rename(index=int).sort_index().to_dict()


    # 1. Ladda occupation space EN gång, spara som self.onet_space_df
    def load_onet_occupation_space_table(self, db_path="data/worm.sqlite3"):
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT * FROM onet_occupation_space", conn)
        conn.close()
        return df.set_index("onet_code")

    # 2. Batchfunktion för att hämta chi/xi för en lista av onet_codes
    def get_chi_xi_for_onet_codes(self, onet_codes):
        # Hämtar en DataFrame (kan ha NaN om kod saknas!)
        result = self.onet_space_df.reindex(onet_codes)
        return result["chi"].values, result["xi"].values

    def _price_field(self):
        """Prisfältet Π ur tabellen wage_field_coefficients, eller None."""
        if not hasattr(self, "_pf_cache"):
            try:
                from core.occupations.price_field import PriceField
                self._pf_cache = PriceField.from_db(self.conn)
            except Exception:
                self._pf_cache = None
            if self._pf_cache is None:
                print("\n" + "!" * 72)
                print("VARNING: tabellen wage_field_coefficients saknas i databasen.")
                print("  Reservationslönen sätts till 0 och överskottet blir S = p*w - c*km.")
                print("  Kör: python scripts/load_task_geometry.py --write")
                print("  med wage_field_coefficients.csv i data/geometry/.")
                print("!" * 72 + "\n")
        return self._pf_cache

    def get_geom_for_onet_codes(self, onet_codes):
        """x_occ, y_occ, r_o (+ chi, xi) för en lista koder; NaN om kod saknas."""
        cols = ["x_occ", "y_occ", "r_o", "chi", "xi", "geom_source", "w_rel", "pi_rel"]
        if "n_tasks" in self.onet_space_df.columns:
            cols.append("n_tasks")
        return self.onet_space_df.reindex(onet_codes)[cols]

    # ------------------------------------------------------------------
    # Ålder (docs/individmodell.md, avsnitt 11)
    # ------------------------------------------------------------------
    def age_config(self):
        """Åldersparametrarna ur simulation.age, med defaults."""
        cfg = self.cfg_reader.config.get("simulation", {}).get("age", {}) or {}
        # Inträdesålder per SUN-nivå. Pensionsmyndigheten redovisar 21,9 år
        # som genomsnittlig inträdesålder i arbetskraften 2025, vilket dessa
        # tal väger ihop till för en rimlig nivåfördelning.
        entry = {1: 17.0, 2: 17.0, 3: 19.0, 4: 20.0, 5: 22.0, 6: 25.0, 7: 30.0}
        entry.update({int(k): float(v)
                      for k, v in (cfg.get("entry_age") or {}).items()})
        return {"retirement_age": float(cfg.get("retirement_age", 67)),
                "retirement_spread": float(cfg.get("retirement_spread", 0.8)),
                "max_alder": int(cfg.get("max_alder", 74)),
                "work_age_min": float(cfg.get("work_age_min", 16)),
                "entry_age": entry}

    def alderspyramid(self, municipal_code, year):
        """Folkmängd per ettårsklass för kommunen, som (åldrar, antal).

        Faller tillbaka på det senaste året som inte ligger efter det önskade,
        och säger ifrån när den gör det. Saknas tabellen eller kommunen kastas
        ett fel: en påhittad pyramid hade bestämt både hur många som står nära
        pensionsåldern och hur långa arbetsliv individerna har bakom sig.
        """
        kod = kommunkod(pd.Series([municipal_code])).iloc[0]
        try:
            df = pd.read_sql(
                "SELECT year, age, n_total FROM population_by_age "
                "WHERE municipal_code = ?", self.conn, params=(kod,))
        except Exception as e:
            raise ValueError(
                "tabellen population_by_age saknas i databasen. Hämta SCB:s "
                "folkmängd per ettårsklass (BE0101) med scripts/fetch_data.py "
                "och kör scripts/create_database.py.") from e
        if df.empty:
            raise ValueError(f"population_by_age saknar kommun {kod}")
        ar = sorted(df["year"].unique())
        valt = max([a for a in ar if a <= year], default=ar[0])
        if valt != year:
            print(f"[ålder] kommun {kod}: befolkning per ålder finns inte för "
                  f"{year}, använder {valt}")
        d = df[df["year"] == valt].sort_values("age")
        return d["age"].to_numpy(float), d["n_total"].to_numpy(float)

    @staticmethod
    def _skala_pyramid(antal, population):
        """Pyramiden skalad till populationen med största resten, så att
        summan blir exakt och ingen ettårsklass tappas till noll av avrundning
        nedåt."""
        andel = antal / antal.sum() * float(population)
        bas = np.floor(andel).astype(int)
        rest = int(population) - int(bas.sum())
        if rest > 0:
            ordning = np.argsort(-(andel - bas))
            bas[ordning[:rest]] += 1
        elif rest < 0:
            ordning = np.argsort(andel - bas)
            bas[ordning[:-rest]] -= 1
        return np.maximum(bas, 0)

    def deltagandeprofil(self, municipal_code, year):
        """Deltagandet per ettårsklass. Cachad per kommun.

        Profilerna sparas i self.profiler och följer med till World, så att
        utträdet vid årsskiftet kan räknas ur samma kurva som fördelningen vid
        uppstart utan att läsa databasen mitt i körningen. Två kurvor för
        samma sak hade kunnat glida isär.

        Underlaget är SCB:s BAS-statistik per åldersklass, som laddas till
        labour_force_by_age. Saknas den kastar dragningen: en platt fördelning
        är inte ett sämre alternativ utan ett annat, och den ska inte smyga
        sig in tyst när tabellen inte finns.
        """
        kod = kommunkod(pd.Series([municipal_code])).iloc[0]
        if not hasattr(self, "profiler"):
            self.profiler = {}
        if kod in self.profiler:
            return self.profiler[kod]
        try:
            rader = pd.read_sql(
                "SELECT age_group, in_labour_force, total FROM labour_force_by_age "
                "WHERE municipal_code = ? AND year = ?", self.conn,
                params=(kod, year))
        except Exception as e:
            raise ValueError(
                "tabellen labour_force_by_age saknas i databasen. Hämta SCB:s "
                "arbetsmarknadsstatus per åldersklass med "
                "scripts/fetch_data.py --only Arbetskraft och kör "
                "scripts/create_database.py.") from e
        if rader.empty:
            ar = pd.read_sql("SELECT DISTINCT year FROM labour_force_by_age "
                             "WHERE municipal_code = ?", self.conn, params=(kod,))
            if ar.empty:
                raise ValueError(f"labour_force_by_age saknar kommun {kod}")
            valt = max([int(v) for v in ar["year"] if int(v) <= year],
                       default=int(ar["year"].min()))
            print(f"[ålder] kommun {kod}: arbetskraft per ålder finns inte för "
                  f"{year}, använder {valt}")
            rader = pd.read_sql(
                "SELECT age_group, in_labour_force, total FROM labour_force_by_age "
                "WHERE municipal_code = ? AND year = ?", self.conn,
                params=(kod, valt))

        aldrar, antal = self.alderspyramid(municipal_code, year)
        bef = pd.Series(antal, index=aldrar.astype(int))
        ac = self.age_config()
        q = profil(rader, bef, retirement_age=ac["retirement_age"],
                   retirement_spread=ac["retirement_spread"],
                   max_alder=ac["max_alder"])
        self.profiler[kod] = q
        return q

    def dra_aldrar(self, municipal_code, year, population, n_workforce, rng):
        """Åldrar för hela befolkningen, uppdelade på arbetskraft och övriga.

        Hela befolkningen får SCB:s pyramid. Arbetskraften placeras INOM den,
        utan återläggning: den tar platser i pyramiden i stället för att dras
        vid sidan av den, så att summan av de två grupperna är pyramiden
        själv. Resten -- barn, pensionärer och de i arbetsför ålder som
        arbetskraften inte fyller -- blir utanför arbetskraften.

        VILKA PLATSER DEN TAR styrs av deltagandeprofilen. Dragningen viktas
        med q(a), sannolikheten att en person i den åldern är i arbetskraften.
        Tidigare var vikten platt över [16, 67), vilket gav sextonåringar samma
        deltagande som fyrtioåringar och la omkring 800 personer i Ovansiljan i
        årskullar som knappt deltar. Eftersom antalet är fixt trängde de undan
        lika många från de åldrar som faktiskt bär arbetskraften, och
        kohorterna närmast riktåldern kom att ligga fulltaligt i arbetskraften
        -- vilket är en del av förklaringen till att körningen efter 0160 gav
        2,3 procent avgångar per år mot rimliga 1,5.
        """
        aldrar, antal = self.alderspyramid(municipal_code, year)
        counts = self._skala_pyramid(antal, population)
        urna = np.repeat(aldrar, counts)
        q = self.deltagandeprofil(municipal_code, year)

        vikt = pd.Series(q).reindex(urna.astype(int)).fillna(0.0).to_numpy(float)
        mojliga = np.flatnonzero(vikt > 0)

        # PROFILEN IMPLICERAR EN ARBETSKRAFT, och scenariots kommer från en
        # annan källa: labour_market_status, avgränsad 20-65. Stämmer de inte
        # blir dragningen skev åt ett håll profilen inte beskriver. Ligger
        # scenariots tal nära antalet MÖJLIGA blir urvalet dessutom nästan
        # uttömmande, och då kan vikterna inte slå igenom -- fördelningen blir
        # plattare än profilen oavsett vad profilen säger.
        implicerad = float(vikt.sum())
        if implicerad > 0 and not 0.75 <= n_workforce / implicerad <= 1.33:
            print(f"[ålder] kommun {municipal_code}: scenariots arbetskraft "
                  f"{n_workforce} mot profilens {implicerad:.0f} "
                  f"({n_workforce / implicerad:.2f}x) -- åldersfördelningen "
                  f"blir skev")
        if n_workforce > len(mojliga):
            raise ValueError(
                f"kommun {municipal_code}: arbetskraften {n_workforce} är "
                f"större än befolkningen {len(mojliga)} i de åldrar där "
                f"deltagandet är positivt ({q.index.min()}-{q.index.max()} år).")
        # Utan återläggning med vikter: Efraimidis-Spirakis nyckel
        # u^(1/w) rangordnar med sannolikhet proportionell mot w, vilket
        # rng.choice med replace=False inte gör korrekt för vikter.
        u = rng.random(len(mojliga))
        nyckel = np.log(np.clip(u, 1e-300, None)) / vikt[mojliga]
        valda = mojliga[np.argsort(-nyckel)[:int(n_workforce)]]
        i_arbetskraft = np.zeros(len(urna), dtype=bool)
        i_arbetskraft[valda] = True
        return urna[i_arbetskraft], urna[~i_arbetskraft]

    def dra_tenure(self, alder, utbildningsniva, rng):
        """Inträdesålder, arbetslivets längd och tenure i nuvarande yrke."""
        entry = self.age_config()["entry_age"]
        entry_default = float(entry.get(3, 19.0))
        entry_ar = np.array([float(entry.get(int(e), entry_default))
                             if e is not None and str(e).isdigit()
                             else entry_default for e in utbildningsniva],
                            dtype=float)
        arbetsliv = np.maximum(0.0, np.asarray(alder, dtype=float) - entry_ar)
        ten_mean = float(self.cfg_reader.config.get("simulation", {})
                         .get("competence", {}).get("initial_tenure_mean_years", 8.0))
        tenure = np.minimum(rng.exponential(ten_mean, size=len(entry_ar)), arbetsliv)
        return entry_ar, arbetsliv, tenure

    def generate_individuals(self, municipal_code, population, workforce_ratio, unemployment_rate, year=2024):
        """
        Skapar individer med verklig utbildningsnivå-fördelning från SCB.
        Arbetskraften fördelas enligt chi-utbildningsnivå, övriga (not_in_labor_force) får låg chi.
        """
        rng = self.rng

        n_workforce = int(round(population * workforce_ratio))
        n_not_in_labor_force = population - n_workforce

        # 1. Utbildningsnivå per individ, på SCB:s sjugradiga skala.
        edu_props = self.get_education_props(municipal_code, year)
        nivaer = sorted(edu_props)
        antal = self._skala_pyramid(
            np.array([edu_props[k] for k in nivaer], dtype=float), n_workforce)
        education_levels = [n for k, a in zip(nivaer, antal) for n in [k] * int(a)]
        rng.shuffle(education_levels)

        # 3. Slumpa status för hela befolkningen
        status_list = ["unemployed"] * n_workforce + ["not_in_labor_force"] * n_not_in_labor_force
        rng.shuffle(status_list)

        # 3b. Ålder ur kommunens pyramid, betingad på status. Arbetskraften
        # ligger inom [work_age_min, retirement_age); resten av pyramiden
        # hamnar utanför arbetskraften.
        alder_arbetskraft, alder_ovriga = self.dra_aldrar(
            municipal_code, year, population, n_workforce, rng)
        alder_arbetskraft = list(alder_arbetskraft)
        alder_ovriga = list(alder_ovriga)

        # 4. Fördela individer över DeSO
        deso_gdf = self.geoworld.deso_zones
        deso_gdf = deso_gdf[(deso_gdf["municipal_code"] == str(municipal_code)) & (deso_gdf["population"] > 0)].reset_index(drop=True)
        if len(deso_gdf) == 0:
            raise ValueError(f"Inga DeSO-zoner med befolkning > 0 hittades för kommun {municipal_code}")

        pop_weights = deso_gdf["population"].values
        pop_probs = pop_weights / pop_weights.sum()
        N = population
        n_per_deso = rng.multinomial(N, pop_probs)

        records = []
        i = 0
        edu_idx = 0
        wf_idx = 0
        nilf_idx = 0
        for deso_idx, n_ind in enumerate(n_per_deso):
            if n_ind == 0:
                continue
            deso_row = deso_gdf.iloc[deso_idx]
            points = self.random_points_in_polygon(deso_row.geometry, n_ind)
            for pt in points:
                status = status_list[i]
                # Endast arbetskraften får utbildningsnivå, övriga sätts till None
                education_level = education_levels[edu_idx] if status == "unemployed" else None
                if status == "unemployed":
                    age = alder_arbetskraft[wf_idx]
                    wf_idx += 1
                else:
                    age = alder_ovriga[nilf_idx]
                    nilf_idx += 1
                records.append({
                    'municipal_code': municipal_code,
                    'status': status,
                    'job_id': None,
                    'deso_code': deso_row['deso_code'],
                    'x': pt.x,
                    'y': pt.y,
                    'geometry': pt,
                    'education_level': education_level,
                    'age': float(age),
                })
                if status == "unemployed":
                    edu_idx += 1
                i += 1

        df = pd.DataFrame(records)
        df["individual_id"] = [f"{municipal_code}_i{ix:06d}" for ix in range(len(df))]
        rng = self.rng

        indiv_defaults = self.cfg_reader.config.get('defaults', {}).get('individuals', {})
        prop_cfg = indiv_defaults.get('propensities', {})

        # 5. Propensiteter
        for name in ['start_education', 'internal_training', 'quit_job', 'career_break', 'internal_job_change']:
            pblock = prop_cfg.get(name, {})
            mean = pblock.get('mean', 0.1)
            std = pblock.get('std', 0.05)
            col = f'propensity_{name}'
            df[col] = np.clip(
                rng.normal(mean, std, size=len(df)), 0, 1
            )

        # ---- Sampla (x_occ, y_occ) för ALLA individer ur yrkesgeometrin ----
        profile = self.municipality_occupational_profile(municipal_code, year)
        geom = self.get_geom_for_onet_codes(profile["onet_code"].values)
        x_vals = geom["x_occ"].values
        y_vals = geom["y_occ"].values
        weights = profile["prob"].values

        valid = ~np.isnan(x_vals) & ~np.isnan(y_vals)
        x_vals, y_vals, weights = x_vals[valid], y_vals[valid], weights[valid]

        # Dra yrke per individ och BEHÅLL det: kompetenscirklarna byggs på det.
        # Personlig avvikelse från yrkets centroid är r_o/sqrt(k), där k är
        # antalet uppgifter i yrket (individen utför en delmängd av dem). Det
        # ersätter den hårdkodade jittern 0.05 med en härledning som skalar med
        # yrket. Se docs/individmodell.md, avsnitt 2.
        # KONCENTRATIONSEXPONENTEN. Individernas yrken dras ur profilens
        # sannolikheter UPPHÖJDA till power och omnormaliserade: vanliga yrken
        # blir vanligare, sällsynta sällsyntare. Jobben dras ur samma profil
        # UTAN exponent (se generate_employers_with_target_jobs, som använder
        # sni_dist['prob'] rakt av). Arbetare och jobb får därmed olika
        # koncentration i uppgiftsrummet by construction, vilket är en
        # felmatchningskälla oberoende av allt annat.
        #
        # Värdet 1.5 stod hårdkodat utan härledning. Det ligger nu i
        # scenariofilen så att det går att svepa: 1.0 betyder att individer
        # och jobb dras ur samma fördelning.
        #
        # Mät effekten med arbetslöshet per kommun mot SCB:s
        # arbetsmarknadsstatus. För Ovansiljan ger modellen 8.3 / 11.3 / 18.9
        # procent mot verklighetens 2.35 / 3.51 / 3.17 (2023), alltså tre till
        # sex gånger för högt och med Orsa och Älvdalen i omvänd ordning.
        power = float(self.cfg_reader.config.get("simulation", {})
                      .get("occupation_concentration", 1.5))
        w = weights ** power; w = w / w.sum()
        codes_arr = profile["onet_code"].values[valid]
        ro_arr = geom["r_o"].values[valid]
        ntask_arr = (geom["n_tasks"].values[valid] if "n_tasks" in geom.columns
                     else np.full(valid.sum(), np.nan))
        k_default = float(self.cfg_reader.config.get("simulation", {})
                          .get("competence", {}).get("tasks_per_occupation_default", 20))
        pick = rng.choice(len(x_vals), size=len(df), p=w)
        n_tasks = np.where(np.isnan(ntask_arr[pick]), k_default, ntask_arr[pick])
        jit = np.nan_to_num(ro_arr[pick], nan=0.27) / np.sqrt(np.maximum(n_tasks, 1.0))
        x_occ = x_vals[pick] + rng.normal(0.0, jit)
        y_occ = y_vals[pick] + rng.normal(0.0, jit)
        rad = np.hypot(x_occ, y_occ); over = rad > 1.0
        x_occ[over] /= rad[over]; y_occ[over] /= rad[over]
        df["onet_code"] = codes_arr[pick]
        df["last_onet_code"] = codes_arr[pick]      # för u_R mätt som CPS: yrke till yrke
        df["r_o_home"] = np.nan_to_num(ro_arr[pick], nan=0.27)
        df["x_occ"] = x_occ
        df["y_occ"] = y_occ
        df["chi"] = np.hypot(x_occ, y_occ)                # för visualisering/kompatibilitet
        df["xi"]  = np.arctan2(y_occ, x_occ) % (2 * np.pi)

        # TENURE KAN INTE ÖVERSTIGA ARBETSLIVETS LÄNGD. Dragningen var
        # exponentiell med medel åtta år och oberoende av allt annat, vilket
        # gav tjugofemåringar med trettio års yrkeserfarenhet. Massan i
        # kompetenscirkeln är m_mattnad*(1 - e^{-lambda*tenure}), så felet gick
        # rakt in i konkurrenskraften: de yngsta startade mättade.
        #
        # Arbetslivets längd är L = ålder - inträdesålder, där inträdesåldern
        # följer utbildningsnivån (19/20/24 år). Dragningen trunkeras vid L.
        #
        # Vad detta INTE gör: massan följer fortfarande tenure i NUVARANDE
        # yrke, inte hela arbetslivet. Den som bytt yrke har byggt massa i det
        # tidigare, och de cirklarna finns inte i startpopulationen. Tills de
        # införs underskattas massan för dem med långt arbetsliv och många
        # byten.
        entry_ar, arbetsliv, tenure = self.dra_tenure(
            df["age"].to_numpy(float), df["education_level"].tolist(), rng)
        df["entry_age"] = entry_ar
        df["work_life_years"] = arbetsliv
        df["tenure_years"] = tenure

        # ---- Reservationslön: rho * Π(egen position), i löneandelar ----
        # Π saknas (ingen koefficienttabell) -> w_res = 0, dvs. S = p*w - c*km.
        rho = self.cfg_reader.config.get("simulation", {}).get("rho_reservation", 0.7)
        pf = self._price_field()
        if pf is not None:
            # PI SPARAS PER INDIVID. Yrkets pris behövs vid körning på två
            # ställen: som absolut golv för reservationslönen (avtalens
            # lägstalöner ligger inte på en andel av DEN EGNA tidigare lönen
            # utan på en andel av yrkets nivå) och för att låta den som tjänar
            # under Pi söka oftare. Utan kolumnen skulle båda kräva ett
            # fältuppslag per individ och sökning.
            df["pi_o"] = pf.pi_rel_cart(x_occ, y_occ)
            df["w_res"] = rho * df["pi_o"]
        else:
            df["pi_o"] = np.nan
            df["w_res"] = 0.0
        # Senaste lön och arbetslöshetens början. Den som aldrig haft en
        # anställning har ingen senaste lön, och för henne är rho * Pi rätt
        # utgångspunkt -- det är vad w_res redan är.
        # UPPSTARTENS ARBETSLÖSA MÅSTE HA EN KLOCKA. Utan unemployed_since och
        # w_last returnerar _uppdatera_reservation tidigt, och deras anspråk
        # står kvar på rho * Pi för evigt. I en körning var 2 553 av 3 233
        # arbetslösa sådana -- fyra femtedelar -- och eftersom Pi är deras EGET
        # yrkes pris avvisade de varje lågavlönad position vars Pi låg lägre.
        # Stocken blev den ursprungliga kohorten, frusen: arbetslösa 3 326 år
        # ett och 3 252 år tio.
        #
        # De har ingen tidigare anställning, så w_last sätts till deras
        # ingående anspråk. Det är inte en lön de haft utan den nivå de utgår
        # från, vilket är vad w_last betyder i mekaniken.
        df["w_last"] = np.where(df["status"].to_numpy() == "unemployed",
                                df["w_res"].to_numpy(), np.nan)
        df["unemployed_since"] = np.where(df["status"].to_numpy() == "unemployed",
                                          0.0, np.nan)
        # Relevansmängdens lönefördelning, skattad när arbetslösheten börjar.
        df["w_rel_med"] = np.nan
        df["w_rel_sd"] = np.nan
        df["p_claim0"] = np.nan
        df["w_res_time"] = np.nan
        df["last_education_draw"] = np.nan

        # r_i är härledd ur kompetenscirklarna (World.init_competence). Tills
        # cirklarna byggts: 0, dvs. samma som en färsk arbetare med en cirkel.
        df['r_i'] = 0.0

        # 9. Z (kompetensbredd/specialisering) – valfritt, kan läggas in här
        # df['Z'] = ... (exempelvis beroende av chi)

        return df

    def faktisk_arbetsloshet(self, municipalities):
        """SCB:s arbetslöshet per kommun ur labour_market_status.

        Scenariofilens unemployment_rate är en platshållare, och sedan 0137
        back-räknas arbetskraften ur den: L = syss / (1 - u). Talet sätter
        därmed golvet för modellens arbetslöshet direkt, eftersom
        u = u_min + V/L med u_min = 1 - J/L. Med platshållarna 6.5, 7.5 och
        7.0 procent för Ovansiljan blev u_min 6.8 procent; med SCB:s faktiska
        2.35, 3.51 och 3.17 blir det 2.75. Skillnaden är inte en modellfråga
        utan ett indatafel.

        ÅLDERSINTERVALLEN SKILJER SIG: SCB:s uttag är 20-65 år, modellen räknar
        15-74. Nivån är därför inte exakt överförbar, men den är mycket
        närmare sanningen än en platshållare satt på fri hand, och
        rangordningen mellan kommunerna är SCB:s.

        Returnerar dict kommun -> andel, eller None om tabellen saknas eller
        inte täcker alla kommunerna. Delvis täckning duger inte: då skulle
        några kommuner ha uppmätt arbetslöshet och andra en gissning, och
        jämförelsen mellan dem mäta skillnaden mellan källorna.
        """
        koder = [str(k).zfill(4) for k in municipalities]
        try:
            df = pd.read_sql("SELECT municipal_code, u_rate "
                             "FROM labour_market_status", self.conn)
        except Exception as e:
            log(f"[arbetslöshet] labour_market_status saknas ({e}) -- "
                f"scenariofilens tal används.")
            return None
        if df.empty:
            return None
        df["municipal_code"] = (df["municipal_code"].astype(str).str.strip()
                                .str.zfill(4))
        d = df.set_index("municipal_code")["u_rate"].to_dict()
        saknas = [k for k in koder if k not in d or not np.isfinite(d.get(k, np.nan))]
        if saknas:
            log(f"[arbetslöshet] saknas för {saknas} -- scenariofilens tal "
                f"används för alla.")
            return None
        return {k: float(d[k]) / 100.0 for k in koder}

    def jobbandelar(self, municipalities, year):
        """Hur scenariots jobb ska FÖRDELAS mellan kommunerna.

        Tidigare fick varje kommun target_jobs = workforce - n_unemployed,
        alltså exakt lika många jobb som den har sysselsatta invånare.
        Nettopendlingen blev därmed noll i varje kommun per konstruktion och
        det enda som kunde uppstå var symmetriska bruttoflöden. I SCB:s tal
        för Ovansiljan har Mora 1.11 jobb per sysselsatt invånare, Orsa 0.74
        och Älvdalen 0.83; modellen gav 1.00 åt alla tre. Ingen justering av
        commute_cost_per_km kan ändra det -- parametern skalar bruttoflödena
        men kan inte skapa ett netto.

        Källan är kolumnsumman i SCB:s pendlingsmatris (tabellen commuting). Den senare såg ut att duga -- den räknar
        efter arbetsställe -- men är ett urval: den ger Mora 4 250 sysselsatta
        på 164 arbetsställen när kommunen har omkring 10 000 jobb, och
        summorna är jämna femtiotal. Andelarna blev 81/12/7 mot de riktiga
        66/15/19, alltså Älvdalen halverat. Att fetch_sni_distribution läser
        kolumnen workplaces och inte employed ur samma tabell var tecknet på
        att employed inte bär det den ser ut att bära.

        Kolumnsumman i pendlingsmatrisen är jobben i kommunen, och kvoten
        mellan kommunerna är den fördelning jobben ska ha.

        SUMMAN BEVARAS. Scenariot är ett slutet system: en Morabo som i
        verkligheten arbetar i Falun kan i modellen inte pendla ut, eftersom
        Falun inte finns. Skulle totalen tas rakt ur arbetsställestatistiken
        skulle Ovansiljan få fler jobb än sysselsatta invånare och skillnaden
        dyka upp som vakanser ingen kan fylla. Det är fördelningen som hämtas
        ur data, inte nivån.

        Returnerar dict kommun -> andel, eller None om underlaget saknas för
        någon kommun. Då faller anroparen tillbaka på den gamla fördelningen,
        som är fel men känd.
        """
        koder = [str(k) for k in municipalities]
        # KÄLLAN ÄR PENDLINGSMATRISENS KOLUMNSUMMA. Det är det enda underlag i
        # databasen som otvetydigt räknar jobb efter ARBETSSTÄLLE.
        #
        # Två andra källor prövades och dög inte. employment_municipality_sni
        # ger Mora 4 250 sysselsatta på 164 arbetsställen när kommunen har
        # omkring 10 000 jobb -- ett urval, inte full statistik.
        # employment_deso_sni är nattbefolkning: DeSO är en bostadsindelning,
        # och totalraderna summerar till 10 163 / 3 399 / 3 450 för Mora, Orsa
        # och Älvdalen, vilket är kommunernas BOENDE sysselsatta (10 116 /
        # 3 348 / 3 245) och inte deras jobb. Med den källan hade fördelningen
        # blivit densamma som den gamla, fast uppmätt i stället för antagen.
        #
        # PRÖVNINGEN SOM SKILJER DAG FRÅN NATT ÄR ORSA: 2 235 jobb mot 3 348
        # boende sysselsatta. Mora skiljer bara någon procent och duger inte
        # som kontroll.
        #
        # Delmatrisen och inte hela kolumnen: de jobb i Mora som innehas av
        # Rättviks- eller Leksandsbor kan ingen i scenariot ta, eftersom de
        # pendlarna inte finns i modellen. Det är också exakt den definition
        # scripts/diagnose_commuting.py mäter mot, så källa och utvärdering
        # använder samma tal.
        try:
            df = pd.read_sql("SELECT * FROM commuting", self.conn)
        except Exception as e:
            log(f"[jobbandelar] tabellen commuting saknas ({e}) -- faller "
                f"tillbaka på kommunernas egen arbetskraft.")
            return None
        if df.empty:
            return None
        for kol in ("home_municipality", "work_municipality"):
            df[kol] = df[kol].astype(str).str.strip().str.zfill(4)
        if "year" in df.columns and df["year"].notna().any():
            df = df[df["year"] == df["year"].max()]
        inom = df[df["home_municipality"].isin(koder)
                  & df["work_municipality"].isin(koder)]
        if inom.empty:
            log("[jobbandelar] commuting täcker inte scenariots kommuner -- "
                "faller tillbaka på kommunernas egen arbetskraft.")
            return None
        dag, natt = {}, {}
        for kod in koder:
            j = float(inom[inom["work_municipality"] == kod]["employed"].sum())
            b = float(inom[inom["home_municipality"] == kod]["employed"].sum())
            if j <= 0 or b <= 0:
                log(f"[jobbandelar] {kod}: saknas i pendlingsmatrisen -- "
                    f"faller tillbaka på kommunernas egen arbetskraft.")
                return None
            dag[kod], natt[kod] = j, b
        # BÅDA MARGINALERNA UR SAMMA DELMATRIS. Kolumnsumman är jobben i
        # kommunen, radsumman dess boende sysselsatta, och de summerar till
        # samma tal -- delmatrisen ÄR en sluten arbetsmarknad. Hämtas bara
        # täljaren ur SCB och nämnaren ur scenariofilens workforce_ratio mäter
        # dag/natt skillnaden mellan två källor lika mycket som modellens
        # beteende: med platshållarna för Ovansiljan fick Mora 63.3 procent av
        # invånarna mot SCB:s 59.6 och Älvdalen 18.1 mot 20.4, vilket ensamt
        # förklarade att kvoterna blev 1.04 och 1.07 i stället för 1.10 och
        # 0.95.
        return {"jobb": dag, "boende": natt}

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

        # BÅDA SIDOR UR PENDLINGSMATRISEN. Jobben per kommun ur kolumnsumman,
        # de boende sysselsatta ur radsumman. De summerar till samma tal, så
        # scenariot förblir slutet: lika många jobb som sysselsatta invånare
        # totalt, men fördelade olika mellan kommunerna. Se jobbandelar().
        #
        # workforce_ratio i scenariofilen slutar därmed styra HUR MÅNGA
        # sysselsatta varje kommun har och blir bara det den bör vara: en
        # uppgift om befolkningen. Andelen härleds, och den härledda skrivs ut
        # tillsammans med den angivna så att skillnaden syns.
        # SCB:s arbetslöshet per kommun, om den finns laddad. Se
        # faktisk_arbetsloshet: talet sätter golvet för modellens arbetslöshet
        # via arbetskraftens storlek, och scenariofilens platshållare låg
        # ungefär dubbelt så högt som verkligheten.
        if str(self.cfg_reader.config.get("simulation", {})
               .get("unemployment_source", "register")).lower() == "register":
            faktisk_u = self.faktisk_arbetsloshet(municipalities)
        else:
            faktisk_u = None

        marginaler = None
        if len(municipalities) > 1:
            marginaler = self.jobbandelar(municipalities, year)
        if marginaler:
            jobb_per_kommun = marginaler["jobb"]
            boende_per_kommun = marginaler["boende"]
            total_jobs = int(round(sum(jobb_per_kommun.values())))
            log("[jobbandelar] jobb " + ", ".join(
                f"{k}: {100 * v / total_jobs:.1f} %"
                for k, v in jobb_per_kommun.items()) + f" av {total_jobs}")
            log("[jobbandelar] boende " + ", ".join(
                f"{k}: {100 * v / sum(boende_per_kommun.values()):.1f} %"
                for k, v in boende_per_kommun.items()))
        else:
            jobb_per_kommun = boende_per_kommun = None
            total_jobs = 0

        for municipal_code in municipalities:
            t1 = time.time()
            log(f"\n--- Kommun {municipal_code} ---")
            population = self.cfg_reader.get_population(municipal_code)[0]
            workforce_ratio = self.cfg_reader.get_workforce_ratio(municipal_code)[0]
            local_unemployment_rate = self.cfg_reader.get_unemployment_rate(municipal_code, year)[0]

            if faktisk_u:
                kod = str(municipal_code).zfill(4)
                log(f"  arbetslöshet: {100*faktisk_u[kod]:.2f} % ur SCB, mot "
                    f"{100*local_unemployment_rate:.2f} % i scenariofilen")
                local_unemployment_rate = faktisk_u[kod]

            if boende_per_kommun:
                # Arbetskraften back-räknas ur SCB:s sysselsatta och
                # scenariots arbetslöshetstal: syss = arbetskraft * (1 - u).
                syss = boende_per_kommun[str(municipal_code)]
                arbetskraft = syss / max(1.0 - local_unemployment_rate, 1e-9)
                harledd = arbetskraft / max(population, 1)
                log(f"  arbetskraftsandel: {harledd:.3f} härledd ur SCB "
                    f"({syss:.0f} sysselsatta), mot {workforce_ratio:.3f} "
                    f"i scenariofilen")
                workforce_ratio = harledd

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
            if jobb_per_kommun:
                # Nycklarna är strängar; kommunkoderna i scenariofilen är
                # heltal. Uppslaget med rå kod gav KeyError vid första
                # kommunen.
                target_jobs = int(round(jobb_per_kommun[str(municipal_code)]))
                log(f"  jobb: {target_jobs} mot {workforce - n_unemployed} "
                    f"sysselsatta invånare -- dag/natt "
                    f"{target_jobs / max(workforce - n_unemployed, 1):.2f}")
            else:
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
            jobs, employers = self.generate_jobs_from_employers(employers)
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
