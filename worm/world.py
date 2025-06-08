# worm/world.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from worm.geography.geoworld import GeoWorld
from worm.plotting.plot_selected_municipalities import plot_selected_municipalities
from worm.matching import greedy_deso_matching
from worm.statistics.log import log

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
        - mode="deso_interleaved": Interleaverad multilevel batchmatchning
        (lägg till fler metoder vid behov)
        """

        # Skapa en kopia av arbetskraften (arbetslösa individer)
        workforce = self.individuals[self.individuals['status'] == 'unemployed'].copy()

        if mode == "deso_greedy":
            from worm.matching import greedy_deso_matching
            self.matchings = greedy_deso_matching(
                individuals=workforce,
                jobs=self.jobs,
                alpha_chi=kwargs.get("alpha_chi", 5.0),
                alpha_xi=kwargs.get("alpha_xi", 5.0),
                alpha_geo=kwargs.get("alpha_geo", 1.0),
                batch_size=kwargs.get("batch_size", 1000),
                verbose=kwargs.get("verbose", True)
            )

        elif mode == "deso_interleaved":
            from worm.matching import interleaved_multilevel_batch_matching
            matchings = interleaved_multilevel_batch_matching(
                individuals=workforce,
                jobs=self.jobs,
                batch_frac_deso=kwargs.get("batch_frac_deso", 0.20),
                batch_frac_muni=kwargs.get("batch_frac_muni", 0.10),
                batch_frac_global=kwargs.get("batch_frac_global", 0.05),
                alpha_chi=kwargs.get("alpha_chi", 5.0),
                alpha_xi=kwargs.get("alpha_xi", 5.0),
                alpha_geo=kwargs.get("alpha_geo", 1.0),
                min_batch=kwargs.get("min_batch", 10),
                verbose=kwargs.get("verbose", True)
            )
            self.matchings = matchings

            # (Optional) Save unmatched for further processing
            # If you want to track remaining individuals/jobs (not needed om du inte bryr dig)
            # self.remaining_unmatched_individuals = ...
            # self.remaining_unmatched_jobs = ...

        else:
            raise ValueError(f"Unknown matching mode: {mode}")

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
        Returnerar utökad statistik över nuvarande värld.
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
            "unmatched_jobs": len(self.jobs[~self.jobs['job_id'].isin(self.matchings['job_id'])]) if not self.matchings.empty else len(self.jobs),
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
    log("Laddat:", world.analyze())
    world.plot(layers=("municipalities", "urban_areas"))
    world.match_individuals_to_jobs()
    log("Efter matchning:", world.analyze())
    # ...eller: ladda in från scenario
    # from worm.scenario_builder import ScenarioBuilder
    # builder = ScenarioBuilder("scenarios/scenario_falun_baseline.yml", world.geoworld)
    # individuals, jobs, employers = builder.generate()
    # world.set_scenario_data(individuals, jobs, employers)
    # world.analyze()
