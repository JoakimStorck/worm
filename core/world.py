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

    def _init_events(self):
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
        n_years = self.cfg_reader.config['simulation'].get('n_years', 5)
        start_year = self.cfg_reader.config['simulation'].get('start_year', 2024)
        start_month = self.cfg_reader.config['simulation'].get('start_month', 1)

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
        
        vacant_jobs = self.jobs[self.jobs['individual_id'].isna()]

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
