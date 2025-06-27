# worm/statistics/log.py

import os
import csv
import json
import datetime

import numpy as np
import pandas as pd

_log_lines = []

def log(*args, print_also=True):
    msg = ' '.join([str(a) for a in args])
    _log_lines.append(msg)
    if print_also:
        print(msg)

def default_converter(o):
    if isinstance(o, np.generic):
        return o.item()
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")

def build_standard_logdict(event, agent_type, agent=None, agent_id=None, extra=None, free_text=""):
    return {
        "time": event["time"],
        "event": event["event_type"],
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

def save_run_output(matching_stats, commuting_stats, scenario_name, outdir="output"):
    os.makedirs(outdir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join(outdir, f"{scenario_name}_{ts}")
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

    def log_event(self, world, event, agent_type=None, extra=None, print_line=False):
        """
        Loggar ett event oavsett agenttyp (individual, employer, system).
        Identifierar agent utifrån agent_type och event["agent_id"].
        """
        # Agent lookup
        agent = None
        agent_id = None

        if agent_type is None:
            # Försök avgöra agenttyp automatiskt
            if event["agent_id"] is None:
                agent_type = "system"
            elif event["agent_id"] in getattr(world, "individuals", pd.DataFrame()).index:
                agent_type = "individual"
            elif event["agent_id"] in getattr(world, "employers", pd.DataFrame()).index:
                agent_type = "employer"
            else:
                agent_type = "unknown"

        if agent_type == "individual":
            agent = world.individuals.loc[event["agent_id"]] if event["agent_id"] in world.individuals.index else None
            agent_id = agent.get("individual_id", event["agent_id"]) if agent is not None else event["agent_id"]
        elif agent_type == "employer":
            agent = world.employers.loc[event["agent_id"]] if event["agent_id"] in world.employers.index else None
            agent_id = agent.get("employer_id", event["agent_id"]) if agent is not None else event["agent_id"]
        else:
            agent = None
            agent_id = event["agent_id"]

        logdict = build_standard_logdict(
            event=event,
            agent_type=agent_type,
            agent=agent,
            agent_id=agent_id,
            extra=extra
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
