"""
Gemensamma testfixturer. Testerna kräver INGEN databas: de bygger syntetiska
världar i minnet. Det gör dem körbara på vilken maskin som helst och snabba
nog att köra före varje commit.
"""
import heapq
import os
import sys

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class FakeQueue:
    """Minimal händelsekö med samma gränssnitt som den riktiga."""
    def __init__(self):
        self._h = []
        self._c = 0

    def push(self, e):
        self._c += 1
        heapq.heappush(self._h, (e["time"], self._c, e))

    def pop(self):
        return heapq.heappop(self._h)[2]

    def is_empty(self):
        return not self._h

    def peek(self):
        return self._h[0][2]

    def __len__(self):
        return len(self._h)


class FakeLogger:
    def __init__(self):
        self.events = []

    def log_event(self, world, event, extra=None, print_line=False):
        self.events.append((event.get("event_type"), dict(extra or {})))


class FakeConfig:
    def __init__(self, simulation=None, timings=None, defaults=None):
        self.config = {"simulation": simulation or {},
                       "defaults": defaults or {"employer": {"training_prob_by_size": {}}}}
        self._timings = timings or {}

    def get_event_timing(self, name):
        return self._timings.get(name, {"dist": "exponential", "mean": 30.0})


def sample_disc(rng, n):
    r = np.sqrt(rng.uniform(0, 1, n))
    t = rng.uniform(0, 2 * np.pi, n)
    return r * np.cos(t), r * np.sin(t)


@pytest.fixture(autouse=True)
def _deterministic_seed():
    """Jobbpostningen använder stokastisk avrundning; utan fast frö blir
    enstaka anrop slumpmässiga och testerna flakiga."""
    np.random.seed(20260904)


@pytest.fixture
def rng():
    return np.random.default_rng(20260904)


@pytest.fixture
def individuals(rng):
    n = 200
    x, y = sample_disc(rng, n)
    return pd.DataFrame({
        "individual_id": np.arange(n),
        "x_occ": x, "y_occ": y,
        "r_i": np.zeros(n),
        "w_res": rng.uniform(0.3, 0.7, n),
        "x": rng.uniform(0, 30_000, n), "y": rng.uniform(0, 30_000, n),
        "status": "unemployed", "job_id": np.nan,
        "deso_code": "2062A", "municipal_code": 2062,
    })


@pytest.fixture
def jobs(rng):
    n = 240
    x, y = sample_disc(rng, n)
    return pd.DataFrame({
        "job_id": [f"J{i:05d}" for i in range(n)],
        "employer_id": [f"E{i % 20}" for i in range(n)],
        "individual_id": np.nan,
        "x_occ": x, "y_occ": y,
        "r_o": rng.uniform(0.10, 0.40, n),
        "wage": rng.uniform(0.5, 1.8, n),
        "x": rng.uniform(0, 30_000, n), "y": rng.uniform(0, 30_000, n),
        "deso_code": "2062A", "municipal_code": 2062,
        "zone_code": "2062A", "layer": "deso",
        "onet_code": "11-1011.00", "chi": 0.3, "xi": 0.3,
        "geom_source": "occupation", "employer_size": 12,
    })


def make_world(n_employers=40, size=5, simulation=None):
    """Syntetisk World för test av jobbflöden. Ingen databas."""
    from core.world import World
    sim = {"job_flows": True, "job_destruction_rate": 0.20,
           "vacancy_fill_rate": 0.25, "employer_growth_rate": 0.0,
           "rho_reservation": 0.7}
    sim.update(simulation or {})
    w = World.__new__(World)
    w.cfg_reader = FakeConfig(sim)
    w.current_time = 0.0
    w.event_queue = FakeQueue()
    w.event_logger = FakeLogger()
    w.conn = None
    w.simulation_end_time = 365.25 * 10

    w.employers = pd.DataFrame({
        "employer_id": [f"E{i}" for i in range(n_employers)],
        "municipal_code": "2062",
    })
    rows = []
    jid = 0
    for e in range(n_employers):
        for _ in range(size):
            rows.append({
                "job_id": f"J{jid:05d}", "employer_id": f"E{e}",
                "individual_id": np.nan, "municipal_code": "2062",
                "onet_code": "11-1011.00", "x_occ": 0.3, "y_occ": 0.1,
                "r_o": 0.27, "wage": 1.0, "chi": 0.3, "xi": 0.3,
                "geom_source": "occupation", "x": 0.0, "y": 0.0,
                "layer": "deso", "zone_code": "A", "employer_size": size,
            })
            jid += 1
    w.jobs = pd.DataFrame(rows)
    w.individuals = pd.DataFrame({
        "individual_id": [], "status": [], "job_id": [], "w_res": [],
        "chi": [], "xi": [], "r_i": [], "x_occ": [], "y_occ": [],
    })
    w._init_job_flows()
    return w


def run_months(world, months):
    """Kör förstörelse + månadsposting, returnerar aktiv jobbstock per månad."""
    from core.event_handlers import handle_destroy_job
    stock = []
    for m in range(1, months + 1):
        t = m * 30.44
        while not world.event_queue.is_empty() and world.event_queue.peek()["time"] <= t:
            ev = world.event_queue.pop()
            if ev["event_type"] == "destroy_job":
                handle_destroy_job(ev, world)
        world.post_vacancies_batch(t)
        stock.append(int(world.jobs["active"].sum()))
    return stock
