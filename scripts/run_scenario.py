# scripts/run_scenario.py
"""
Run a WORM scenario: initializes the agent population and labor market,
performs initial batch matching of the workforce, then runs the event-driven
simulation. Collects statistics and visualizes results.

1. Reads scenario and config from YAML.
2. Initializes database, geography, and agent population via ScenarioBuilder.
3. Performs initial batch matching (t=0) so that all matchable individuals have job status.
4. Runs the event-driven simulation.
5. Collects statistics and visualizes output.
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import sqlite3
import yaml
import geopandas as gpd

from worm.configreader import ConfigReader
from worm.geography.geoworld import GeoWorld
from worm.scenariobuilder import ScenarioBuilder
from worm.world import World
from worm.statistics.matching_stats import compute_matching_statistics, compute_commuting_statistics 
from worm.statistics.log import log, save_run_output, log_lines

def load_config(config_path):
    """Load YAML configuration as Python dict."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

if __name__ == "__main__":
    # --- 1. Define paths and load config ---
    db_path = "data/worm.sqlite3"
    scenario_path = "scenarios/falun_baseline.yml"

    config = load_config(scenario_path)

    # --- 2. Initialize database, config, and scenario environment ---
    conn = sqlite3.connect(db_path)
    cfg = ConfigReader(config, conn)
    geoworld = GeoWorld(db_path)
    builder = ScenarioBuilder(config, conn, cfg, geoworld=geoworld)

    # --- 3. Generate agent population, employers, and jobs from scenario ---
    individuals, jobs, employers, events = builder.generate()

    # --- 4. Create World object (no matching performed yet) ---
    world = World(
        db_path,
        config=config,
        individuals=individuals,
        jobs=jobs,
        employers=employers,
        events=events
    )

    # --- 5. Log and show statistics BEFORE batch matching ---
    log("Scenario:", scenario_path)
    log("Statistics BEFORE batch matching:", world.analyze())

    # --- 6. Initial batch matching of all unemployed individuals to available jobs (t=0) ---
    #    (This represents the labor market at simulation start.)
    #    The matching uses utility in occupation and geographic space.
    matchings = world.match_individuals_to_jobs(
        mode="interleaved_multilevel",
        alpha_chi=config.get('alpha_chi', 5.0),
        alpha_xi=config.get('alpha_xi', 5.0),
        alpha_geo=config.get('alpha_geo', 1.0),
        # Other batch parameters can be added here
    )
    world.update_after_matching(matchings=matchings)
    log("Statistics AFTER batch matching (t=0):", world.analyze())

    # --- 7. (Optional) Compute and save statistics for batch matching ---
    match_stats = compute_matching_statistics(world.matchings)
    commuting_stats = compute_commuting_statistics(world.matchings, world.individuals, world.jobs)

    # --- 8. Run event-driven simulation ---
    log("Starting event-driven simulation ...")
    world.simulate()
    log("Statistics AFTER simulation:", world.analyze())

    # --- 9. (Optional) Save and summarize final statistics ---
    scenario_name = config.get("scenario_name", "scenario")
    save_run_output(world.matchings, match_stats, commuting_stats, log_lines, scenario_name)

    # --- 10. Visualize results for selected municipalities ---
    municipalities = config.get("municipalities", [])

    employers_gdf = gpd.GeoDataFrame(
        employers,
        geometry=gpd.points_from_xy(employers["x"], employers["y"]),
        crs="EPSG:3006"  # Adjust CRS if necessary!
    )
    individuals_gdf = gpd.GeoDataFrame(
        individuals,
        geometry=gpd.points_from_xy(individuals["x"], individuals["y"]),
        crs="EPSG:3006"
    )

    world.plot(
        municipal_codes_or_names=municipalities,
        layers=("municipalities", "urban_areas", "business_zones", "employers", "individuals"),
        employers_gdf=employers_gdf,
        individuals_gdf=individuals_gdf,
    )

    world.close()