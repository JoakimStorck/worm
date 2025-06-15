# worm/statistics/log.py


import os
import csv
import json
import datetime

import numpy as np


_log_lines = []

def log(*args, print_also=True):
    msg = ' '.join([str(a) for a in args])
    _log_lines.append(msg)
    if print_also:
        print(msg)


# def save_log(scenario_name=None, output_dir="output"):
#     """Save the global log to a file with scenario name and timestamp."""
#     # Skapa katalog om den inte finns
#     os.makedirs(output_dir, exist_ok=True)
#     # Tid för filnamnet
#     timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
#     # Bygg filnamnet
#     if scenario_name:
#         safe_scenario = scenario_name.replace("/", "_").replace("\\", "_")
#         filename = f"{output_dir}/log_{safe_scenario}_{timestamp}.txt"
#     else:
#         filename = f"{output_dir}/log_{timestamp}.txt"
#     # Skriv till fil
#     with open(filename, "w", encoding="utf-8") as f:
#         f.write('\n'.join(log_lines))
#     return filename  # så att du kan visa namnet på filen efteråt

def default_converter(o):
    if isinstance(o, np.generic):
        return o.item()
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

def build_standard_logdict(event, agent_type, agent=None, agent_id=None, extra=None, free_text=""):
    return {
        "time": event.time,
        "event": event.event_type,
        "agent_type": agent_type,
        "agent_id": agent_id,
        "chi": agent.get("chi") if agent is not None else None,
        "xi": agent.get("xi") if agent is not None else None,
        "H": agent.get("H") if agent is not None else None,
        "free_text": free_text,
        **(extra if extra else {})
    }

def create_run_output_dir(scenario_name):
    run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = os.path.join("output", f"run_{run_id}")
    os.makedirs(outdir, exist_ok=True)
    # Spara metadata
    with open(os.path.join(outdir, "metadata.txt"), "w") as f:
        f.write(f"Run ID: {run_id}\n")
        f.write(f"Scenario: {scenario_name}\n")
        f.write(f"Timestamp: {run_id}\n")
    return outdir, run_id

def save_run_output(matchings, matching_stats, commuting_stats, scenario_name, outdir="output"):
    os.makedirs(outdir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(outdir, f"{scenario_name}_{ts}")
    matchings.to_csv(f"{base}_matchings.csv", index=False)
    with open(f"{base}_matching_stats.json", "w", encoding="utf-8") as f:
        json.dump(matching_stats, f, indent=2, ensure_ascii=False, default=default_converter)
    with open(f"{base}_commuting_stats.json", "w", encoding="utf-8") as f:
        json.dump(commuting_stats, f, indent=2, ensure_ascii=False, default=default_converter)
    with open(f"{base}_log.txt", "w", encoding="utf-8") as f:
        f.write('\n'.join(_log_lines))


class EventLogger:
    def __init__(self, filepath=None):
        self.filepath = filepath
        self.file = open(filepath, 'w') if filepath else None
        self.csv_writer = None
        self.columns = None

    def log_individual_event(self, world, event, extra=None, print_line=False):
        idx = event.agent_id
        ind = world.individuals.loc[idx]
        logdict = build_standard_logdict(
            event=event,
            agent_type="individual",
            agent=ind,
            agent_id=ind.get("individual_id", idx),
            extra=extra
        )
        self._write_log(logdict, print_line)

    def log_employer_event(self, world, event, extra=None, print_line=False):
        idx = event.agent_id
        emp = world.employers.loc[idx]
        logdict = build_standard_logdict(
            event=event,
            agent_type="employer",
            agent=emp,
            agent_id=emp.get("employer_id", idx),
            extra=extra
        )
        self._write_log(logdict, print_line)

    def log_generic_event(self, event, data=None, print_line=False):
        logdict = build_standard_logdict(
            event=event,
            agent_type="system",
            agent=None,
            agent_id=None,
            extra=data
        )
        self._write_log(logdict, print_line)

    def _write_log(self, logdict, print_line=False):
        # Skriv alltid ut tidsstämpel och event-typ först
        parts = []
        if 'time' in logdict:
            parts.append(f"{logdict['time']:.2f}")
        if 'event' in logdict:
            parts.append(f"{logdict['event']}")
        # Lägg till övriga fält i den ordning de lades in
        for k in logdict:
            if k in ['time', 'event']:
                continue
            parts.append(f"{k} {logdict[k]}")
        line = ", ".join(str(x) for x in parts)
        if self.file:
            self.file.write(line + "\n")
            self.file.flush()
            if print_line:
                print(line)
        else:
            print(line)



    def close(self):
        if self.file:
            self.file.close()
