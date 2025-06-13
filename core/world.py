# worm/world.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
import numpy as np
import pandas as pd
from core.geography.geoworld import GeoWorld
from core.plotting.plot_selected_municipalities import plot_selected_municipalities
from core.matching import greedy_deso_matching, interleaved_multilevel_batch_matching

from core.statistics.log import log
from core.events import Event, EventQueue
from core.statistics.log import EventLogger

DAYS_PER_YEAR = 365.25  # Average days per year, accounting for leap years
MONTH_LENGTHS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def is_leap_year(year):
    """Returns True if the year is a leap year."""
    return (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))


class World:
    def __init__(self, db_path, config, geoworld=None, scope=None, individuals=None, jobs=None, employers=None, events=None):
        """
        World collects all core data and manages the simulation for a region or scenario.
        If DataFrames (individuals, jobs, employers) are provided, they are used directly
        otherwise empty DataFrames are created.
        """
        self.db_path = db_path
        self.scope = scope
        self.config = config

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

        self.simulation_end_time = DAYS_PER_YEAR*self.config.get('simulation', {}).get('n_years', 1)  # Default to 1 year in days
        log(f"simulation_end_time={self.simulation_end_time}")
        # Output/resultat – samlas/uppdateras löpande
        self.matchings = pd.DataFrame()

        # Logging configuration
        self.log_to_console = self.config.get('simulation', {}).get('log_to_console', False)
        self.log_to_file = self.config.get('simulation', {}).get('log_to_file', True)
        self.logfile_path = self.config.get('simulation', {}).get('logfile_path', 'output/worm_simulation.log')

        self.event_logger = EventLogger(filepath=self.logfile_path if self.log_to_file else None)

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

        self.event_logger.log_generic_event(
            Event(0.00, None, "batch_matching"),
            data={
                "employed": n_emp,
                "unemployed": n_unemp,
                "not_in_labor_force": n_notlf,
                "vacant_jobs": n_vacant
            }
        )

        # Sätt gärna en egen katalog/loggningsnamn om du vill samla olika loggar
        outdir = "output"
        os.makedirs(outdir, exist_ok=True)

        # Logga hela individ-tabellen med relevant status
        self.individuals.to_csv(os.path.join(outdir, "initial_state_individuals.csv"), index=True)

        # Logga hela jobb-tabellen på samma sätt (om du vill)
        self.jobs.to_csv(os.path.join(outdir, "initial_state_jobs.csv"), index=False)

    def analyze(self):
        """
        Returns extended statistics about the current world.
        """
        n_unique_individuals = len(self.matchings['individual_id'].unique()) if not self.matchings.empty else 0
        n_unique_jobs = len(self.matchings['job_id'].unique()) if not self.matchings.empty else 0

        stats = {
            "total_individuals": len(self.individuals),
            "individual_status_counts": self.individuals['status'].value_counts().to_dict(),
            "total_jobs": len(self.jobs),
            "matched_pairs": len(self.matchings),
            "unique_matched_individuals": n_unique_individuals,
            "unique_matched_jobs": n_unique_jobs,
            "unmatched_individuals_in_workforce": len(self.individuals[(self.individuals['status'] == 'unemployed') & (~self.individuals['individual_id'].isin(self.matchings['individual_id']) if not self.matchings.empty else True)]),
            "unmatched_jobs": self.jobs['individual_id'].isna().sum()
        }
        return stats

    def plot(
        self,
        layers=("municipalities",),
        municipal_codes_or_names=None,
        **kwargs  # fångar employers_gdf=..., individuals_gdf=..., etc
    ):
        """
        Wrapper that plots selected layers.
        Also supports point layers, e.g. employers_gdf, individuals_gdf.

        Example:
        world.plot(layers=("municipalities", "urban_areas"), individuals_gdf=world.individuals)
        """
        plot_selected_municipalities(
            self.geoworld,
            layers=layers,
            municipal_codes_or_names=municipal_codes_or_names,
            **kwargs
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
                handler(event)
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
        # Schedule first events, e.g. when all employees are supposed to quit
        employed_mask = self.individuals['status'] == 'employed'
        n_emp = employed_mask.sum()
        if n_emp > 0:
            durations = DAYS_PER_YEAR * self.draw_employment_duration(
                self.config['simulation']['avg_employment_duration'],
                self.config['simulation']['employment_duration_std'],
                size=n_emp
            )
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
        n_years = self.config['simulation'].get('n_years', 5)
        start_year = self.config['simulation'].get('start_year', 2024)
        start_month = self.config['simulation'].get('start_month', 1)  # 1-based, 1 = January

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

        # Sannolikhet för att gå till utbildning
        prop_edu = self.individuals.at[idx, 'propensity_start_education']
        if np.random.rand() < prop_edu:
            edu_event = Event(
                event.time + np.random.uniform(5, 40),  # dagar till utbildningsstart
                idx,
                'start_education',
                {
                    'education_type': 'broad',
                    'delta_chi': 0.8,
                    'delta_H': 0.3,
                    'duration': 0.7 * DAYS_PER_YEAR
                }
            )
            self.push_event(edu_event)
        else:
            # Börja söka nytt jobb
            t_search = event.time + DAYS_PER_YEAR * np.random.exponential(
                self.config['simulation']['job_search_interval'])
            search_event = Event(t_search, idx, 'start_job_search')
            self.push_event(search_event)

        self.event_logger.log_individual_event(self, event)

    def handle_start_job(self, event):
        idx = event.agent_id
        job_id = event.params['job_id']
        self.individuals.at[idx, 'status'] = 'employed'
        self.individuals.at[idx, 'job_id'] = job_id
        job_idx = self.jobs['job_id'] == job_id
        self.jobs.loc[job_idx, 'individual_id'] = idx

        self.event_logger.log_individual_event(self, event, extra={'job_id': job_id})

        # Internutbildning: propensity * arbetsgivarens chans
        job_row = self.jobs[self.jobs['job_id'] == job_id].iloc[0]
        n_employees = job_row['employer_size']
        prop_ind = self.individuals.at[idx, 'propensity_internal_training']
        P = prop_ind * self.employer_training_prob(n_employees)
        if np.random.rand() < P:
            t_training = event.time + np.random.uniform(0.05, 0.2) * DAYS_PER_YEAR
            training_event = Event(
                t_training,
                idx,
                'start_internal_training',
                {'delta_H': np.random.uniform(0.05, 0.15), 'delta_chi': np.random.uniform(0.01, 0.04)}
            )
            self.push_event(training_event)

        # Interna byten av arbetsuppgifter, kan ha lägre sannolikhet
        if np.random.rand() < 0.10:  # 10% chans, kan styras från config
            t_change = event.time + np.random.uniform(0.2, 0.8) * DAYS_PER_YEAR
            change_event = Event(
                t_change,
                idx,
                'internal_job_change',
                {'delta_xi': np.random.uniform(2, 7), 'delta_H': np.random.uniform(0.10, 0.25), 'delta_chi': np.random.uniform(0.01, 0.03)}
            )
            self.push_event(change_event)

        # Schemalägg när individen slutar detta jobb
        t_quit = event.time + DAYS_PER_YEAR * self.draw_employment_duration(
            self.config['simulation']['avg_employment_duration'],
            self.config['simulation']['employment_duration_std']
        )
        quit_event = Event(t_quit, idx, 'quit_job')
        self.push_event(quit_event)

    def handle_start_job_search(self, event):
        idx = event.agent_id
        df = self.individuals.loc[[idx]]
        matches = self.match_individuals_to_jobs(
            individuals=df,
            mode="interleaved_multilevel",
            alpha_chi=self.config['simulation']['alpha_chi'],
            alpha_xi=self.config['simulation']['alpha_xi'],
            alpha_geo=self.config['simulation']['alpha_geo'],
        )
        if not matches.empty:
            job_id = matches.iloc[0]['job_id']
            t_start = event.time
            start_event = Event(t_start, idx, 'start_job', {'job_id': job_id})
            self.push_event(start_event)
            self.event_logger.log_generic_event(event, data={"event_detail": "match_completed", "job_id": job_id})
        else:
            t_retry = event.time + DAYS_PER_YEAR * np.random.exponential(self.config['simulation']['job_search_interval'])
            retry_event = Event(t_retry, idx, 'start_job_search')
            self.push_event(retry_event)
            self.event_logger.log_generic_event(event, data={"event_detail": "match_failed"})

    def handle_start_education(self, event):
        idx = event.agent_id
        education_type = event.params.get('education_type', 'specialist')
        if education_type == 'specialist':
            self.individuals.at[idx, 'chi'] += event.params.get('delta_chi', 1.0)
            self.individuals.at[idx, 'H'] += event.params.get('delta_H', 0.1)
        elif education_type == 'broad':
            self.individuals.at[idx, 'H'] += event.params.get('delta_H', 0.5)
            self.individuals.at[idx, 'xi'] += event.params.get('delta_xi', 10)
        self.individuals.at[idx, 'status'] = 'in_education'
        self.event_logger.log_individual_event(self, event, extra={'education_type': education_type})
        # Schemalägg slut på utbildningen
        education_duration = event.params.get('duration', 1 * DAYS_PER_YEAR)
        end_event = Event(event.time + education_duration, idx, 'end_education', {'education_type': education_type})
        self.push_event(end_event)

    def handle_end_education(self, event):
        idx = event.agent_id
        self.individuals.at[idx, 'status'] = 'unemployed'
        self.event_logger.log_individual_event(self, event, extra={'event_detail': 'education_finished'})
        t_search = event.time + DAYS_PER_YEAR * np.random.exponential(self.config['simulation']['job_search_interval'])
        search_event = Event(t_search, idx, 'start_job_search')
        self.push_event(search_event)

    def handle_start_internal_training(self, event):
        idx = event.agent_id
        self.individuals.at[idx, 'H'] += event.params.get('delta_H', 0.2)
        self.individuals.at[idx, 'chi'] += event.params.get('delta_chi', 0.05)
        self.event_logger.log_individual_event(self, event, extra={'event_detail': 'start_internal_training'})
        # Ev. möjlighet till återkommande utbildning (rekursivt, med låg sannolikhet)
        if self.individuals.at[idx, 'status'] == 'employed' and np.random.rand() < 0.15:
            t_training = event.time + np.random.uniform(0.2, 0.8) * DAYS_PER_YEAR
            more_training = Event(
                t_training,
                idx,
                'start_internal_training',
                {'delta_H': np.random.uniform(0.03, 0.10), 'delta_chi': np.random.uniform(0.01, 0.02)}
            )
            self.push_event(more_training)

    def handle_internal_job_change(self, event):
        idx = event.agent_id
        self.individuals.at[idx, 'xi'] += event.params.get('delta_xi', 3)
        self.individuals.at[idx, 'H'] += event.params.get('delta_H', 0.3)
        self.individuals.at[idx, 'chi'] += event.params.get('delta_chi', 0.03)
        self.event_logger.log_individual_event(self, event, extra={'event_detail': 'internal_job_change'})

    def handle_career_break(self, event):
        idx = event.agent_id
        self.individuals.at[idx, 'status'] = 'career_break'
        self.individuals.at[idx, 'chi'] -= event.params.get('delta_chi', 0.05)
        self.individuals.at[idx, 'H'] -= event.params.get('delta_H', 0.02)
        self.event_logger.log_individual_event(self, event, extra={'event_detail': 'career_break'})
        break_duration = event.params.get('duration', 0.5 * DAYS_PER_YEAR)
        end_event = Event(event.time + break_duration, idx, 'start_job_search')
        self.push_event(end_event)

    def handle_new_month(self, event):
        year = event.params.get('year')
        month = event.params.get('month')
        self.event_logger.log_generic_event(event, data={"year": year, "month": month}, print_line=True)

    def handle_new_year(self, event):
        year = event.params.get('year')
        stats = self.analyze()
        employed = stats['individual_status_counts'].get('employed', 0)
        unemployed = stats['individual_status_counts'].get('unemployed', 0)
        matched = stats.get('matched_pairs', 0)
        unmatched_jobs = stats.get('unmatched_jobs', 0)
        self.event_logger.log_generic_event(event, data={
            "year": year,
            "employed": employed,
            "unemployed": unemployed,
            "matched": matched,
            "unmatched_jobs": unmatched_jobs
        }, print_line=True)

    def employer_training_prob(self, n_employees):
        tr_cfg = self.config['defaults']['employer']['training_prob_by_size']
        if n_employees < 10:
            return tr_cfg.get('small', 0.05)
        elif n_employees < 100:
            return tr_cfg.get('medium', 0.15)
        else:
            return tr_cfg.get('large', 0.40)

