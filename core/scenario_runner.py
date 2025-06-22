# core/scenario_runner.py

import os
import sys
import sqlite3
import yaml
import datetime
import pandas as pd

from core.configreader import ConfigReader
from core.geography.geoworld import GeoWorld
from core.scenariobuilder import ScenarioBuilder
from core.world import World
from core.statistics.matching_stats import compute_matching_statistics, compute_commuting_statistics 
import core.log as log   # log, save_run_output
from core.scenario_result import ScenarioResult
from core.statistics.basic_stats import save_basic_stats

REGISTRY_PATH = "output/runs_registry.csv"
REGISTRY_HEADER = "run_id,output_path,scenario_name,timestamp\n"

def ensure_registry_exists():
    if not os.path.exists(REGISTRY_PATH):
        os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
        with open(REGISTRY_PATH, "w") as f:
            f.write(REGISTRY_HEADER)

def create_run_output_dir(scenario_name):
    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = os.path.join("output", f"run_{run_id}")
    os.makedirs(outdir, exist_ok=True)
    return outdir, run_id

def run_and_log_scenario(config_path):
    """
    Kör en komplett simulering, sparar output/resultat i unik output-mapp,
    uppdaterar central registry, och returnerar körlogg som text.
    """
    output_buffer = []
    def local_log(*args):
        s = " ".join([str(a) for a in args])
        log.log(s)
        output_buffer.append(s)

    try:
            
        # --- 1. Ladda scenario och skapa run-mapp ---
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        db_path = "data/worm.sqlite3"
        conn = sqlite3.connect(db_path)
        cfg_reader = ConfigReader(config, conn)
        cfg_reader.validate_scenario(strict=True)
        geoworld = GeoWorld(db_path)
        builder = ScenarioBuilder(conn, cfg_reader, geoworld=geoworld)

        scenario_name = config.get("scenario_name", os.path.splitext(os.path.basename(config_path))[0])
        outdir, run_id = create_run_output_dir(scenario_name)

        # --- 2. Spara metadata för run ---
        with open(os.path.join(outdir, "metadata.txt"), "w") as f:
            f.write(f"Run ID: {run_id}\n")
            f.write(f"Scenario: {scenario_name}\n")
            f.write(f"Timestamp: {run_id}\n")
            f.write(f"Config: {config}\n")

        # --- 3. Generera data ---
        individuals, jobs, employers, events = builder.generate()
        result = ScenarioResult(
            individuals,
            jobs,
            employers,
            events,
            outdir
        )

        # --- 4. Skapa World ---
        world = World(
            db_path,
            cfg_reader=cfg_reader,
            outdir=outdir,
            individuals=result.individuals,
            jobs=result.jobs,
            employers=result.employers,
            events=result.events,
            geoworld=geoworld
        )

        # --- 5. Initial statistik/logg ---
        local_log("Scenario:", config_path)

        # --- 6. Initial batch-matching ---
        matchings = world.match_individuals_to_jobs(
            mode="interleaved_multilevel",
            alpha_chi=config.get('alpha_chi', 5.0),
            alpha_xi=config.get('alpha_xi', 5.0),
            alpha_geo=config.get('alpha_geo', 1.0)
        )
        world.update_after_matching(matchings=matchings)
        local_log("Pre-run matching (t=0) completed.")

        # --- 7. Statistik för batch-match ---
        match_stats = compute_matching_statistics(matchings)
        commuting_stats = compute_commuting_statistics(matchings, world.individuals, world.jobs)

        # --- 8. Spara snapshots och batchresultat ---
        world.individuals.to_csv(os.path.join(outdir, "initial_state_individuals.csv"), index=False)
        world.jobs.to_csv(os.path.join(outdir, "initial_state_jobs.csv"), index=False)
        world.employers.to_csv(os.path.join(outdir, "initial_state_employers.csv"), index=False)
        log.save_run_output(world.matchings, match_stats, commuting_stats, scenario_name, outdir=outdir)

        save_basic_stats(result, outdir, tag="before")

        # --- 9. Eventdriven simulering ---
        local_log("Starting event-driven simulation ...")
        world.simulate()

        # --- 10. Spara post-sim statistik ---
        save_basic_stats(result, outdir, tag="after")
        world.individuals.to_csv(os.path.join(outdir, "final_state_individuals.csv"), index=False)
        world.jobs.to_csv(os.path.join(outdir, "final_state_jobs.csv"), index=False)
        world.employers.to_csv(os.path.join(outdir, "final_state_employers.csv"), index=False)
        log.save_run_output(world.matchings, match_stats, commuting_stats, scenario_name, outdir=outdir)

        world.close()

        # --- 11. Uppdatera registry ---
        ensure_registry_exists()
        with open(REGISTRY_PATH, "a") as reg:
            reg.write(f"{run_id},{os.path.abspath(outdir)},{scenario_name},{datetime.datetime.now().isoformat()}\n")

    except Exception as e:
        import traceback
        traceback.print_exc()

    return "\n".join(output_buffer)


# --- CLI-stöd: tillåter körning som script ---
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Ange sökväg till scenario/config-fil!")
        sys.exit(1)
    output = run_and_log_scenario(sys.argv[1])
    print(output)
