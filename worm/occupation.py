
import numpy as np
import math
from worm.agents import Worker
from worm.jobs import Job

def angular_distance(xi1, xi2):
    diff = abs(xi1 - xi2)
    return min(diff, 2 * np.pi - diff)

def compute_utility(worker: Worker, job: Job, alpha=1.0) -> float:
    if worker.chi < job.chi:
        return -np.inf
    angle_penalty = np.exp(-alpha * angular_distance(worker.xi, job.xi))
    dx = worker.position[0] - job.position[0]
    dy = worker.position[1] - job.position[1]
    distance = math.sqrt(dx**2 + dy**2)
    return (job.chi / (distance + 1e-6)) * angle_penalty
