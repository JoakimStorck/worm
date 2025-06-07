# scripts/run_scenario.py

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worm.world import World
from worm.scenariobuilder import ScenarioBuilder

if __name__ == "__main__":
    # Initiera GeoWorld (och ev. koppling till databas)
    db_path = "data/worm.sqlite3"

    # Ladda scenariot
    scenario_path = "scenarios/falun_baseline.yml"
    builder = ScenarioBuilder(scenario_path, db_path="data/worm.sqlite3", geoworld=None)

    # Generera scenario-agentdata (workers, jobs, employers, events...)
    workers, jobs, employers, events = builder.generate()

    print(f"Antal genererade arbetsgivare: {len(employers)}")
    print("\nTopp 10 största arbetsgivare (storlek, SNI, zon):")
    print(employers.nlargest(10, "size")[["size", "sni_code", "layer", "zone_code"]])
    print("\nTopp 10 SNI-koder (arbetsgivare):")
    print(employers["sni_code"].value_counts().head(10))

    # Skapa World och injicera scenariodata
    world = World(db_path, workers=workers, jobs=jobs, employers=employers, events=events)

    # Kör analys och visualisering
    print("Scenario:", scenario_path)
    print("Statistik före matchning:", world.analyze())

    world.match_workers_to_jobs()
    print("Efter matchning:", world.analyze())

    # Hämta urval från scenario:
    municipalities = builder.config["municipalities"]

    world.plot(
        layers=("municipalities", "urban_areas", "business_zones", "employers", "workers"), 
        municipal_codes_or_names=municipalities, 
        employers_gdf=employers,
        #workers_gdf=workers
    )


