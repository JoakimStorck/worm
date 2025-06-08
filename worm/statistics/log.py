# worm/statistics/log.py


import os
import json
from datetime import datetime

import numpy as np


log_lines = []

def log(*args, print_also=True):
    msg = ' '.join([str(a) for a in args])
    log_lines.append(msg)
    if print_also:
        print(msg)


def save_log(scenario_name=None, output_dir="output"):
    """Save the global log to a file with scenario name and timestamp."""
    # Skapa katalog om den inte finns
    os.makedirs(output_dir, exist_ok=True)
    # Tid för filnamnet
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    # Bygg filnamnet
    if scenario_name:
        safe_scenario = scenario_name.replace("/", "_").replace("\\", "_")
        filename = f"{output_dir}/log_{safe_scenario}_{timestamp}.txt"
    else:
        filename = f"{output_dir}/log_{timestamp}.txt"
    # Skriv till fil
    with open(filename, "w", encoding="utf-8") as f:
        f.write('\n'.join(log_lines))
    return filename  # så att du kan visa namnet på filen efteråt

def default_converter(o):
    if isinstance(o, np.generic):
        return o.item()
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

def save_run_output(matchings, matching_stats, commuting_stats, log_lines, scenario_name):
    os.makedirs("output", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"output/{scenario_name}_{ts}"
    matchings.to_csv(f"{base}_matchings.csv", index=False)
    with open(f"{base}_matching_stats.json", "w", encoding="utf-8") as f:
        json.dump(matching_stats, f, indent=2, ensure_ascii=False, default=default_converter)
    with open(f"{base}_commuting_stats.json", "w", encoding="utf-8") as f:
        json.dump(commuting_stats, f, indent=2, ensure_ascii=False, default=default_converter)
    with open(f"{base}_log.txt", "w", encoding="utf-8") as f:
        f.write('\n'.join(log_lines))
