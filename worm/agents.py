
from dataclasses import dataclass, field
from typing import List, Tuple
import numpy as np
import uuid

@dataclass
class Job:
    id: str
    chi: float
    xi: float
    position: Tuple[float, float]
    employer_id: str

@dataclass
class Worker:
    id: str
    chi: float
    xi: float
    position: Tuple[float, float]

@dataclass
class Employer:
    id: str
    position: Tuple[float, float]
    segment: float
    size: int
    jobs: List[Job] = field(default_factory=list)

    def generate_jobs(self):
        for _ in range(self.size):
            chi = np.random.lognormal(mean=1.0, sigma=0.5)
            xi = self.segment + np.random.normal(scale=0.1)
            job = Job(
                id=str(uuid.uuid4()),
                chi=chi,
                xi=xi,
                position=self.position,
                employer_id=self.id
            )
            self.jobs.append(job)

def generate_employers(n, map_size=100) -> List[Employer]:
    employers = []
    for _ in range(n):
        x, y = np.random.uniform(0, map_size, size=2)
        segment = np.random.uniform(0, 2 * np.pi)
        size = int(np.random.lognormal(mean=1.0, sigma=0.7))
        size = max(1, min(size, 25))
        employer = Employer(id=str(uuid.uuid4()), position=(x, y), segment=segment, size=size)
        employer.generate_jobs()
        employers.append(employer)
    return employers

def generate_workers(n, map_size=100) -> List[Worker]:
    workers = []
    for _ in range(n):
        x, y = np.random.uniform(0, map_size, size=2)
        chi = np.random.lognormal(mean=2.0, sigma=1.0)
        xi = np.random.uniform(0, 2 * np.pi)
        worker = Worker(
            id=str(uuid.uuid4()),
            chi=chi,
            xi=xi,
            position=(x, y)
        )
        workers.append(worker)
    return workers
