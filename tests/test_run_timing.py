"""Körtiden: att klockan stannas och att talet når runs.csv.

wallclock_start sattes i simulate() sedan länge utan att någonsin läsas. Ett
mått som ingen läser är samma sak som inget mått, och det märks inte förrän
någon frågar efter det. Testerna håller kedjan hel: World mäter, run_meta.json
bär, summary_row plockar upp.
"""
import json
import os

from conftest import make_world

from core.analysis.eventlog import summary_row


class _LoggerMedClose:
    def __init__(self):
        self.events = []

    def log_event(self, world, event, extra=None, print_line=False):
        self.events.append((event.get("event_type"), dict(extra or {})))

    def close(self):
        self.stangd = True


def test_simulate_loggar_kortid_och_handelseantal():
    w = make_world(n_employers=2, size=1)
    w.event_logger = _LoggerMedClose()
    w._init_events = lambda: None
    w._check_calendar_covers_run = lambda: None

    w.simulate()

    typer = dict(w.event_logger.events)
    assert "simulation_completed" in typer
    rad = typer["simulation_completed"]
    assert rad["wallclock_seconds"] >= 0.0
    assert rad["n_events_handled"] == 0
    # Och talet ska gå att läsa av utifrån, inte bara ligga i loggraden.
    assert w.sim_seconds >= 0.0


def test_summary_row_bar_kortiden(tmp_path):
    d = str(tmp_path / "run_t")
    os.makedirs(d)
    with open(os.path.join(d, "run_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"scenario": "mora_baseline", "seed": 3,
                   "git_commit": "0123456789", "municipalities": ["2062"],
                   "total_seconds": 412.5, "sim_seconds": 388.1}, f)
    with open(os.path.join(d, "eventlog.csv"), "w", encoding="utf-8") as f:
        f.write("0.00, new_month, month 1, year 2020, employed 0, "
                "unemployed 10, unmatched_jobs 10, active_jobs 10\n")

    rad = summary_row(d)
    assert rad["total_seconds"] == 412.5
    assert rad["sim_seconds"] == 388.1


def test_kortiden_saknas_tyst_for_aldre_korningar(tmp_path):
    """Körningar gjorda före 0115 har ingen klocka i härkomsten. De ska ge
    tomma fält, inte krascha analysen -- runs.csv blandar gamla och nya."""
    d = str(tmp_path / "run_g")
    os.makedirs(d)
    with open(os.path.join(d, "run_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"scenario": "mora_baseline", "seed": 1,
                   "git_commit": "abcdef1234"}, f)
    with open(os.path.join(d, "eventlog.csv"), "w", encoding="utf-8") as f:
        f.write("0.00, new_month, month 1, year 2020, employed 0, "
                "unemployed 10, unmatched_jobs 10, active_jobs 10\n")

    rad = summary_row(d)
    assert rad["total_seconds"] is None
    assert rad["sim_seconds"] is None
