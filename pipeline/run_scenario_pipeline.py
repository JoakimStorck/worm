# scripts/run_scenario_pipeline.py

import sys
import os
import sqlite3
import yaml
import pandas as pd
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.configreader import ConfigReader
from core.geography.geoworld import GeoWorld
from core.scenariobuilder import ScenarioBuilder
from core.world import World
from core.statistics.matching_stats import compute_matching_statistics, compute_commuting_statistics 
from core.log import log, save_run_output, log_lines
from core.analysis.scenario_result import ScenarioResult
from core.visualization.occupation_space_panel import plot_occupation_space_panel
from core.visualization.map_panel import plot_selected_municipalities_bokeh_panel


# === 1. Ladda scenario (YAML) ===
def load_scenario(yaml_path):
    print(f"Laddar scenario från: {yaml_path}")
    with open(yaml_path, "r", encoding="utf-8") as f:
        scenario = yaml.safe_load(f)
    print("Scenario inläst, nycklar:", list(scenario.keys()))
    return scenario

# === 2. Preprocessing och bygg world ===
def build_world_from_scenario(scenario, db_path):
    conn = sqlite3.connect(db_path)
    cfg = ConfigReader(scenario, conn)
    cfg.validate_scenario(strict=True)
    geoworld = GeoWorld(db_path)
    builder = ScenarioBuilder(scenario, conn, cfg, geoworld=geoworld)
    individuals, jobs, employers, events = builder.generate()
    world = World(
        db_path,
        config=scenario,
        individuals=individuals,
        jobs=jobs,
        employers=employers,
        events=events
    )
    return world, geoworld

# === 3. Initial analys/loggning/statistik före matching ===
def log_pre_matching(world, scenario_path):
    log("Scenario:", scenario_path)
    log("Statistics BEFORE batch matching:", world.analyze())

# === 4. Matching och update av world ===
def run_batch_matching(world, config):
    matchings = world.match_individuals_to_jobs(
        mode="interleaved_multilevel",
        alpha_chi=config.get('alpha_chi', 5.0),
        alpha_xi=config.get('alpha_xi', 5.0),
        alpha_geo=config.get('alpha_geo', 1.0),
    )
    world.update_after_matching(matchings=matchings)
    log("Statistics AFTER batch matching (t=0):", world.analyze())
    return matchings

# === 5. Statistik efter matching ===
def compute_and_save_stats(world, scenario, matchings):
    match_stats = compute_matching_statistics(world.matchings)
    commuting_stats = compute_commuting_statistics(
        world.matchings, world.individuals, world.jobs
    )
    scenario_name = scenario.get("scenario_name", "scenario")
    save_run_output(world.matchings, match_stats, commuting_stats, scenario_name)
    return match_stats, commuting_stats

# === 6. Event-driven simulering ===
def run_event_simulation(world):
    log(f"Starting event-driven simulation, simulation_end_time = {world.simulation_end_time}")
    world.simulate()
    log("Statistics AFTER simulation:", world.analyze())

# === 7. Extrahera snapshot/utdata för analys och visualisering ===
def get_snapshot(world):
    # Samla dataframes för individer, jobb, pathways mm
    return {
        "individuals": world.individuals.copy(),
        "jobs": world.jobs.copy(),
        "employers": world.employers.copy(),
        "eventlog": getattr(world, "eventlog", None)
    }


# === 9. Interaktiv visualisering med Bokeh (occupation space + karta) ===

def show_interactive_dashboard(result: ScenarioResult, geoworld=None, config=None):
    from core.visualization.map_panel import plot_selected_municipalities_bokeh_panel
    from core.visualization.occupation_space_panel import plot_occupation_space_panel
    from bokeh.layouts import row
    from bokeh.plotting import show, output_file

    # 1. Occupation space-panel (all data via ScenarioResult)
    p_occ, indiv_source = plot_occupation_space_panel(result)

    # 2. Karta-panel – använd samma indiv_source!
    if (geoworld is not None) and (config is not None):
        muni_config = config.get("municipalities", [])
        if isinstance(muni_config, list):
            muni_codes = [str(m['municipal_code']) if isinstance(m, dict) else str(m) for m in muni_config]
        else:
            muni_codes = [str(muni_config)]
        muni_gdf = geoworld.municipalities

        # Hämta arbetsgivare (från ScenarioResult, inte world)
        try:
            employers_gdf = result.get_employers()
        except AttributeError:
            employers_gdf = result.employers if hasattr(result, "employers") else None

        layers = ["municipalities", "urban_areas", "business_zones", "deso_zones", "employers", "individuals"]
        gdf_layers = {
            "urban_areas": geoworld.urban_areas,
            "business_zones": geoworld.business_zones,
            "deso": geoworld.deso_zones,
            # etc.
        }

        p_map = plot_selected_municipalities_bokeh_panel(
            geoworld.municipalities,
            muni_codes,
            result=result,
            layers=layers,
            gdf_layers=gdf_layers
        )
    else:
        from bokeh.plotting import figure
        p_map = figure(title="Ingen karta", width=500, height=700)

    layout = row(p_occ, p_map)
    output_file("html/dashboard_linked.html")
    show(layout)


# === 10. Main pipeline ===
def main():
    scenario_path = "scenarios/falun_baseline.yml"
    db_path = "data/worm.sqlite3"

    # 1. Ladda scenario
    scenario = load_scenario(scenario_path)

    # 2. Bygg world från scenario
    world, geoworld = build_world_from_scenario(scenario, db_path)

    # 3. Logga statistik före matching
    log_pre_matching(world, scenario_path)

    # 4. Kör matchning och uppdatering
    matchings = run_batch_matching(world, scenario)

    # 5. Beräkna och spara statistik
    compute_and_save_stats(world, scenario, matchings)

    # 6. Kör event-driven simulering
    run_event_simulation(world)

    # 7. Extrahera snapshot/resultat för analys/viz
    snapshot = get_snapshot(world)
    result = ScenarioResult(snapshot)

    # 8. Visa interaktiv dashboard (Bokeh)
    show_interactive_dashboard(result, geoworld, scenario)

if __name__ == "__main__":
    main()
