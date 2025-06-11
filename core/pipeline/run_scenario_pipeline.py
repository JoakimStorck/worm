# scripts/run_scenario_modern.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


import sys
from pathlib import Path
import yaml
import pandas as pd

# === 1. Ladda scenario ===
def load_scenario(yaml_path):
    with open(yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# === 2. Preprocessing och bygg world ===
def build_world_from_scenario(scenario, db_path):
    # Din befintliga pipeline här: 
    # - skapa GeoWorld, 
    # - skapa individer/arbetsgivare/jobb via ScenarioBuilder,
    # - lagra i World-objekt
    from geography.geoworld import GeoWorld
    from core.scenariobuilder import ScenarioBuilder
    from core.world import World

    geoworld = GeoWorld(db_path)
    scenbuilder = ScenarioBuilder(scenario, conn=None, configreader=None) # Fyll på med rätt init!
    # Skapa population och jobb etc
    indiv_df, jobs_df, employers_df = scenbuilder.generate() # Pseudokod, anpassa till din API
    # Bygg world
    world = World(
        individuals=indiv_df,
        jobs=jobs_df,
        employers=employers_df,
        geoworld=geoworld
    )
    return world

# === 3. Kör matchning/simulering (minimal version) ===
def run_simulation(world):
    from core.matching import match
    from core.events import run_events

    # Initial matchning
    match(world) # Modifierar world in-place
    # Minimal event/sim
    run_events(world) # Modifierar world och loggar event
    return world

# === 4. Extrahera snapshot/utdata för analys och visualisering ===
def get_snapshot(world):
    # Samla dataframes för individer, jobb, pathways mm
    return {
        "individuals": world.individuals.copy(),
        "jobs": world.jobs.copy(),
        "employers": world.employers.copy(),
        "eventlog": world.eventlog.copy() if hasattr(world, "eventlog") else None
    }

# === 5. API för analys/visualisering (minimal) ===
class ScenarioResult:
    def __init__(self, snapshot):
        self.individuals = snapshot["individuals"]
        self.jobs = snapshot["jobs"]
        self.eventlog = snapshot["eventlog"]
        # Kan lägga till metoder för pathways, entropi, grupper etc

    def get_individuals(self, filter_func=None):
        df = self.individuals
        if filter_func:
            df = df[df.apply(filter_func, axis=1)]
        return df

    def get_jobs(self):
        return self.jobs

    def get_eventlog(self):
        return self.eventlog

# === 6. Visualisering: enkel occupation space + karta ===
def show_interactive_dashboard(result: ScenarioResult):
    from bokeh.plotting import figure, show, output_file
    from bokeh.models import ColumnDataSource, HoverTool
    from bokeh.layouts import gridplot, column

    indiv = result.get_individuals()
    jobs = result.get_jobs()

    # Kartesiska coordinates för occupation space
    indiv["x_occ"] = indiv["chi"] * np.cos(indiv["xi"])
    indiv["y_occ"] = indiv["chi"] * np.sin(indiv["xi"])
    jobs["x_occ"] = jobs["chi"] * np.cos(jobs["xi"])
    jobs["y_occ"] = jobs["chi"] * np.sin(jobs["xi"])

    # Karta – dummy (anpassa med riktiga koordinater!)
    indiv["x_map"] = indiv.get("x_map", indiv["x_occ"] + 5)
    indiv["y_map"] = indiv.get("y_map", indiv["y_occ"] + 5)

    indiv_source = ColumnDataSource(indiv)
    job_source = ColumnDataSource(jobs)

    # Occupation space
    p_occ = figure(title="Occupation space", width=400, height=400, match_aspect=True, tools="lasso_select,box_select,reset,pan,wheel_zoom")
    p_occ.circle('x_occ', 'y_occ', source=indiv_source, color="red", alpha=0.6, size=8, legend_label="Individer", selection_color="orange")
    p_occ.circle('x_occ', 'y_occ', source=job_source, color="blue", alpha=0.3, size=5, legend_label="Jobb", selection_color="green")

    # Karta
    p_map = figure(title="Karta", width=400, height=400, match_aspect=True, tools="lasso_select,box_select,reset,pan,wheel_zoom")
    p_map.circle('x_map', 'y_map', source=indiv_source, color="red", alpha=0.6, size=8, selection_color="orange")

    layout = column(gridplot([[p_occ, p_map]]))
    output_file("first_slice_dashboard.html")
    show(layout)

# === 7. CLI/main – kör pipelinen för ett scenario ===
def main():
    # Sätt paths
    scenario_path = "scenarios/falun_baseline.yml"
    db_path = "data/worm.sqlite3"

    # 1. Ladda scenario
    scenario = load_scenario(scenario_path)

    # 2. Bygg world
    world = build_world_from_scenario(scenario, db_path)

    # 3. Kör simulering
    world = run_simulation(world)

    # 4. Hämta snapshot/resultat
    snapshot = get_snapshot(world)
    result = ScenarioResult(snapshot)

    # 5. Visa dashboard
    show_interactive_dashboard(result)

if __name__ == "__main__":
    main()
