# worm/world.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import time
import numpy as np
import pandas as pd
from worm.geography.geoworld import GeoWorld
from worm.plotting.plot_selected_municipalities import plot_selected_municipalities
from worm.matching import greedy_deso_matching, interleaved_multilevel_batch_matching

from worm.statistics.log import log
from worm.events import Event, EventQueue

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
        }

        # Event queue (AP8) – från scenario, eller tom DataFrame
        self.event_queue = EventQueue()
        self.current_time = 0  # Starttid i simuleringen, kan vara t.ex. dagar, månader, år

        # Output/resultat – samlas/uppdateras löpande
        self.matchings = pd.DataFrame()

        # Logging configuration
        self.log_to_console = self.config.get('simulation', {}).get('log_to_console', False)
        self.log_to_file = self.config.get('simulation', {}).get('log_to_file', True)
        self.logfile_path = self.config.get('simulation', {}).get('logfile_path', 'output/worm_simulation.log')
        self.logfile = open(self.logfile_path, "w") if self.log_to_file else None



    def draw_employment_duration(self, avg_employment_duration, employment_duration_std):
        """
        Returns a log-normally distributed employment duration with given mean and std.
        """
        mean = avg_employment_duration
        std = employment_duration_std

        sigma = np.sqrt(np.log(1 + (std / mean) ** 2))
        mu = np.log(mean) - 0.5 * sigma ** 2

        return np.random.lognormal(mean=mu, sigma=sigma)

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
            if handler:
                handler(event)
            else:
                print(f"Unknown event: {event.event_type}")
            # Logging/statistics can be added here

    def close(self):
        """ Shut down after simulation is done. Closes any open resources, e.g. log files.
        """
        if self.logfile:
            self.logfile.close()
        if self.log_to_console:
            elapsed = time.time() - self.wallclock_start
            print(f"[TIMER] {elapsed:8.2f}s | simulation_ended")

    def _init_events(self):
        # Schedule first events, e.g. when all employees are supposed to quit
        for idx, row in self.individuals[self.individuals['status'] == 'employed'].iterrows():
            t_quit = DAYS_PER_YEAR*self.draw_employment_duration(
                self.config['simulation']['avg_employment_duration'],
                self.config['simulation']['employment_duration_std']
            )
            event = Event(self.current_time + t_quit, idx, 'quit_job')
            self.event_queue.push(event)

        # Add new_month/new_year events if desired
        self.schedule_calendar_events()


    def log_event(self, event, *args):
        logline = f"{event.time:.2f}, {event.event_type}" + (", " if args else "") + ", ".join(map(str, args))
        # Always write to file if enabled
        if self.log_to_file and self.logfile:
            self.logfile.write(logline + "\n")
        # Print to console only for new_month/new_year (or whatever you choose)
        if self.log_to_console and event.event_type in {"new_month", "new_year"}:
            elapsed = time.time() - self.wallclock_start
            print(f"[TIMER] {elapsed:8.2f}s | {logline}")
            
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
        self.event_queue.push(Event(day, None, 'new_year', {'year': year}))

        for y in range(n_years):
            current_year = start_year + y
            months_in_year = list(range(1, 13))
            # Skip months before start month in first year
            if y == 0 and start_month > 1:
                months_in_year = list(range(start_month, 13))
            for current_month in months_in_year:
                self.event_queue.push(Event(day, None, 'new_month', {'year': current_year, 'month': current_month}))
                # Determine month length
                if current_month == 2 and is_leap_year(current_year):
                    days_in_month = 29
                else:
                    days_in_month = MONTH_LENGTHS[current_month - 1]
                day += days_in_month
            # Schedule new_year for next year (if not last year)
            if y < n_years - 1:
                next_year = current_year + 1
                self.event_queue.push(Event(day, None, 'new_year', {'year': next_year}))


    # Eventhandlers below

    def handle_start_job(self, event):
        idx = event.agent_id
        job_id = event.params['job_id']
        self.individuals.at[idx, 'status'] = 'employed'
        self.individuals.at[idx, 'job_id'] = job_id
        job_idx = self.jobs['job_id'] == job_id
        self.jobs.loc[job_idx, 'individual_id'] = idx

        self.log_event(event, idx, job_id)

        t_quit = event.time + DAYS_PER_YEAR*self.draw_employment_duration(
            self.config['simulation']['avg_employment_duration'],
            self.config['simulation']['employment_duration_std']
        )
        quit_event = Event(t_quit, idx, 'quit_job')
        self.event_queue.push(quit_event)

    def handle_start_job_search(self, event):
        idx = event.agent_id
        df = self.individuals.loc[[idx]]
        matches = self.match_individuals_to_jobs(
            individuals=df,
            mode="interleaved_multilevel",
            alpha_chi=self.config['simulation']['alpha_chi'],
            alpha_xi=self.config['simulation']['alpha_xi'],
            alpha_geo=self.config['simulation']['alpha_geo'],
            # ... andra parametrar
        )
        if not matches.empty:
            job_id = matches.iloc[0]['job_id']
            # Schedule start_job
            t_start = event.time
            start_event = Event(t_start, idx, 'start_job', {'job_id': job_id})
            self.event_queue.push(start_event)
            self.log_event(event, idx, "match_completed", f"job {job_id}")
        else:
            # New search after interval
            t_retry = event.time + DAYS_PER_YEAR*np.random.exponential(self.config['simulation']['job_search_interval'])
            retry_event = Event(t_retry, idx, 'start_job_search')
            self.event_queue.push(retry_event)
            self.log_event(event, idx, "match_failed")

    def handle_quit_job(self, event):
        idx = event.agent_id
        # Set individual's status to unemployed
        self.individuals.at[idx, 'status'] = 'unemployed'
        # Get job_id and vacate the job
        job_id = self.individuals.at[idx, 'job_id']
        if pd.notna(job_id):
            self.jobs.loc[self.jobs['job_id'] == job_id, 'individual_id'] = np.nan
            self.individuals.at[idx, 'job_id'] = np.nan
        # Schedule new job search
        t_search = event.time + DAYS_PER_YEAR*np.random.exponential(self.config['simulation']['job_search_interval'])
        search_event = Event(t_search, idx, 'start_job_search')
        self.event_queue.push(search_event)

        self.log_event(event, idx)

    def handle_new_month(self, event):
        year = event.params.get('year')
        month = event.params.get('month')
        self.log_event(event, f"{year}-{month:02d}")

    def handle_new_year(self, event):
        year = event.params.get('year')
        stats = self.analyze()
        employed = stats['individual_status_counts'].get('employed', 0)
        unemployed = stats['individual_status_counts'].get('unemployed', 0)
        matched = stats.get('matched_pairs', 0)
        unmatched_jobs = stats.get('unmatched_jobs', 0)

        # Example log format:
        # <time>, new_year, <year>, employed <count>, unemployed <count>, matched <count>, unmatched_jobs <count>
        self.log_event(
            event,
            year,
            f"employed {employed}",
            f"unemployed {unemployed}",
            f"matched {matched}",
            f"unmatched_jobs {unmatched_jobs}"
        )
