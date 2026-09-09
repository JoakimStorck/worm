# core/world.py

import sys
import os
import numpy as np
import pandas as pd
import traceback
import time

from core.geography.geoworld import GeoWorld
from core.log import log
from core.events import EventQueue
from core.log import EventLogger
from core.occupations.utils import xi_add, chi_add, r_add

DAYS_PER_YEAR = 365.25
MONTH_LENGTHS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def is_leap_year(year):
    return (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))

class World:
    def __init__(self, db_path, cfg_reader, outdir, geoworld=None, scope=None,
                 individuals=None, jobs=None, employers=None, events=None):
        self.db_path = db_path
        self.cfg_reader = cfg_reader
        self.outdir = outdir
        self.scope = scope
        self.geoworld = geoworld if geoworld is not None else GeoWorld(db_path)
        self.individuals = individuals if individuals is not None else pd.DataFrame()
        self.jobs = jobs if jobs is not None else pd.DataFrame()
        self.employers = employers if employers is not None else pd.DataFrame()
        self.events = events if events is not None else pd.DataFrame(columns=["time", "agent_id", "event_type", "params"])
        self.current_time = 0

        self.event_queue = EventQueue()
        self.event_logger = EventLogger(filepath=os.path.join(outdir, "eventlog.csv"))
        self._matchings = pd.DataFrame()
        self.n_matched_in_month = 0
        self.simulation_end_time = self._get_simulation_end_time()

    @property
    def conn(self):
        """Lat sqlite-anslutning. Saknades helt sedan jobbflödena infördes:
        _geom_lookup och _draw_occupation_for_employer föll tyst i try/except
        och u_R_occ kunde aldrig beräknas."""
        if getattr(self, "_conn", None) is None and getattr(self, "db_path", None):
            import sqlite3
            self._conn = sqlite3.connect(self.db_path)
        return getattr(self, "_conn", None)

    @conn.setter
    def conn(self, value):
        self._conn = value

    def _get_simulation_end_time(self):
        config = self.cfg_reader.config
        n_years = config.get('n_years') or config.get('simulation', {}).get('n_years', 1)
        return DAYS_PER_YEAR * n_years

    def simulate(self):
        from core.event_handlers import RULE_SWITCH
        self.wallclock_start = time.time()
        self._init_events()
        while not self.event_queue.is_empty():
            event = self.event_queue.pop()
            if event["time"] > self.simulation_end_time:
                break
            handler = RULE_SWITCH[event["event_type"]]
            handler(event, self)

        event = {
            "time": self.simulation_end_time,
            "agent_id": None,
            "event_type": "simulation_completed",
            "params": {}
        }
        self.event_logger.log_event(self, event, print_line=True)

        self.close()

    def tick(self):
        self._apply_decision_rules()
        self._process_due_events()

    def _apply_decision_rules(self):
        unemployed = self.individuals[self.individuals['status'] == 'unemployed']
        if 'next_job_search_time' in self.individuals.columns:
            ready = unemployed[unemployed['next_job_search_time'] <= self.current_time]
        else:
            ready = unemployed

        for idx in ready.index:
            event = {
                "time": self.current_time,
                "agent_id": idx,
                "event_type": "start_job_search",
                "params": {}
            }
            self._push_event(event)

    def _process_due_events(self):
        from core.event_handlers import RULE_SWITCH
        while not self.event_queue.is_empty() and self.event_queue.peek()["time"] <= self.current_time:
            event = self.event_queue.pop()
            handler = RULE_SWITCH.get(event["event_type"])
            if handler is None:
                print(f"Unknown event: {event['event_type']}")
                continue
            try:
                handler(event, self)
            except Exception as e:
                print(f"[FATAL] Exception in handler for event {event['event_type']} (agent {event['agent_id']}): {e}")
                traceback.print_exc()
                raise

    def _push_event(self, event):
        if event["time"] is None:
            print(f"VARNING: Försöker pusha event utan tidsstämpel: {event['event_type']}")
            return
        if event["time"] < self.simulation_end_time:
            self.event_queue.push(event)

    def close(self):
        self.event_logger.close()

    # ------------------------------------------------------------------
    # Jobbflöden: jobb föds och dör. Utan detta är antalet jobb konstant och
    # Beveridgekurvan en bokföringsidentitet (v linjär i u).
    # ------------------------------------------------------------------
    def _job_flow_cfg(self):
        sim = self.cfg_reader.config.get('simulation', {})
        return {
            'enabled': bool(sim.get('job_flows', False)),
            'delta': float(sim.get('job_destruction_rate', 0.10)),   # per år
            'fill_rate': float(sim.get('vacancy_fill_rate', 0.25)),  # andel av underskott per månad
            'growth': float(sim.get('employer_growth_rate', 0.0)),   # per år, mål-tillväxt
        }

    def _init_job_flows(self):
        """Ger jobben active/created_time och arbetsgivarna ett måltal."""
        # individual_id måste vara object: är kolumnen float64 (enbart NaN)
        # höjer pandas 2.x TypeError när ett sträng-id skrivs in. I praktiken
        # räddas det av batch-matchningen vid t=0, men en händelsedriven
        # anställning i en värld utan föregående batch skulle falla.
        if 'individual_id' in self.jobs.columns and self.jobs['individual_id'].dtype != object:
            self.jobs['individual_id'] = self.jobs['individual_id'].astype(object)
        if 'pending' not in self.jobs.columns:
            # Tillsatt men ännu inte tillträtt. Positionen är en öppen vakans i
            # statistiken men får inte sökas av någon annan.
            self.jobs['pending'] = False
        if 'active' not in self.jobs.columns:
            self.jobs['active'] = True
            self.jobs['created_time'] = float(self.current_time)
            self.jobs['destroyed_time'] = np.nan
        if 'target_size' not in self.employers.columns:
            counts = self.jobs[self.jobs['active']].groupby('employer_id').size()
            self.employers['target_size'] = (
                self.employers['employer_id'].map(counts).fillna(0).astype(float))
        self._next_job_seq = len(self.jobs)

    def _schedule_destruction(self, job_ids, t_now):
        """Exponentiell livslängd med hasard delta (per år)."""
        cfg = self._job_flow_cfg()
        if not cfg['enabled'] or cfg['delta'] <= 0 or len(job_ids) == 0:
            return
        scale = 365.25 / cfg['delta']
        lifetimes = np.random.exponential(scale, size=len(job_ids))
        for job_id, life in zip(job_ids, lifetimes):
            self._push_event({
                "time": float(t_now + life),
                "agent_id": None,
                "event_type": "destroy_job",
                "params": {"job_id": job_id},
            })

    def post_vacancies_batch(self, t_now):
        """Skapar nya jobb mot arbetsgivarnas måltal. Körs en gång per månad.

        Underskott = mål - aktiva jobb. En andel fill_rate av underskottet
        postas varje månad, vilket ger en stock av vakanser i omlopp i stället
        för omedelbar återfyllnad. Måltalet växer med growth (0 = stationärt);
        en teknologichock sänker måltalet, vilket är hur chocken förstör jobb.
        """
        cfg = self._job_flow_cfg()
        if not cfg['enabled']:
            return 0
        jobs = self.jobs
        active = jobs[jobs['active']]
        n_active = active.groupby('employer_id').size()
        emp = self.employers
        if cfg['growth']:
            emp['target_size'] = emp['target_size'] * (1.0 + cfg['growth'] / 12.0)
        target = emp.set_index('employer_id')['target_size']
        deficit = (target - n_active.reindex(target.index).fillna(0)).clip(lower=0)
        # Stokastisk avrundning: floor() skulle nolla alla underskott under
        # 1/fill_rate, vilket systematiskt kväver jobbskapandet hos små
        # arbetsgivare (i Mora är 681 av 792 mikroföretag).
        expected = deficit * cfg['fill_rate']
        base = np.floor(expected)
        n_new = (base + (np.random.random(len(expected)) < (expected - base))).astype(int)
        n_new = n_new[n_new > 0]
        if n_new.empty:
            return 0

        # Mall per arbetsgivare ur ALLA jobb, inte bara aktiva: en arbetsgivare
        # som tillfälligt förlorat alla sina positioner måste kunna posta igen
        # (annars dör mikroföretag permanent vid första förstörelsen).
        proto = jobs.drop_duplicates('employer_id', keep='last').set_index('employer_id')
        rows, new_ids = [], []
        for employer_id, k in n_new.items():
            if employer_id not in proto.index:
                continue
            base = proto.loc[employer_id]
            for _ in range(int(k)):
                onet_code = self._draw_occupation_for_employer(base)
                geom = self._geom_lookup(onet_code)
                jid = f"N{self._next_job_seq:07d}"      # N = nypostad, undviker krock
                self._next_job_seq += 1
                row = base.to_dict()
                row.update({
                    "job_id": jid, "employer_id": employer_id, "individual_id": None,
                    "onet_code": onet_code, "active": True,
                    # Mallen kopierar ALLA kolumner. Utan denna rad ärver ett
                    # nyskapat jobb mallens pending-flagga och föds osökbart:
                    # det räknas som vakans men kan aldrig tillsättas. Över fem
                    # år lade det 3 688 döda vakanser i Mora medan
                    # sysselsättningen föll från 9 900 till 6 505.
                    "pending": False,
                    "created_time": float(t_now), "destroyed_time": np.nan,
                })
                if geom is not None:
                    row.update(geom)
                # geom ger yrkets fältlön; arbetsgivareffekten är en egenskap
                # hos arbetsgivaren och följer med mallen, som är samma
                # arbetsgivare. Utan detta tappar nypostade jobb eta och
                # betalar yrkets normallön oavsett var de sitter.
                if "wage_eta" in row and pd.notna(row.get("wage_eta")):
                    row["wage"] = float(row["wage"]) * float(np.exp(row["wage_eta"]))
                rows.append(row); new_ids.append(jid)
        if not rows:
            return 0
        self.jobs = pd.concat([jobs, pd.DataFrame(rows)], ignore_index=True)
        self._schedule_destruction(new_ids, t_now)
        return len(rows)

    def _occupation_source(self):
        return str(self.cfg_reader.config.get("simulation", {})
                   .get("occupation_source", "sni")).lower()

    def _table_exists(self, name):
        cur = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
        return cur.fetchone() is not None

    def _occupation_profile(self, municipal_code):
        """Yrkesfordelning for en kommun, samma kalla som scenariobyggaren.

        Tidigare fragade den har vagen ALLTID registertabellen
        occupation_weights_by_municipality, oavsett occupation_source, och
        svalde felet med except Exception. Med den forvalda kallan 'sni'
        finns den tabellen inte, sa varje nytt jobb foll tillbaka pa mallens
        yrkeskod. Eftersom mallen ar arbetsgivarens sist tillagda rad blev
        varje nytt jobb en kopia av det forra, och arbetsgivaren drev mot
        monokultur i uppgiftsrummet: med tio procents destruktion per ar ar
        ungefar en tredjedel av bestandet efter fem ar kopior av ETT yrke per
        arbetsgivare. Det urholkar arbetsgivarens centroid och tackningen av
        uppgiftsrummet, alltsa glesbygdspapprets oberoende variabel.

        SNI-vagen ar samma rakning som ScenarioBuilder._sni_occupational_profile:
        kommunens SNI-andel gonger yrkesfordelningen inom varje SNI,
        normaliserad. Koder utan geometri slapps har i stallet for att tyst
        falla igenom _geom_lookup.
        """
        if self.conn is None:
            return None
        src = self._occupation_source()
        krav = (["occupation_weights_by_municipality"] if src == "register"
                else ["employment_municipality_sni", "sni_onet_link"])
        saknas = [t for t in krav + ["onet_occupation_space"]
                  if not self._table_exists(t)]
        if saknas:
            raise ValueError(
                f"occupation_source='{src}' kraver tabellerna {krav} plus "
                f"onet_occupation_space, men {saknas} saknas i databasen. "
                "Registerkallan fylls av scripts/load_occupation_weights.py, "
                "SNI-kallan av scripts/create_database.py och "
                "scripts/load_task_geometry.py. Utan dem skulle nya jobb arva "
                "mallens yrke och arbetsgivaren driva mot monokultur.")
        if src == "register":
            df = pd.read_sql(
                "SELECT w.onet_code, SUM(w.weight) AS weight "
                "  FROM occupation_weights_by_municipality w "
                "  JOIN onet_occupation_space g ON g.onet_code = w.onet_code "
                " WHERE w.municipal_code = ? GROUP BY w.onet_code",
                self.conn, params=(str(municipal_code),))
        else:
            df = pd.read_sql(
                "WITH sni AS ("
                "  SELECT sni_code, CAST(employed AS REAL) AS emp"
                "    FROM employment_municipality_sni"
                "   WHERE municipal_code = ? AND employed > 0"
                "     AND year = (SELECT MAX(year) FROM employment_municipality_sni"
                "                  WHERE municipal_code = ?)),"
                " lsum AS (SELECT sni_code, SUM(CAST(freq AS REAL)) AS s"
                "            FROM sni_onet_link GROUP BY sni_code)"
                " SELECT l.onet_code,"
                "        SUM((s.emp / (SELECT SUM(emp) FROM sni))"
                "            * (CAST(l.freq AS REAL) / ls.s)) AS weight"
                "   FROM sni s"
                "   JOIN sni_onet_link l ON l.sni_code = s.sni_code"
                "   JOIN lsum ls        ON ls.sni_code = s.sni_code"
                "   JOIN onet_occupation_space g ON g.onet_code = l.onet_code"
                "  WHERE ls.s > 0"
                "  GROUP BY l.onet_code",
                self.conn, params=(str(municipal_code), str(municipal_code)))
        df = df[df["weight"] > 0]
        if df.empty:
            raise ValueError(
                f"occupation_source='{src}' gav ingen yrkesfordelning for kommun "
                f"{municipal_code}. Registerkallan kraver "
                "occupation_weights_by_municipality (scripts/load_occupation_weights.py); "
                "SNI-kallan kraver employment_municipality_sni och sni_onet_link "
                "(scripts/create_database.py). Nya jobb skulle annars arva mallens "
                "yrke och arbetsgivaren driva mot monokultur.")
        p = df["weight"].to_numpy(dtype=float)
        return df["onet_code"].to_numpy(), p / p.sum()

    def _draw_occupation_for_employer(self, base_row):
        """Yrkeskod for ett nytt jobb: samma fordelning som scenariobyggaren."""
        if not hasattr(self, "_occ_draw_cache"):
            self._occ_draw_cache = {}
        key = base_row.get("municipal_code")
        if key not in self._occ_draw_cache:
            self._occ_draw_cache[key] = self._occupation_profile(key)
        drawn = self._occ_draw_cache[key]
        if drawn is None:                       # syntetisk varld utan databas
            return base_row.get("onet_code")
        codes, p = drawn
        return str(np.random.choice(codes, p=p))

    def _geom_lookup(self, onet_code):
        """Yrkets geometri, pris OCH kravintensitet.

        r_req måste vara med. Ett nytt jobb får ett nytt yrke ur
        _draw_occupation_for_employer men byggs ur en mall med
        row = base.to_dict(); saknas r_req här behåller jobbet MALLENS krav
        medan position, radie och lön kommer från det nya yrket. Position och
        pris ur ett yrke, krav ur ett annat, utan NaN och utan varning. Felet
        ärvs dessutom vidare, eftersom mallen är den sist tillagda raden per
        arbetsgivare, och växer därför under körningen.

        Det tidigare 'except Exception: _geom_df = None' dolde samma sak en
        gång till: en trasig eller gammal tabell gav tyst noll geometri åt
        alla nya jobb. En värld utan databas (syntetiska tester) är ett
        legitimt fall och behandlas för sig; ett SQL-fel är det inte.
        """
        if not hasattr(self, "_geom_df"):
            if self.conn is None:
                self._geom_df = None
            else:
                self._geom_df = pd.read_sql(
                    "SELECT onet_code, chi, xi, x_occ, y_occ, r_o, w_rel, r_req, "
                    "geom_source FROM onet_occupation_space",
                    self.conn).set_index("onet_code")
        if self._geom_df is None or onet_code not in self._geom_df.index:
            return None
        r = self._geom_df.loc[onet_code]
        return {"chi": float(r["chi"]), "xi": float(r["xi"]),
                "x_occ": float(r["x_occ"]), "y_occ": float(r["y_occ"]),
                "r_o": float(r["r_o"]), "geom_source": str(r["geom_source"]),
                "wage": float(r["w_rel"]) if pd.notna(r["w_rel"]) else 1.0,
                "r_req": float(r["r_req"]) if pd.notna(r["r_req"]) else np.nan}

    def _init_events(self):
        self._init_job_flows()
        if "onet_code" in self.individuals.columns and not hasattr(self, "circles"):
            self.init_competence()
        if self._job_flow_cfg()['enabled']:
            self._schedule_destruction(self.jobs.loc[self.jobs['active'], 'job_id'].tolist(),
                                       self.current_time)
        # Schemalägg quit_job för alla som är employed från början
        employed_mask = self.individuals['status'] == 'employed'
        n_emp = employed_mask.sum()
        if n_emp > 0:
            timing = self.cfg_reader.get_event_timing('quit_job')
            print("QUIT_JOB TIMING:", timing)
            if timing['dist'] == 'normal':
                durations = np.random.normal(timing['mean'], timing['std'], size=n_emp)
                durations = np.clip(durations, 1, None)  # undvik negativa tider
            elif timing['dist'] == 'lognormal':
                sigma = timing.get('sigma', 0.4)
                mu = np.log(timing['mean']) - 0.5 * sigma ** 2
                durations = np.random.lognormal(mean=mu, sigma=sigma, size=n_emp)
            else:
                raise ValueError(f"Unknown dist for quit_job: {timing['dist']}")
            for idx, t_quit in zip(self.individuals.index[employed_mask], durations):
                event = {
                    "time": float(self.current_time + t_quit),
                    "agent_id": idx,
                    "event_type": "quit_job",
                    "params": {}
                }
                self._push_event(event)

        # Schemalägg start_job_search för arbetslösa från början
        unemployed_mask = self.individuals['status'] == 'unemployed'
        n_unemp = unemployed_mask.sum()
        if n_unemp > 0:
            timing = self.cfg_reader.get_event_timing('start_job_search')
            for idx in self.individuals.index[unemployed_mask]:
                if timing['dist'] == 'exponential':
                    interval = np.random.exponential(timing['mean'])
                elif timing['dist'] == 'uniform':
                    interval = np.random.uniform(timing['min'], timing['max'])
                else:
                    interval = 0.0
                event = {
                    "time": float(self.current_time + interval),
                    "agent_id": idx,
                    "event_type": "start_job_search",
                    "params": {}
                }
                self._push_event(event)

        # Schemalägg kalenderhändelser (new_month, new_year)
        self.schedule_calendar_events()

    def schedule_calendar_events(self):
        n_years = self.cfg_reader.config.get('simulation', {}).get('n_years', 5)
        start_year = self.cfg_reader.config.get('simulation', {}).get('start_year', 2024)
        start_month = self.cfg_reader.config.get('simulation', {}).get('start_month', 1)

        day = 0
        # Lägg till new_year för startåret
        event = {
            "time": day,
            "agent_id": None,
            "event_type": "new_year",
            "params": {"year": start_year}
        }
        self._push_event(event)

        for y in range(n_years):
            current_year = start_year + y
            months_in_year = list(range(1, 13))
            if y == 0 and start_month > 1:
                months_in_year = list(range(start_month, 13))
            for current_month in months_in_year:
                event = {
                    "time": day,
                    "agent_id": None,
                    "event_type": "new_month",
                    "params": {"year": current_year, "month": current_month}
                }
                self._push_event(event)
                # Räkna ut dagar i månaden
                if current_month == 2 and is_leap_year(current_year):
                    days_in_month = 29
                else:
                    days_in_month = MONTH_LENGTHS[current_month - 1]
                day += days_in_month
            # Lägg till new_year för nästa år (utom sista året)
            if y < n_years - 1:
                event = {
                    "time": day,
                    "agent_id": None,
                    "event_type": "new_year",
                    "params": {"year": current_year + 1}
                }
                self._push_event(event)

    # ------------------------------------------------------------------
    # Kompetenscirklar (docs/individmodell.md, avsnitt 2)
    # ------------------------------------------------------------------
    def competence_params(self):
        from core.occupations.competence import CompetenceParams
        if not hasattr(self, "_cp"):
            self._cp = CompetenceParams.from_config(
                self.cfg_reader.config.get("simulation", {}))
        return self._cp

    def init_competence(self):
        """Bygger startpopulationens cirklar ur onet_code, education_level och
        tenure_years, och skriver de härledda måtten till individtabellen."""
        from core.occupations.competence import Circles, seed_circles
        ind = self.individuals
        p = self.competence_params()
        self.circles = Circles(len(ind), p.K)
        codes = ind["onet_code"].to_numpy() if "onet_code" in ind.columns else [None] * len(ind)
        xs = ind["x_occ"].to_numpy(float); ys = ind["y_occ"].to_numpy(float)
        ro = (ind["r_o_home"].to_numpy(float) if "r_o_home" in ind.columns
              else np.full(len(ind), 0.27))
        ten = (ind["tenure_years"].to_numpy(float) if "tenure_years" in ind.columns
               else np.full(len(ind), 5.0))
        edu = (ind["education_level"].to_numpy() if "education_level" in ind.columns
               else np.full(len(ind), 0))
        for i in range(len(ind)):
            e = edu[i]
            try:
                e = int(float(e))
            except (TypeError, ValueError):
                e = 0
            seed_circles(self.circles, i, codes[i], xs[i], ys[i], ro[i], ten[i], e, p)
        self._active_key = np.full(len(ind), -1, dtype=np.int64)
        st = ind["status"].to_numpy() if "status" in ind.columns else None
        if st is not None:
            for i in np.flatnonzero(st == "employed"):
                if codes[i] is not None and not (isinstance(codes[i], float) and np.isnan(codes[i])):
                    self._active_key[i] = self.circles.code(str(codes[i]))
        self._write_competence_summary()

    def _write_competence_summary(self):
        summ = self.circles.summarize()
        ind = self.individuals
        for col in ("x_occ", "y_occ", "chi", "xi", "r_i"):
            ind[col] = summ[col]
        ind["R"] = summ["R"]

    def set_active_occupation(self, idx, onet_code, x, y, r_o):
        """Anropas vid tillträde: individen arbetar nu i onet_code, och den
        cirkeln får exponering och skärpning i kommande månadssteg."""
        if not hasattr(self, "circles"):
            return
        c = self.circles
        k = c.code(str(onet_code))
        if not (c.key[idx] == k).any():
            c.add(idx, str(onet_code), float(x), float(y), float(r_o) ** 2, 0.0,
                  rho2_home=float(r_o) ** 2)
        self._active_key[idx] = k

    def clear_active_occupation(self, idx):
        if hasattr(self, "_active_key"):
            self._active_key[idx] = -1

    def evolve_competence(self, dt_years):
        if not hasattr(self, "circles"):
            return
        self.circles.evolve(dt_years, self._active_key, self.competence_params())
        self._write_competence_summary()

    def job_index(self):
        """job_id -> positionsindex. Uppslag via boolesk jämförelse över hela
        tabellen kostade 825 mikrosekunder per anrop; en dict kostar 33."""
        n = len(self.jobs)
        if getattr(self, "_ji_n", None) != n:
            self._ji = {j: i for i, j in enumerate(self.jobs["job_id"].to_numpy())}
            self._ji_n = n
        return self._ji

    def vacant_mask(self):
        """Boolesk vy över lediga, aktiva positioner, underhållen inkrementellt.

        Att räkna om masken ur individual_id kostade 392 mikrosekunder per
        sökning, eftersom isna på en strängkolumn är dyr: 6.7 av 33 sekunder i
        en Mora-körning låg i _isna_string_dtype. Cachad array kostar 3.
        Masken byggs om när tabellen ändrar längd och uppdateras punktvis av
        set_job_filled och set_job_inactive.
        """
        n = len(self.jobs)
        if getattr(self, "_vm_n", None) != n:
            filled = self.jobs["individual_id"].notna().to_numpy()
            act = (self.jobs["active"].to_numpy(dtype=bool)
                   if "active" in self.jobs.columns else np.ones(n, dtype=bool))
            pend = (self.jobs["pending"].to_numpy(dtype=bool)
                    if "pending" in self.jobs.columns else np.zeros(n, dtype=bool))
            self._vm = (~filled) & act & (~pend)
            self._vm_n = n
        return self._vm

    def set_job_filled(self, job_id, filled):
        """Håller vakansmasken i synk när en position tillsätts eller frigörs.

        Går via vacant_mask(), som bygger om masken när tabellen ändrat längd.
        Direkt åtkomst till _vm gav IndexError när en nypostad position
        förstördes innan någon sökning hunnit utlösa ombyggnaden."""
        pos = self.job_index().get(job_id)
        if pos is not None:
            vm = self.vacant_mask()
            if pos < vm.size:
                vm[pos] = not filled
        if pos is not None and "pending" in self.jobs.columns:
            # Rensas i båda riktningarna: rekryteringen är avslutad antingen
            # genom tillträde eller genom att positionen frigjorts.
            self.jobs.iat[pos, self.jobs.columns.get_loc("pending")] = False

    # ---- ansökningar ------------------------------------------------------
    def file_application(self, job_id, idx, t_now, **bud):
        """Lägger en ansökan och öppnar annonsen om den inte redan är öppen.

        Fönstret schemalägger EN close_vacancy per annons, vid första
        ansökan. En vakans utan sökande får därför ingen händelse alls, vilket
        är både billigt och rätt: den står kvar och kan hittas igen.

        Under fönstret byter ingenting tillstånd -- arbetaren är arbetslös och
        positionen ledig -- så bokföringsidentiteten U = L - J + V är oberörd.
        """
        if not hasattr(self, "applications"):
            self.applications = {}
        self.applicant_counts()      # materialisera FÖRE mutationen, annars
                                     # räknas den nya raden två gånger
        first = job_id not in self.applications
        kö = self.applications.setdefault(job_id, [])
        if any(a["idx"] == idx for a in kö):
            return False                      # redan sökt, ingen dubblett
        kö.append(dict(idx=idx, t=float(t_now), **bud))
        self._bump_applicant_count(job_id, 1.0)
        if first:
            days = float(self.cfg_reader.config.get("simulation", {})
                         .get("application_window_days", 40.0))
            self._push_event({"time": float(t_now) + days, "agent_id": idx,
                              "event_type": "close_vacancy",
                              "params": {"job_id": job_id}})
        return True

    def applicant_counts(self):
        """Antal liggande ansökningar per jobbposition, underhållen array.

        Behövs vid VARJE sökning, så den byggs inte om per anrop: en array
        över femtontusen jobb allokerad hundratusentals gånger är ren
        allokeringsvärme. Samma mönster som vacant_mask -- byggs om när
        tabellen ändrar längd, uppdateras punktvis av file_application och
        close_application_window.
        """
        n = len(self.jobs)
        if getattr(self, "_ac_n", None) != n:
            self._ac = np.zeros(n, dtype=float)
            self._ac_n = n
            pos_of = self.job_index()
            for jid, kö in getattr(self, "applications", {}).items():
                pos = pos_of.get(jid)
                if pos is not None and pos < n:
                    self._ac[pos] = len(kö)
        return self._ac

    def _bump_applicant_count(self, job_id, delta):
        ac = self.applicant_counts()
        pos = self.job_index().get(job_id)
        if pos is not None and pos < ac.size:
            ac[pos] = max(0.0, ac[pos] + delta)

    def close_application_window(self, job_id):
        if not hasattr(self, "applications"):
            self.applications = {}
        self.applicant_counts()      # samma skäl som i file_application
        kö = self.applications.pop(job_id, [])
        if kö:
            self._bump_applicant_count(job_id, -float(len(kö)))
        return kö

    def n_open_applications(self):
        return sum(len(v) for v in getattr(self, "applications", {}).values())

    def set_job_pending(self, job_id):
        """Positionen är utlovad men inte tillträdd: ingen annan kan söka den,
        men den räknas fortfarande som en öppen vakans."""
        pos = self.job_index().get(job_id)
        if pos is None:
            return
        if "pending" in self.jobs.columns:
            self.jobs.iat[pos, self.jobs.columns.get_loc("pending")] = True
        vm = self.vacant_mask()
        if pos < vm.size:
            vm[pos] = False

    def set_job_inactive(self, job_id):
        pos = self.job_index().get(job_id)
        if pos is not None:
            vm = self.vacant_mask()
            if pos < vm.size:
                vm[pos] = False

    def job_arrays(self):
        """Cachad numpy-vy av jobbtabellen, byggs om när tabellen ändrar längd
        (dvs. när vakanser postas). Attributen x_occ, y_occ, r_o, wage, x, y
        ändras inte för ett befintligt jobb."""
        from core.occupations.utils import build_job_arrays
        n = len(self.jobs)
        if getattr(self, "_ja_n", None) != n:
            self._ja = build_job_arrays(self.jobs)
            self._ja_n = n
        return self._ja

    # match_individuals_to_jobs och update_after_matching utgick i 0069.
    # De körde interleaved_multilevel_batch_matching / global_greedy_matching,
    # en tidigare version av samma modell: samma överskott, samma dragning på
    # passform, samma sortering på S -- men utan kön i överskottet (0057),
    # arbetsgivarens urval (0055), kravgrinden (0049) och loneformeln
    # w = Pi_j * p**theta med arbetsgivareffekt (0061, 0063). Nio tusen
    # matchningar, alltså större delen av beståndet i flera år, var därför
    # gjorda under en modell vi inte längre tror på.
    #
    # Dessutom partitionerade den GEOGRAFISKT, DeSO -> kommun -> globalt.
    # Individer i samma bostadsområde liknar varandra i uppgiftsrummet, så den
    # som råkade komma tidigt i deso_codes-ordningen tog de bästa jobben i hela
    # kommunen: en gradient efter körordning, permanent, i en modell där
    # geografi är glesbygdspapprets förklaringsvariabel.
    #
    # Uppstarten ligger nu i core.matching_core.bootstrap_matching och anropar
    # samma funktioner som händelsehanterarna. _seed_wages_for_matched (0068)
    # utgår med den: startlönen kommer ur negotiated_wage som för alla andra.

    def employer_training_prob(self, n_employees):
        tr_cfg = self.cfg_reader.config.get('defaults', {}).get('employer', {}).get('training_prob_by_size', {})
        if n_employees < 10:
            return tr_cfg.get('small', 0.05)
        elif n_employees < 100:
            return tr_cfg.get('medium', 0.15)
        else:
            return tr_cfg.get('large', 0.40)
        

# Importera event handlers sist!
from core.event_handlers import *
