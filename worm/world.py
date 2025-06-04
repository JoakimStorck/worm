# worm/world.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


import pandas as pd
from worm.geography.geoworld import GeoWorld

class World:
    def __init__(self, db_path, scope=None):
        """
        World samlar all kärndata och hanterar simulering för valfri region.
        scope: kommun- eller regionkod (str, lista eller None för allt).
        """
        self.db_path = db_path
        self.scope = scope  # T.ex. ["2081", "2086"] för Falun+Borlänge, None för hela landet

        # Geografi (navet för spatiala frågor)
        self.geoworld = GeoWorld(db_path)

        # DataFrames för alla agenter/entiteter (batch, snabbt, skalbart)
        self.workers = self.load_workers_df()
        self.jobs = self.load_jobs_df()
        self.employers = self.load_employers_df()

        # Event queue (AP8) – tomt i början, men grunden är lagd
        self.events = pd.DataFrame(columns=["time", "agent_id", "event_type", "params"])
        self.current_time = 0  # Starttid i simuleringen, kan vara t.ex. dagar, månader...

        # Output/resultat – samlas/uppdateras löpande
        self.matchings = pd.DataFrame()

    def load_workers_df(self):
        # Här skriver du effektiv SQL till DataFrame, gärna scope-filtrerat
        query = "SELECT * FROM workers"
        if self.scope:
            # Antag att workers har kolumn 'municipal_code'
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

    def match_workers_to_jobs(self, mode="utility"):
        """
        Batch-matchning mellan workers och jobs. 
        Byt ut logiken till utility/random/geografisk efter behov.
        """
        # Stub/logik – byt till din matchningsfunktion!
        n = min(len(self.workers), len(self.jobs))
        matched_workers = self.workers.sample(n).reset_index(drop=True)
        matched_jobs = self.jobs.sample(n).reset_index(drop=True)
        self.matchings = pd.DataFrame({
            "worker_id": matched_workers["worker_id"],
            "job_id": matched_jobs["job_id"],
            # Fler attribut/statistik kan fyllas på här
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
        (Stub – utbyggs med din eventlogik per event_type!)
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

    def plot(self, layers=("municipalities",)):
        """
        Enkel wrapper för att plotta karta med GeoWorld och overlay.
        """
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 10))
        for layer in layers:
            gdf = getattr(self.geoworld, layer)
            gdf.plot(ax=ax, alpha=0.6, edgecolor="gray", linewidth=0.5, label=layer)
        ax.set_aspect("equal")
        ax.axis("off")
        plt.legend()
        plt.tight_layout()
        plt.show()

# Exempel på användning:
if __name__ == "__main__":
    world = World("data/worm.sqlite3", scope=["2081", "2086"])  # Falun+Borlänge
    print("Laddat:", world.analyze())
    world.plot(layers=("municipalities", "urban_areas"))
    world.match_workers_to_jobs()
    print("Efter matchning:", world.analyze())
    # Lägg till ett event:
    world.add_event(time=1, agent_id=42, event_type="job_change", params={"new_job_id": 17})
    print("Event queue:", world.events.head())
