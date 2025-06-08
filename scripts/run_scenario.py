# scripts/run_scenario.py

import sys
import os
import sqlite3
import yaml

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worm.configreader import ConfigReader
from worm.geography.geoworld import GeoWorld
from worm.scenariobuilder import ScenarioBuilder
from worm.world import World

def load_config(config_path):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

if __name__ == "__main__":
    db_path = "data/worm.sqlite3"
    scenario_path = "scenarios/falun_baseline.yml"

    # Ladda config
    config = load_config(scenario_path)

    # Initiera databasanslutning
    conn = sqlite3.connect(db_path)

    # Initiera ConfigReader
    cfg = ConfigReader(config, conn)

    # Initiera GeoWorld
    geoworld = GeoWorld(db_path)
    
    # Initiera ScenarioBuilder
    builder = ScenarioBuilder(config, conn, cfg, geoworld=geoworld)

    # Generera scenario-agentdata (individuals, jobs, employers, events...)
    individuals, jobs, employers, events = builder.generate()

    # print(f"Antal genererade arbetsgivare: {len(employers)}")
    # print("\nTopp 10 största arbetsgivare (storlek, SNI, zon):")
    # print(employers.nlargest(10, "size")[["size", "sni_code", "layer", "zone_code"]])
    # print("\nTopp 10 SNI-koder (arbetsgivare):")
    # print(employers["sni_code"].value_counts().head(10))

    # Skapa World och injicera scenariodata
    world = World(
        db_path,
        individuals=individuals,
        jobs=jobs,
        employers=employers,
        events=events
    )

    # Kör analys och visualisering
    print("Scenario:", scenario_path)
    print("Statistik före matchning:", world.analyze())

    # Matcha individer till jobb (optimal assignment)
    world.match_individuals_to_jobs(mode="deso_greedy", alpha=1.0, batch_size=1000)
    world.update_after_matching()
    print("Efter matchning:", world.analyze())

    from worm.statistics.matching_stats import compute_matching_statistics

    # Efter att matchnings-DataFrame (matchings) är färdig
    stats = compute_matching_statistics(world.matchings)
    print(stats)

    # Hämta urval från scenario:
    municipalities = config["municipalities"]

    import geopandas as gpd

    # Om dina DataFrames heter employers och individuals:
    employers_gdf = gpd.GeoDataFrame(
        employers,
        geometry=gpd.points_from_xy(employers["x"], employers["y"]),
        crs="EPSG:3006"  # Justera om du har annat CRS!
    )

    individuals_gdf = gpd.GeoDataFrame(
        individuals,
        geometry=gpd.points_from_xy(individuals["x"], individuals["y"]),
        crs="EPSG:3006"
    )

    # Nu kan du plotta!
    world.plot(
        municipal_codes_or_names=["2080"],
        layers=("municipalities", "urban_areas", "business_zones", "employers", "individuals"),
        employers_gdf=employers_gdf,
        individuals_gdf=individuals_gdf,
    )

