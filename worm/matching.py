
from .agents import Worker, Employer
from .occupation import compute_utility
from typing import List, Tuple

def match_workers_to_jobs(workers: List[Worker], employers: List[Employer], alpha=1.0) -> List[Tuple[Worker, object, float]]:
    all_jobs = [job for employer in employers for job in employer.jobs]
    used_jobs = set()
    matches = []

    for worker in workers:
        best_score = -float('inf')
        best_job = None

        for job in all_jobs:
            if job.id in used_jobs:
                continue
            score = compute_utility(worker, job, alpha)
            if score > best_score:
                best_score = score
                best_job = job

        if best_job:
            used_jobs.add(best_job.id)
            matches.append((worker, best_job, best_score))

    return matches
