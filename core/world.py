# core/world.py

import sys
import os
import numpy as np
import pandas as pd
import traceback
import time

from core.geography.geoworld import GeoWorld
from core.matching import interleaved_multilevel_batch_matching, multilevel_exhaustive_matching
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
                    "created_time": float(t_now), "destroyed_time": np.nan,
                })
                if geom is not None:
                    row.update(geom)
                rows.append(row); new_ids.append(jid)
        if not rows:
            return 0
        self.jobs = pd.concat([jobs, pd.DataFrame(rows)], ignore_index=True)
        self._schedule_destruction(new_ids, t_now)
        return len(rows)

    def _draw_occupation_for_employer(self, base_row):
        """Yrkeskod för ett nytt jobb: samma fördelning som scenariobyggaren använde."""
        if not hasattr(self, "_occ_draw_cache"):
            self._occ_draw_cache = {}
        key = base_row.get("municipal_code")
        if key not in self._occ_draw_cache:
            try:
                df = pd.read_sql(
                    "SELECT onet_code, weight FROM occupation_weights_by_municipality "
                    "WHERE municipal_code = ?", self.conn, params=(str(key),))
            except Exception:
                df = pd.DataFrame()
            if df.empty:
                self._occ_draw_cache[key] = None
            else:
                p = df["weight"].to_numpy(dtype=float); p = p / p.sum()
                self._occ_draw_cache[key] = (df["onet_code"].to_numpy(), p)
        drawn = self._occ_draw_cache[key]
        if drawn is None:
            return base_row.get("onet_code")      # behåll arbetsgivarens yrkesmix
        codes, p = drawn
        return str(np.random.choice(codes, p=p))

    def _geom_lookup(self, onet_code):
        if not hasattr(self, "_geom_df"):
            try:
                self._geom_df = pd.read_sql(
                    "SELECT onet_code, chi, xi, x_occ, y_occ, r_o, w_rel, geom_source "
                    "FROM onet_occupation_space", self.conn).set_index("onet_code")
            except Exception:
                self._geom_df = None
        if self._geom_df is None or onet_code not in self._geom_df.index:
            return None
        r = self._geom_df.loc[onet_code]
        return {"chi": float(r["chi"]), "xi": float(r["xi"]),
                "x_occ": float(r["x_occ"]), "y_occ": float(r["y_occ"]),
                "r_o": float(r["r_o"]), "geom_source": str(r["geom_source"]),
                "wage": float(r["w_rel"]) if pd.notna(r["w_rel"]) else 1.0}

    def _init_events(self):
        self._init_job_flows()
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
            self._vm = (~filled) & act
            self._vm_n = n
        return self._vm

    def set_job_filled(self, job_id, filled):
        """Håller vakansmasken i synk när en position tillsätts eller frigörs."""
        pos = self.job_index().get(job_id)
        if pos is not None and getattr(self, "_vm", None) is not None:
            self._vm[pos] = not filled

    def set_job_inactive(self, job_id):
        pos = self.job_index().get(job_id)
        if pos is not None and getattr(self, "_vm", None) is not None:
            self._vm[pos] = False

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

    def match_individuals_to_jobs(self, individuals=None, mode="exhaustive_multilevel", **kwargs):
        """
        Batch-matches individuals to jobs. If individuals is None, all unemployed individuals are used.
        Returns DataFrame with 'individual_id', 'job_id', etc.
        """
        # Undvik onödiga kopior
        if individuals is None:
            workforce = self.individuals[self.individuals['status'] == 'unemployed']
        else:
            workforce = individuals  # Utgå från redan vald DataFrame
        
        if not getattr(self, "_wage_checked", False):
            self._wage_checked = True
            if 'wage' not in self.jobs.columns or self.jobs['wage'].isna().all():
                print("VARNING: jobben saknar lön (kolumnen 'wage'). Matchningen körs "
                      "utan priser: S = p - c*km.")
            elif float(self.jobs['wage'].std(skipna=True) or 0.0) == 0.0:
                print("VARNING: alla jobb har samma lön. Prisfältet är sannolikt inte "
                      "inläst (w_rel tomt i onet_occupation_space).")
        vacant_jobs = self.jobs[self.jobs['individual_id'].isna()]
        if 'active' in self.jobs.columns:
            vacant_jobs = vacant_jobs[vacant_jobs['active']]

        if mode == "interleaved_multilevel":
            # Import your matching function!
            return interleaved_multilevel_batch_matching(
                workforce,
                vacant_jobs,
                alpha_chi=kwargs.get("alpha_chi", 5.0),
                alpha_xi=kwargs.get("alpha_xi", 5.0),
                alpha_geo=kwargs.get("alpha_geo", 1.0),
                sigma_gamma=kwargs.get("sigma_gamma", 1.0),
                utility_min=kwargs.get("utility_min", 0.05),
                commute_cost_per_km=kwargs.get("commute_cost_per_km", 0.005),
                min_surplus=kwargs.get("min_surplus", 0.0),
                batch_frac_deso=kwargs.get("batch_frac_deso", 0.2),
                batch_frac_muni=kwargs.get("batch_frac_muni", 0.1),
                batch_frac_global=kwargs.get("batch_frac_global", 0.05),
                min_batch=kwargs.get("min_batch", 10),
                verbose=kwargs.get("verbose", False)
            )
        elif mode == "exhaustive_multilevel":
            # Import your matching function!
            return multilevel_exhaustive_matching(
                workforce,
                vacant_jobs,
                alpha_chi=kwargs.get("alpha_chi", 5.0),
                alpha_xi=kwargs.get("alpha_xi", 5.0),
                alpha_geo=kwargs.get("alpha_geo", 1.0),
                sigma_gamma=kwargs.get("sigma_gamma", 1.0),
                utility_min=kwargs.get("utility_min", 0.05),
                commute_cost_per_km=kwargs.get("commute_cost_per_km", 0.005),
                min_surplus=kwargs.get("min_surplus", 0.0),
                verbose=kwargs.get("verbose", False)
            )
        else:
            raise ValueError(f"Unknown matching mode: {mode}")

    def update_after_matching(self, matchings=None):
        """
        Updates both individuals and jobs after matching.
        Takes an explicit matchings DataFrame if provided, otherwise self.matchings.
        """
        if matchings is None:
            matchings = self._matchings

        # Update individuals
        matched = matchings.set_index('individual_id')['job_id']
        idx = self.individuals['individual_id'].isin(matched.index)
        self.individuals.loc[idx, 'status'] = 'employed'
        self.individuals.loc[idx, 'job_id'] = self.individuals.loc[idx, 'individual_id'].map(matched)

        # Update jobs
        job_to_ind = matchings.set_index('job_id')['individual_id']
        job_idx = self.jobs['job_id'].isin(job_to_ind.index)
        self.jobs.loc[job_idx, 'individual_id'] = self.jobs.loc[job_idx, 'job_id'].map(job_to_ind)

    def employer_training_prob(self, n_employees):
        tr_cfg = self.cfg_reader.config['defaults']['employer']['training_prob_by_size']
        if n_employees < 10:
            return tr_cfg.get('small', 0.05)
        elif n_employees < 100:
            return tr_cfg.get('medium', 0.15)
        else:
            return tr_cfg.get('large', 0.40)
        

# Importera event handlers sist!
from core.event_handlers import *
