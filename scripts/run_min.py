"""
run_min.py  (placera i scripts/)
--------------------------------
Minimalt, korrigerat drivskript för WORM mot det AKTUELLA core-API:t.
Ersätter pipeline/run_scenario_pipeline.py som är osynkad mot koden.

Löser ut repo-roten själv, så skriptet fungerar oavsett varifrån det körs
och var det ligger (letar uppåt efter mappen som innehåller core/ och scenarios/).

Förutsätter att data/worm.sqlite3 finns (är redan byggd). Kör:
    python scripts/run_min.py
"""
import os
import sys
import sqlite3
import yaml


def find_repo_root(start):
    """Gå uppåt tills vi hittar mappen som innehåller både core/ och scenarios/."""
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, "core")) and os.path.isdir(os.path.join(d, "scenarios")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            raise RuntimeError("Hittade ingen repo-rot (mapp med core/ och scenarios/).")
        d = parent


ROOT = find_repo_root(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

from core.configreader import ConfigReader
from core.geography.geoworld import GeoWorld
from core.scenariobuilder import ScenarioBuilder
from core.world import World

# Absoluta sökvägar under repo-roten – oberoende av aktuell katalog
SCENARIO_PATH = os.path.join(ROOT, "scenarios", "mora_baseline.yml")   # minsta scenariot
DB_PATH       = os.path.join(ROOT, "data", "worm.sqlite3")
OUTDIR        = os.path.join(ROOT, "output", "run_min")

RUN_EVENT_SIMULATION = False   # sätt True för att även köra den händelsedrivna delen


def main():
    if not os.path.exists(DB_PATH):
        raise SystemExit(f"Saknar databas: {DB_PATH} (kör scripts/create_database.py)")
    os.makedirs(OUTDIR, exist_ok=True)

    # 1. Scenario (YAML) -> dict
    with open(SCENARIO_PATH, "r", encoding="utf-8") as f:
        scenario = yaml.safe_load(f)

    # 2. Konfiguration + DB-anslutning
    conn = sqlite3.connect(DB_PATH)
    cfg = ConfigReader(scenario, conn)
    cfg.validate_scenario(strict=False)   # strict=True för full validering

    # 3. Bygg world (rätt argumentordning enligt nuvarande signaturer)
    geoworld = GeoWorld(DB_PATH)
    builder = ScenarioBuilder(conn, cfg, geoworld=geoworld)
    individuals, jobs, employers, events = builder.generate()

    print("\n[BYGGT]")
    print("  individuals:", individuals.shape, list(individuals.columns)[:12])
    print("  jobs:       ", jobs.shape, list(jobs.columns)[:12])
    print("  employers:  ", employers.shape)

    world = World(
        DB_PATH, cfg, OUTDIR,
        geoworld=geoworld,
        individuals=individuals,
        jobs=jobs,
        employers=employers,
        events=events,
    )

    # 4. Batch-matchning vid t=0 (alpha-vikterna explicit för robusthet)
    matchings = world.match_individuals_to_jobs(
        mode="interleaved_multilevel",
        alpha_chi=5.0, alpha_xi=5.0, alpha_geo=1.0,
    )
    world.update_after_matching(matchings=matchings)

    n_emp = (world.individuals["status"] == "employed").sum()
    print(f"\n[MATCHNING t=0] {len(matchings)} matchningar, "
          f"{n_emp}/{len(world.individuals)} sysselsatta")

    # 5. (Valfritt) Händelsedriven simulering över hela horisonten
    if RUN_EVENT_SIMULATION:
        print("\n[SIMULERING] startar event-driven körning ...")
        world.simulate()
        n_emp2 = (world.individuals["status"] == "employed").sum()
        print(f"[SIMULERING klar] {n_emp2}/{len(world.individuals)} sysselsatta vid slutet")
        print(f"Eventlogg: {os.path.join(OUTDIR, 'eventlog.csv')}")

    conn.close()


if __name__ == "__main__":
    main()
