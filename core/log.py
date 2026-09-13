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
        "r_i": agent.get("r_i") if agent is not None else None,
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

class _AgentFields:
    """De fyra fält loggen faktiskt läser, ur CACHADE kolumnarrayer.

    MÄTT, INTE GISSAT, och första försöket var fel. .loc[idx] bygger en Series
    över alla kolumner (pandas fast_xs): 45 us. Att i stället läsa de fyra
    fälten med .at[] kostade 45 us -- ingen vinst alls, varje .at är ett eget
    uppslag. Kolumnerna som numpy-arrayer, med en get_loc för positionen,
    kostar 1.1 us. Arrayerna cachas per tabell och byggs om när tabellen byter
    längd, vilket är samma villkor som jobbtabellens arrayer använder sedan
    0060.

    Bär samma get()-gränssnitt som den Series den ersätter, så
    build_standard_logdict är oförändrad.
    """

    FALT = ("individual_id", "employer_id", "chi", "xi", "r_i")
    __slots__ = ("_kol", "_pos", "id_value")

    def __init__(self, cache, df, idx, id_column):
        self._kol = cache.kolumner(df)
        self._pos = None
        if self._kol is not None:
            try:
                self._pos = df.index.get_loc(idx)
            except KeyError:
                self._pos = None
        self.id_value = self.get(id_column, idx) if self._pos is not None else idx

    def get(self, key, default=None):
        if self._pos is None or self._kol is None:
            return default
        arr = self._kol.get(key)
        if arr is None:
            return default
        v = arr[self._pos]
        return default if v is None else v


class _KolumnCache:
    """Kolumnarrayer per tabell, ombyggda när tabellen byter längd."""

    def __init__(self):
        self._per_tabell = {}

    def kolumner(self, df):
        if df is None or not len(df):
            return None
        nyckel = id(df)
        post = self._per_tabell.get(nyckel)
        if post is None or post[0] != len(df) or post[1] is not df.columns.size:
            self._per_tabell[nyckel] = (
                len(df), df.columns.size,
                {k: df[k].to_numpy() for k in _AgentFields.FALT if k in df.columns})
            post = self._per_tabell[nyckel]
        return post[2]


class EventLogger:
    # Buffertens storlek i rader. flush() per rad kostade 0.8 sekunder rent
    # systemanrop i profilen, och tvingade dessutom fram en skrivning per
    # händelse. Buffras och töms vid close() och vid print_line (månads- och
    # årsraderna), så att en avbruten körning ändå har allt fram till senaste
    # månadsskiftet.
    BUFFERT = 2000

    def __init__(self, filepath=None):
        self.filepath = filepath
        self.file = open(filepath, 'w') if filepath else None
        self.csv_writer = None
        self.columns = None
        self._buffert = []
        self._kolcache = _KolumnCache()

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

        # EN KONVENTION FÖR agent_id. Fram till 0092 skrev extra-dicten över
        # agent_id med DataFrame-indexet, medan händelsens egen agent_id
        # slogs upp och skrevs som individual_id. Loggen hade därför två
        # former för samma person -- 2062_i003443 på ansökan, 3443 på
        # match_completed -- och varje läsare som jämförde dem fick ingen
        # träff. Bär extra ett agent_id går det genom samma uppslagning.
        if extra and extra.get("agent_id") is not None and event.get("agent_id") is None:
            extra = dict(extra)
            event = {**event, "agent_id": extra.pop("agent_id")}
            agent_type = None
            if event["agent_id"] in getattr(world, "individuals", pd.DataFrame()).index:
                agent_type = "individual"
            elif event["agent_id"] in getattr(world, "employers", pd.DataFrame()).index:
                agent_type = "employer"
            else:
                agent_type = "unknown"

        # FYRA FÄLT, INTE EN SERIE. .loc[idx] på en DataFrame bygger en Series
        # över alla kolumner -- pandas fast_xs, 348 000 anrop och 21 sekunder
        # av 160 i profilen -- för att sedan läsa fyra av dem. Samma fyra
        # hämtas nu direkt ur kolumnerna. Identiskt utfall: agent.get(k)
        # returnerar None för en kolumn som inte finns, och det gör _hamta
        # också.
        agent = None
        if agent_type == "individual":
            agent = _AgentFields(self._kolcache, world.individuals,
                                 event["agent_id"], "individual_id")
            agent_id = agent.id_value
        elif agent_type == "employer":
            agent = _AgentFields(self._kolcache, world.employers,
                                 event["agent_id"], "employer_id")
            agent_id = agent.id_value
        else:
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
            self._buffert.append(line)
            if print_line or len(self._buffert) >= self.BUFFERT:
                self._tom()
            if print_line:
                print(line)
        else:
            print(line)

    def _tom(self):
        if self.file and self._buffert:
            self.file.write("\n".join(self._buffert) + "\n")
            self._buffert.clear()
            self.file.flush()

    def close(self):
        self._tom()
        if self.file:
            self.file.close()
