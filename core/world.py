# core/world.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
import numpy as np
import pandas as pd
from core.geography.geoworld import GeoWorld
#from core.plotting.plot_selected_municipalities import plot_selected_municipalities
#from core.matching import greedy_deso_matching, interleaved_multilevel_batch_matching
from core.matching import interleaved_multilevel_batch_matching, multilevel_exhaustive_matching

from core.log import log
from core.events import Event, EventQueue
from core.log import EventLogger

import traceback

def print_exception_hook(exctype, value, tb):
    print("\n--- UNCAUGHT EXCEPTION ---")
    traceback.print_exception(exctype, value, tb)
    print("--- END EXCEPTION ---\n")

sys.excepthook = print_exception_hook

DAYS_PER_YEAR = 365.25  # Average days per year, accounting for leap years
MONTH_LENGTHS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def is_leap_year(year):
    """Returns True if the year is a leap year."""
    return (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))


class World:
    def __init__(self, db_path, cfg_reader, outdir, geoworld=None, scope=None, individuals=None, jobs=None, employers=None, events=None):
        """
        World collects all core data and manages the simulation for a region or scenario.
        If DataFrames (individuals, jobs, employers) are provided, they are used directly
        otherwise empty DataFrames are created.
        """
        self.db_path = db_path
        self.scope = scope
        self.cfg_reader = cfg_reader

        self.geoworld = geoworld if geoworld is not None else GeoWorld(db_path)

        # Use only explicitly provided DataFrames, otherwise create empty
        self.individuals = individuals if individuals is not None else pd.DataFrame()
        self.jobs = jobs if jobs is not None else pd.DataFrame()
        self.employers = employers if employers is not None else pd.DataFrame()
        self.events = events if events is not None else pd.DataFrame(columns=["time", "agent_id", "event_type", "params"])
        self.current_time = 0

        self.matchings = pd.DataFrame()

        self.event_handlers = {
            'quit_job': self.handle_quit_job,
            'start_job_search': self.handle_start_job_search,
            'start_job': self.handle_start_job,
            'new_month': self.handle_new_month,
            'new_year': self.handle_new_year,
            # Nya events:
            'start_education': self.handle_start_education,
            'end_education': self.handle_end_education,
            'start_internal_training': self.handle_start_internal_training,
            'internal_job_change': self.handle_internal_job_change,
            'career_break': self.handle_career_break,
        }

        # Event queue (AP8) – från scenario, eller tom DataFrame
        self.event_queue = EventQueue()
        self.current_time = 0  # Starttid i simuleringen, kan vara t.ex. dagar, månader, år

        self.simulation_end_time = DAYS_PER_YEAR*self.cfg_reader.config.get('simulation', {}).get('n_years', 1)  # Default to 1 year in days
        log(f"simulation_end_time={self.simulation_end_time}")
        # Output/resultat – samlas/uppdateras löpande
        self.matchings = pd.DataFrame()

        # Logging configuration
        self.log_to_console = self.cfg_reader.config.get('simulation', {}).get('log_to_console', False)
        self.log_to_file = self.cfg_reader.config.get('simulation', {}).get('log_to_file', True)

        self.eventlog_path = os.path.join(outdir, "eventlog.csv")
        self.event_logger = EventLogger(filepath=self.eventlog_path if self.log_to_file else None)

    def draw_employment_duration(self, avg_employment_duration, employment_duration_std, size=None):
        mean = avg_employment_duration
        std = employment_duration_std
        sigma = np.sqrt(np.log(1 + (std / mean) ** 2))
        mu = np.log(mean) - 0.5 * sigma ** 2
        return np.random.lognormal(mean=mu, sigma=sigma, size=size)

    def set_scenario_data(self, individuals=None, jobs=None, employers=None, events=None):
        """
        Replace agent and event data with data from ScenarioBuilder.
        """
        if individuals is not None:
            self.individuals = individuals
        if jobs is not None:
            self.jobs = jobs
        if employers is not None:
            self.employers = employers
        if events is not None:
            self.events = events

    def match_individuals_to_jobs(self, individuals=None, mode="deso_interleaved", **kwargs):
        """
        Batch-matches individuals to jobs. If individuals is None, all unemployed individuals are used.
        Returns DataFrame with 'individual_id', 'job_id', etc.
        """
        if individuals is None:
            workforce = self.individuals[self.individuals['status'] == 'unemployed'].copy()
        else:
            workforce = individuals.copy()
        
        # I din matchningsfunktion eller precis före
        vacant_jobs = self.jobs[self.jobs['individual_id'].isna()]

        if mode == "interleaved_multilevel":
            # Import your matching function!
            return interleaved_multilevel_batch_matching(
                workforce,
                vacant_jobs,
                alpha_chi=kwargs.get("alpha_chi", 5.0),
                alpha_xi=kwargs.get("alpha_xi", 5.0),
                alpha_geo=kwargs.get("alpha_geo", 1.0),
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
            matchings = self.matchings

        # Update individuals
        matched = matchings.set_index('individual_id')['job_id']
        idx = self.individuals['individual_id'].isin(matched.index)
        self.individuals.loc[idx, 'status'] = 'employed'
        self.individuals.loc[idx, 'job_id'] = self.individuals.loc[idx, 'individual_id'].map(matched)

        # Update jobs
        job_to_ind = matchings.set_index('job_id')['individual_id']
        job_idx = self.jobs['job_id'].isin(job_to_ind.index)
        self.jobs.loc[job_idx, 'individual_id'] = self.jobs.loc[job_idx, 'job_id'].map(job_to_ind)

        n_emp = (self.individuals['status'] == 'employed').sum()
        n_unemp = (self.individuals['status'] == 'unemployed').sum()
        n_notlf = (self.individuals['status'] == 'not_in_labor_force').sum()
        n_vacant = (self.jobs['individual_id'].isna()).sum()

        self.event_logger.log_event(
            self,
            Event(0.00, None, "batch_matching"),
            extra={
                "employed": n_emp,
                "unemployed": n_unemp,
                "not_in_labor_force": n_notlf,
                "vacant_jobs": n_vacant
            }
        )

    def simulate(self):
        self.wallclock_start = time.time()
        self._init_events()

        for ev in self.event_queue.queue:
            if not isinstance(ev.event_type, str):
                print("Event type is not str!", ev)

        while not self.event_queue.is_empty():
            event = self.event_queue.pop()
        
            self.current_time = event.time
            handler = self.event_handlers.get(event.event_type)
            if event.time > self.simulation_end_time:
                print(f"FEL: Executing event {event.event_type} at {event.time}, which is after simulation end time {self.simulation_end_time}")
                break  # <-- AVBRYT SIMULERINGEN!

            if handler:
                try:
                    handler(event)
                except Exception as e:
                    print(f"[FATAL] Exception in handler for event {event.event_type} (agent {event.agent_id}): {e}")
                    import traceback
                    traceback.print_exc()
                    print(f"[DEBUG] event.params: {getattr(event, 'params', None)}")
                    print(f"[DEBUG] individual row: {self.individuals.loc[[event.agent_id]] if event.agent_id in self.individuals.index else 'N/A'}")
                    raise
            else:
                print(f"Unknown event: {event.event_type}")
            # Logging/statistics can be added here

    def close(self):
        """ Shut down after simulation is done. Closes any open resources, e.g. log files.
        """
        if self.log_to_console:
            elapsed = time.time() - self.wallclock_start
            print(f"[TIMER] {elapsed:8.2f}s | simulation_ended")

    def _init_events(self):
        employed_mask = self.individuals['status'] == 'employed'
        n_emp = employed_mask.sum()
        if n_emp > 0:
            # HÄR: använd event_timings och get_event_timing för 'quit_job'
            timing = self.cfg_reader.get_event_timing('quit_job')
            print("QUIT_JOB TIMING:", timing)
            # Du kan nu välja dist, t.ex. normal/lognormal
            if timing['dist'] == 'normal':
                durations = np.random.normal(timing['mean'], timing['std'], size=n_emp)
                durations = np.clip(durations, 1, None)  # undvik negativa tider
            elif timing['dist'] == 'lognormal':
                # Exempel, om lognormal-parametrar
                sigma = timing.get('sigma', 0.4)
                mu = np.log(timing['mean']) - 0.5 * sigma ** 2
                durations = np.random.lognormal(mean=mu, sigma=sigma, size=n_emp)
            else:
                raise ValueError(f"Unknown dist for quit_job: {timing['dist']}")
            for idx, t_quit in zip(self.individuals.index[employed_mask], durations):
                event = Event(self.current_time + t_quit, idx, 'quit_job')
                self.push_event(event)

        # Add new_month/new_year events if desired
        self.schedule_calendar_events()

    def push_event(self, event):
        if event.time is None:
            print(f"VARNING: Försöker pusha event utan tidsstämpel: {event.event_type}")
            return

        if event.time < self.simulation_end_time:
            self.event_queue.push(event)
            
    def schedule_calendar_events(self):
        """
        Schedules 'new_month' and 'new_year' events for the simulation based on config.
        Start year, start month, and number of years control the period's start and length.

        - Handles arbitrary start month and start year.
        - Schedules each month exactly on the right day, even across year boundaries.
        - Handles leap years: February gets 29 days every four years (except years divisible by 100 but not by 400).
        - All calendar logic is done without Pandas or datetime – works entirely on integers.
        - Always creates 'new_year' for the start year (day 0), and then at the beginning of each year.
        - Use event.params['year'], event.params['month'] for further processing.
        """
        n_years = self.cfg_reader.config['simulation'].get('n_years', 5)
        start_year = self.cfg_reader.config['simulation'].get('start_year', 2024)
        start_month = self.cfg_reader.config['simulation'].get('start_month', 1)  # 1-based, 1 = January

        # Simulation always starts on day 0
        year = start_year
        month = start_month
        day = 0

        # new_year always on day 0
        self.push_event(Event(day, None, 'new_year', {'year': year}))

        for y in range(n_years):
            current_year = start_year + y
            months_in_year = list(range(1, 13))
            # Skip months before start month in first year
            if y == 0 and start_month > 1:
                months_in_year = list(range(start_month, 13))
            for current_month in months_in_year:
                self.push_event(Event(day, None, 'new_month', {'year': current_year, 'month': current_month}))
                # Determine month length
                if current_month == 2 and is_leap_year(current_year):
                    days_in_month = 29
                else:
                    days_in_month = MONTH_LENGTHS[current_month - 1]
                day += days_in_month
            # Schedule new_year for next year (if not last year)
            if y < n_years - 1:
                next_year = current_year + 1
                self.push_event(Event(day, None, 'new_year', {'year': next_year}))

    # Eventhandlers below

    def handle_quit_job(self, event):
        idx = event.agent_id
        # Sätt status till arbetslös
        self.individuals.at[idx, 'status'] = 'unemployed'
        job_id = self.individuals.at[idx, 'job_id']
        if pd.notna(job_id):
            self.jobs.loc[self.jobs['job_id'] == job_id, 'individual_id'] = np.nan
            self.individuals.at[idx, 'job_id'] = np.nan

        # === Sannolikhet för utbildning ===
        prop_edu = self.individuals.at[idx, 'propensity_start_education']
        if np.random.rand() < prop_edu:
            # Hämta effekter och tid från config/event_effects och event_timings
            eff = self.cfg_reader.config['simulation']['event_effects']['start_education']['broad']
            timing = self.cfg_reader.get_event_timing('start_education')
            # Stöd för olika distributionsnamn
            if timing['dist'] == 'uniform':
                days_until_start = np.random.uniform(timing['min'], timing['max'])
            else:
                raise ValueError("Unknown dist for start_education")
            edu_event = Event(
                event.time + days_until_start,
                idx,
                'start_education',
                {
                    'education_type': 'broad',
                    'delta_chi': eff['delta_chi'],
                    'delta_H': eff['delta_H'],
                    'duration': eff['duration'],
                    'delta_xi': eff.get('delta_xi', 10),
                }
            )
            self.push_event(edu_event)
        else:
            # === Schemalägg jobbsök baserat på config ===
            timing = self.cfg_reader.get_event_timing('start_job_search')
            if timing['dist'] == 'exponential':
                # mean kan vara i år, konvertera till dagar
                interval = np.random.exponential(timing['mean'])
            else:
                raise ValueError("Unknown dist for start_job_search")
            search_event = Event(event.time + interval, idx, 'start_job_search')
            self.push_event(search_event)

        self.event_logger.log_event(self, event, "individual")


    def handle_start_job(self, event):
        idx = event.agent_id
        job_id = event.params['job_id']
        self.individuals.at[idx, 'status'] = 'employed'
        self.individuals.at[idx, 'job_id'] = job_id
        job_idx = self.jobs['job_id'] == job_id
        self.jobs.loc[job_idx, 'individual_id'] = idx

        self.event_logger.log_event(self, event, extra={'job_id': job_id})

        # Internutbildning: propensity * arbetsgivarens chans
        job_row = self.jobs[self.jobs['job_id'] == job_id].iloc[0]
        n_employees = job_row['employer_size']
        prop_training = self.individuals.at[idx, 'propensity_internal_training']
        P_training = prop_training * self.employer_training_prob(n_employees)

        # Hämta timing från config för internutbildning
        training_timing = self.cfg_reader.get_event_timing('start_internal_training')
        if np.random.rand() < P_training:
            if training_timing['dist'] == 'uniform':
                interval = np.random.uniform(training_timing['min'], training_timing['max'])
            else:
                interval = 28  # fallback, 4 veckor
            t_training = event.time + interval
            training_event = Event(
                t_training,
                idx,
                'start_internal_training',
                {
                    'delta_H': np.random.uniform(0.05, 0.15),
                    'delta_chi': np.random.uniform(0.01, 0.04)
                }
            )
            self.push_event(training_event)

        # Interna byten av arbetsuppgifter, sannolikhet från individen!
        job_change_timing = self.cfg_reader.get_event_timing('internal_job_change')
        prop_job_change = self.individuals.at[idx, 'propensity_internal_job_change']
        if np.random.rand() < prop_job_change:
            if job_change_timing['dist'] == 'exponential':
                interval = np.random.exponential(job_change_timing['mean'])
            elif job_change_timing['dist'] == 'uniform':
                interval = np.random.uniform(job_change_timing['min'], job_change_timing['max'])
            else:
                interval = 182  # fallback, 26 veckor
            t_change = event.time + interval
            change_event = Event(
                t_change,
                idx,
                'internal_job_change',
                {
                    'delta_xi': np.random.uniform(2, 7),
                    'delta_H': np.random.uniform(0.10, 0.25),
                    'delta_chi': np.random.uniform(0.01, 0.03)
                }
            )
            self.push_event(change_event)

        # Schemalägg när individen slutar detta jobb
        quit_timing = self.cfg_reader.get_event_timing('quit_job')
        if quit_timing['dist'] == 'normal':
            duration = np.random.normal(quit_timing['mean'], quit_timing['std'])
            duration = max(duration, 1)  # ingen negativ anställningstid
        elif quit_timing['dist'] == 'lognormal':
            sigma = quit_timing.get('sigma', 0.4)
            mu = np.log(quit_timing['mean']) - 0.5 * sigma ** 2
            duration = np.random.lognormal(mean=mu, sigma=sigma)
        else:
            duration = 365  # fallback, 1 år
        t_quit = event.time + duration
        quit_event = Event(t_quit, idx, 'quit_job')
        self.push_event(quit_event)


    def handle_start_job_search(self, event):
        idx = event.agent_id
        df = self.individuals.loc[[idx]]
        matches = self.match_individuals_to_jobs(
            individuals=df,
            mode="exhaustive_multilevel",
            alpha_chi=self.cfg_reader.config['simulation']['alpha_chi'],
            alpha_xi=self.cfg_reader.config['simulation']['alpha_xi'],
            alpha_geo=self.cfg_reader.config['simulation']['alpha_geo'],
        )
        if not matches.empty:
            job_id = matches.iloc[0]['job_id']            
            utility = matches.iloc[0]['utility']            

            t_start = event.time
            start_event = Event(t_start, idx, 'start_job', {'job_id': job_id})
            self.push_event(start_event)
            self.event_logger.log_event(self, event, extra={"event_detail": "match_completed", "job_id": job_id, "utility": utility})
        else:
            timing = self.cfg_reader.get_event_timing('start_job_search')
            if timing['dist'] == 'exponential':
                interval = np.random.exponential(timing['mean'])
            else:
                # fallback/varning
                interval = 30.0
            t_retry = event.time + interval

            retry_event = Event(t_retry, idx, 'start_job_search')
            self.push_event(retry_event)
            self.event_logger.log_event(self, event, extra={"event_detail": "match_failed"})

    def handle_start_education(self, event):
        idx = event.agent_id
        education_type = event.params.get('education_type', 'specialist')
        
        # Ta ut parametrar, med default och explicit kontroll mot None
        delta_chi = event.params.get('delta_chi', 1.0)
        delta_H = event.params.get('delta_H', 0.1)
        delta_xi = event.params.get('delta_xi', 10.0)  # relevant för 'broad'

        # Om någon är None, använd default och logga en varning
        if delta_chi is None:
            print(f"[VARNING] delta_chi är None i start_education för individ {idx}. Default 1.0 används.")
            delta_chi = 1.0
        if delta_H is None:
            print(f"[VARNING] delta_H är None i start_education för individ {idx}. Default 0.1 används.")
            delta_H = 0.1
        if delta_xi is None:
            print(f"[VARNING] delta_xi är None i start_education för individ {idx}. Default 10.0 används.")
            delta_xi = 10.0

        if education_type == 'specialist':
            self.individuals.at[idx, 'chi'] += delta_chi
            self.individuals.at[idx, 'H'] += delta_H
        elif education_type == 'broad':
            self.individuals.at[idx, 'H'] += delta_H
            self.individuals.at[idx, 'xi'] += delta_xi

        self.individuals.at[idx, 'status'] = 'in_education'
        self.event_logger.log_event(self, event, extra={'education_type': education_type})

        # Schemalägg slut på utbildningen
        education_duration = self.cfg_reader.parse_time_with_unit(event.params.get('duration'))
        if education_duration is None:
            print(f"[VARNING] duration är None i start_education för individ {idx}. Default {DAYS_PER_YEAR} används.")
            education_duration = DAYS_PER_YEAR

        end_event = Event(
            event.time + education_duration,
            idx,
            'end_education',
            {'education_type': education_type}
        )
        self.push_event(end_event)

    def handle_end_education(self, event):
        idx = event.agent_id
        self.individuals.at[idx, 'status'] = 'unemployed'
        self.event_logger.log_event(self, event, extra={'event_detail': 'education_finished'})
        
        # Använd get_event_timing
        timing = self.cfg_reader.get_event_timing('start_job_search')
        if timing['dist'] == 'exponential':
            interval = np.random.exponential(timing['mean'])  # mean redan i dagar
        elif timing['dist'] == 'uniform':
            interval = np.random.uniform(timing['min'], timing['max'])
        else:
            raise ValueError("Unknown dist for start_job_search")
        
        search_event = Event(event.time + interval, idx, 'start_job_search')
        self.push_event(search_event)

    def handle_start_internal_training(self, event):
        idx = event.agent_id

        # Ta ut parametrar med default, skydda mot None
        delta_H = event.params.get('delta_H', 0.2)
        delta_chi = event.params.get('delta_chi', 0.05)

        if delta_H is None:
            print(f"[VARNING] delta_H är None i start_internal_training för individ {idx}. Default 0.2 används.")
            delta_H = 0.2
        if delta_chi is None:
            print(f"[VARNING] delta_chi är None i start_internal_training för individ {idx}. Default 0.05 används.")
            delta_chi = 0.05

        self.individuals.at[idx, 'H'] += delta_H
        self.individuals.at[idx, 'chi'] += delta_chi
        self.event_logger.log_event(self, event, extra={'event_detail': 'start_internal_training'})

        # Möjlighet till rekursiv internutbildning (med låg sannolikhet)
        if self.individuals.at[idx, 'status'] == 'employed' and np.random.rand() < 0.15:
            training_timing = self.cfg_reader.get_event_timing('start_internal_training')
            if training_timing['dist'] == 'uniform':
                interval = np.random.uniform(training_timing['min'], training_timing['max'])
            else:
                interval = 28  # fallback, t.ex. 4 veckor

            t_training = event.time + interval
            # Slumpa nya parametrar, skydda även här
            rec_delta_H = np.random.uniform(0.03, 0.10)
            rec_delta_chi = np.random.uniform(0.01, 0.02)

            more_training = Event(
                t_training,
                idx,
                'start_internal_training',
                {'delta_H': rec_delta_H, 'delta_chi': rec_delta_chi}
            )
            self.push_event(more_training)

    def handle_internal_job_change(self, event):
        idx = event.agent_id

        # Hämta param med fallback, skydda mot None
        delta_xi = event.params.get('delta_xi', 3)
        delta_H = event.params.get('delta_H', 0.3)
        delta_chi = event.params.get('delta_chi', 0.03)

        if delta_xi is None:
            print(f"[VARNING] delta_xi är None i internal_job_change för individ {idx}. Default 3 används.")
            delta_xi = 3
        if delta_H is None:
            print(f"[VARNING] delta_H är None i internal_job_change för individ {idx}. Default 0.3 används.")
            delta_H = 0.3
        if delta_chi is None:
            print(f"[VARNING] delta_chi är None i internal_job_change för individ {idx}. Default 0.03 används.")
            delta_chi = 0.03

        self.individuals.at[idx, 'xi'] += delta_xi
        self.individuals.at[idx, 'H'] += delta_H
        self.individuals.at[idx, 'chi'] += delta_chi

        self.event_logger.log_event(self, event, extra={'event_detail': 'internal_job_change'})

    def handle_career_break(self, event):
        idx = event.agent_id
        self.individuals.at[idx, 'status'] = 'career_break'
        self.individuals.at[idx, 'chi'] -= event.params.get('delta_chi', 0.05)
        self.individuals.at[idx, 'H'] -= event.params.get('delta_H', 0.02)
        self.event_logger.log_event(self, event, extra={'event_detail': 'career_break'})
        break_duration = event.params.get('duration', 0.5 * DAYS_PER_YEAR)
        end_event = Event(event.time + break_duration, idx, 'start_job_search')
        self.push_event(end_event)

    def handle_new_month(self, event):
        year = event.params.get('year')
        month = event.params.get('month')
        self.event_logger.log_event(self, event, extra={"year": year, "month": month}, print_line=True)

    def handle_new_year(self, event):
        from core.statistics.basic_stats import analyze_world

        year = event.params.get('year')
        stats = analyze_world(self)
        employed = stats['individual_status_counts'].get('employed', 0)
        unemployed = stats['individual_status_counts'].get('unemployed', 0)
        matched = stats.get('matched_pairs', 0)
        unmatched_jobs = stats.get('unmatched_jobs', 0)
        self.event_logger.log_event(self, event, extra={
            "year": year,
            "employed": employed,
            "unemployed": unemployed,
            "matched": matched,
            "unmatched_jobs": unmatched_jobs
        }, print_line=True)

    def employer_training_prob(self, n_employees):
        tr_cfg = self.cfg_reader.config['defaults']['employer']['training_prob_by_size']
        if n_employees < 10:
            return tr_cfg.get('small', 0.05)
        elif n_employees < 100:
            return tr_cfg.get('medium', 0.15)
        else:
            return tr_cfg.get('large', 0.40)

