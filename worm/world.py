# worm/world.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from worm.geography.geoworld import GeoWorld
from worm.plotting.plot_selected_municipalities import plot_selected_municipalities

class World:
    def __init__(self, db_path, geoworld=None, scope=None, workers=None, jobs=None, employers=None, events=None):
        """
        World samlar all kärndata och hanterar simulering för valfri region eller scenario.
        - scope: kommun- eller regionkod (str, lista eller None för allt).
        - workers, jobs, employers: DataFrames från ScenarioBuilder eller genererade direkt
        - events: event queue (t.ex. från ScenarioBuilder/scenariofil)
        """
        self.db_path = db_path
        self.scope = scope  # T.ex. ["2081", "2086"] för Falun+Borlänge, None för hela landet

        # Geografi (navet för spatiala frågor)
        self.geoworld = geoworld if geoworld is not None else GeoWorld(db_path)

        # Agentdata – läs från scenario om det finns, annars från db (tom sim = ingen agentdata)
        self.workers = workers if workers is not None else self.load_workers_df()
        self.jobs = jobs if jobs is not None else self.load_jobs_df()
        self.employers = employers if employers is not None else self.load_employers_df()

        # Event queue (AP8) – från scenario, eller tom DataFrame
        self.events = events if events is not None else pd.DataFrame(columns=["time", "agent_id", "event_type", "params"])
        self.current_time = 0  # Starttid i simuleringen, kan vara t.ex. dagar, månader, år

        # Output/resultat – samlas/uppdateras löpande
        self.matchings = pd.DataFrame()

    def load_workers_df(self):
        query = "SELECT * FROM workers"
        if self.scope:
            codes = ','.join([f"'{c}'" for c in self.scope]) if isinstance(self.scope, (list, tuple)) else f"'{self.scope}'"
            query += f" WHERE municipal_code IN ({codes})"
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql(query, conn)
        conn.close()
        return df

    def load_jobs_df(self):
        query = "SELECT * FROM jobs"
        if self.scope:
            codes = ','.join([f"'{c}'" for c in self.scope]) if isinstance(self.scope, (list, tuple)) else f"'{self.scope}'"
            query += f" WHERE municipal_code IN ({codes})"
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql(query, conn)
        conn.close()
        return df

    def load_employers_df(self):
        query = "SELECT * FROM employers"
        if self.scope:
            codes = ','.join([f"'{c}'" for c in self.scope]) if isinstance(self.scope, (list, tuple)) else f"'{self.scope}'"
            query += f" WHERE municipal_code IN ({codes})"
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql(query, conn)
        conn.close()
        return df

    def set_scenario_data(self, workers=None, jobs=None, employers=None, events=None):
        """
        Ersätt agent- och eventdata med data från ScenarioBuilder.
        """
        if workers is not None:
            self.workers = workers
        if jobs is not None:
            self.jobs = jobs
        if employers is not None:
            self.employers = employers
        if events is not None:
            self.events = events

    def match_workers_to_jobs(self, mode="utility"):
        """
        Batch-matchning mellan workers och jobs. 
        Byt ut logiken till utility/random/geografisk efter behov.
        """
        n = min(len(self.workers), len(self.jobs))
        matched_workers = self.workers.sample(n).reset_index(drop=True)
        matched_jobs = self.jobs.sample(n).reset_index(drop=True)
        self.matchings = pd.DataFrame({
            "worker_id": matched_workers["worker_id"],
            "job_id": matched_jobs["job_id"],
            # Lägg till fler attribut/statistik om du vill
        })
        return self.matchings

    def add_event(self, time, agent_id, event_type, params=None):
        """
        Lägg till en rad i event queue.
        """
        new_event = {"time": time, "agent_id": agent_id, "event_type": event_type, "params": params}
        self.events = pd.concat([self.events, pd.DataFrame([new_event])], ignore_index=True)

    def process_events(self, until_time=None):
        """
        Kör igenom event queue fram till given tidpunkt.
        """
        if self.events.empty:
            return
        to_process = self.events if until_time is None else self.events[self.events["time"] <= until_time]
        for _, event in to_process.iterrows():
            # Här skriver du logik för vad som händer vid varje event
            pass
        # Efter körning: ta bort processade events (om du vill)
        if until_time is not None:
            self.events = self.events[self.events["time"] > until_time]

    def analyze(self):
        """
        Sammanställ och returnera grundläggande statistik.
        Utbyggs successivt efter behov.
        """
        stats = {
            "total_workers": len(self.workers),
            "total_jobs": len(self.jobs),
            "matched": len(self.matchings),
            # ... fyll på!
        }
        return stats


    def plot(
        self,
        layers=("municipalities",),
        municipal_codes_or_names=None,
        **kwargs  # fångar employers_gdf=..., workers_gdf=..., etc
    ):
        """
        Wrapper som plottar valda lager.
        Stödjer även punktlager, t.ex. employers_gdf, workers_gdf.

        Exempel:
            world.plot(
                layers=("municipalities", "urban_areas", "employers"),
                municipal_codes_or_names=["2080"],
                employers_gdf=employers
            )
        """
        plot_selected_municipalities(
            self.geoworld,
            codes_or_names=municipal_codes_or_names if municipal_codes_or_names else [],
            layers=layers,
            **kwargs
        )



# --- Exempel på användning ---
if __name__ == "__main__":
    # Antingen "klassisk": läs data från db (scope kan vara kommunkod, t.ex. Falun)
    world = World("data/worm.sqlite3", scope=["2081", "2086"])
    print("Laddat:", world.analyze())
    world.plot(layers=("municipalities", "urban_areas"))
    world.match_workers_to_jobs()
    print("Efter matchning:", world.analyze())
    # ...eller: ladda in från scenario
    # from worm.scenario_builder import ScenarioBuilder
    # builder = ScenarioBuilder("scenarios/scenario_falun_baseline.yml", world.geoworld)
    # workers, jobs, employers = builder.generate()
    # world.set_scenario_data(workers, jobs, employers)
    # world.analyze()
