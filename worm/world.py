# worm/world.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from worm.geography.geoworld import GeoWorld
from worm.plotting.plot_selected_municipalities import plot_selected_municipalities
from worm.matching import greedy_deso_matching

class World:
    def __init__(self, db_path, geoworld=None, scope=None, individuals=None, jobs=None, employers=None, events=None):
        """
        World samlar all kärndata och hanterar simulering för valfri region eller scenario.
        Om DataFrames anges (individuals, jobs, employers) används de direkt – annars blir de tomma.
        """
        self.db_path = db_path
        self.scope = scope

        self.geoworld = geoworld if geoworld is not None else GeoWorld(db_path)

        # Använd bara explicit skickade DataFrames, annars skapa tomma
        self.individuals = individuals if individuals is not None else pd.DataFrame()
        self.jobs = jobs if jobs is not None else pd.DataFrame()
        self.employers = employers if employers is not None else pd.DataFrame()
        self.events = events if events is not None else pd.DataFrame(columns=["time", "agent_id", "event_type", "params"])
        self.current_time = 0

        self.matchings = pd.DataFrame()

        # Event queue (AP8) – från scenario, eller tom DataFrame
        self.events = events if events is not None else pd.DataFrame(columns=["time", "agent_id", "event_type", "params"])
        self.current_time = 0  # Starttid i simuleringen, kan vara t.ex. dagar, månader, år

        # Output/resultat – samlas/uppdateras löpande
        self.matchings = pd.DataFrame()

    def set_scenario_data(self, individuals=None, jobs=None, employers=None, events=None):
        """
        Ersätt agent- och eventdata med data från ScenarioBuilder.
        """
        if individuals is not None:
            self.individuals = individuals
        if jobs is not None:
            self.jobs = jobs
        if employers is not None:
            self.employers = employers
        if events is not None:
            self.events = events

    def match_individuals_to_jobs(self, mode="deso_greedy", **kwargs):
        """
        Matchar individer till jobb enligt valt läge.
        Stödjer nu:
        - mode="deso_greedy": Hierarkisk DeSO-matchning
        (lägg till fler metoder vid behov)
        """

        self.matchings = greedy_deso_matching(
            individuals=self.individuals,
            jobs=self.jobs,
            alpha=1.0,           # eller vad du vill
            batch_size=1000,     # kan användas i optimeringar senare
            verbose=True
        )


    def update_after_matching(self):
        """
        Uppdaterar både individer och jobb efter matchning:
        - Sätter status och job_id på individer som fått jobb
        - Sätter individual_id på jobb som blivit tillsatta
        Kräver att self.matchings innehåller 'individual_id' och 'job_id'
        """
        matchings = self.matchings

        # Uppdatera individer
        matched = matchings.set_index('individual_id')['job_id']
        idx = self.individuals['individual_id'].isin(matched.index)
        self.individuals.loc[idx, 'status'] = 'employed'
        self.individuals.loc[idx, 'job_id'] = self.individuals.loc[idx, 'individual_id'].map(matched)

        # Uppdatera jobb
        # Förbered lookup: job_id → individual_id
        job_to_ind = matchings.set_index('job_id')['individual_id']
        job_idx = self.jobs['job_id'].isin(job_to_ind.index)
        self.jobs.loc[job_idx, 'individual_id'] = self.jobs.loc[job_idx, 'job_id'].map(job_to_ind)

    def analyze(self):
        """
        Returnerar enkel statistik över nuvarande värld.
        """
        stats = {
            "total_individuals": len(self.individuals),
            "total_jobs": len(self.jobs),
            "matched": len(self.matchings),
        }
        return stats

    def plot(
        self,
        layers=("municipalities",),
        municipal_codes_or_names=None,
        **kwargs  # fångar employers_gdf=..., individuals_gdf=..., etc
    ):
        """
        Wrapper som plottar valda lager.
        Stödjer även punktlager, t.ex. employers_gdf, individuals_gdf.

        Exempel:
        world.plot(layers=("municipalities", "urban_areas"), individuals_gdf=world.individuals)
        """
        plot_selected_municipalities(
            self.geoworld,
            layers=layers,
            municipal_codes_or_names=municipal_codes_or_names,
            **kwargs
        )

# Test/demo (kan tas bort vid import)
if __name__ == "__main__":
    # Exempel
    db_path = "data/example.db"
    world = World(db_path)
    print("Laddat:", world.analyze())
    world.plot(layers=("municipalities", "urban_areas"))
    world.match_individuals_to_jobs()
    print("Efter matchning:", world.analyze())
    # ...eller: ladda in från scenario
    # from worm.scenario_builder import ScenarioBuilder
    # builder = ScenarioBuilder("scenarios/scenario_falun_baseline.yml", world.geoworld)
    # individuals, jobs, employers = builder.generate()
    # world.set_scenario_data(individuals, jobs, employers)
    # world.analyze()
