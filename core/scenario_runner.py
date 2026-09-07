# core/scenario_runner.py

import os
import numpy as np
import json
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


def _git_commit():
    """Commit som körningen gjordes på. Utan den går utfall inte att koppla
    till kod, och en samlad tabell blandar versioner utan att det syns."""
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "unknown"


def _git_dirty():
    import subprocess
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.DEVNULL, text=True)
        return bool(out.strip())
    except Exception:
        return False


def _resolve_seed(config):
    """Frö ur scenariot, miljövariabeln WORM_SEED, eller slumpat.

    Ett slumpat frö SPARAS, så att körningen kan upprepas i efterhand."""
    env = os.environ.get("WORM_SEED")
    if env:
        return int(env)
    s = config.get("seed") or config.get("simulation", {}).get("seed")
    if s is not None:
        return int(s)
    import random
    return random.randrange(2 ** 31)


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
        # Lös upp 'extends' så att kommuner kan dela en gemensam
        # simulation-konfiguration (se scenarios/_simulation_defaults.yml).
        from core.configreader import ConfigReader as _CR
        config = _CR.resolve_extends(config, os.path.dirname(os.path.abspath(config_path)))

        db_path = "data/worm.sqlite3"
        conn = sqlite3.connect(db_path)
        cfg_reader = ConfigReader(config, conn)
        cfg_reader.validate_scenario(strict=True)
        geoworld = GeoWorld(db_path)
        builder = ScenarioBuilder(conn, cfg_reader, geoworld=geoworld)

        scenario_name = config.get("scenario_name", os.path.splitext(os.path.basename(config_path))[0])
        outdir, run_id = create_run_output_dir(scenario_name)

        # --- 2. Spara metadata för run ---
        # Härkomst i maskinläsbar form. Utan den blandar en samlad tabell
        # körningar från olika kodversioner, och en regression mäter
        # kodhistorik i stället för det den ska mäta. Fröet gör körningen
        # upprepbar och gör spridning över frön mätbar.
        seed = _resolve_seed(config)
        np.random.seed(seed)
        meta = {
            "run_id": run_id,
            "scenario": scenario_name,
            "scenario_file": os.path.basename(config_path),
            "seed": seed,
            "git_commit": _git_commit(),
            "git_dirty": _git_dirty(),
            "started": datetime.datetime.now().isoformat(timespec="seconds"),
            "municipalities": config.get("municipalities"),
            "n_years": config.get("n_years") or config.get("simulation", {}).get("n_years"),
            "simulation": {k: v for k, v in config.get("simulation", {}).items()
                           if not isinstance(v, (dict, list))},
        }
        with open(os.path.join(outdir, "run_meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)
        with open(os.path.join(outdir, "metadata.txt"), "w") as f:
            f.write(f"Run ID: {run_id}\n")
            f.write(f"Scenario: {scenario_name}\n")
            f.write(f"Seed: {seed}\n")
            f.write(f"Commit: {meta['git_commit']}"
                    f"{' (ocommittade ändringar)' if meta['git_dirty'] else ''}\n")
        print(f"[RUN] {run_id}  seed={seed}  commit={meta['git_commit'][:8]}"
              f"{'+dirty' if meta['git_dirty'] else ''}")

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
        log.save_run_output(match_stats, commuting_stats, scenario_name, outdir=outdir)

        save_basic_stats(result, outdir, tag="before")

        # --- 9. Eventdriven simulering ---
        local_log("Starting event-driven simulation ...")
        world.simulate()

        # --- 10. Spara post-sim statistik ---
        save_basic_stats(result, outdir, tag="after")
        world.individuals.to_csv(os.path.join(outdir, "final_state_individuals.csv"), index=False)
        world.jobs.to_csv(os.path.join(outdir, "final_state_jobs.csv"), index=False)
        world.employers.to_csv(os.path.join(outdir, "final_state_employers.csv"), index=False)
        log.save_run_output(match_stats, commuting_stats, scenario_name, outdir=outdir)

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
