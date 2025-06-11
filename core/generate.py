import uuid
import numpy as np
import random
from typing import List, Tuple
from core.employers import Employer
from core.geography.places import Workplace, Residence
from core.jobs import Job
from core.agents import Worker

def generate_employers(n, map_size=100) -> Tuple[List[Employer], List[Workplace]]:
    """
    Skapar n arbetsgivare och tillhörande arbetsplatser (Workplace).
    """
    employers = []
    workplaces = []
    for _ in range(n):
        x, y = np.random.uniform(0, map_size, size=2)
        employer_id = str(uuid.uuid4())
        workplace_id = str(uuid.uuid4())
        workplaces.append(Workplace(
            place_id=workplace_id,
            x=x,
            y=y,
            municipality_id=None,
            employer_id=employer_id,
            sni_code="62010"
        ))
        emp = Employer(
            id=employer_id,
            name=None,
            sni_codes=["62010"],
            job_profile={"A": np.random.randint(1, 5)},
            workplace_ids=[workplace_id]
        )
        employers.append(emp)
    return employers, workplaces

def generate_jobs(employers: List[Employer]) -> List[Job]:
    """
    Genererar jobb utifrån arbetsgivarnas job_profile och arbetsplatser.
    """
    jobs = []
    for emp in employers:
        for wp_id in emp.workplace_ids:
            for occ_cluster, n_jobs in emp.job_profile.items():
                for _ in range(n_jobs):
                    chi = np.random.lognormal(mean=1.0, sigma=0.5)
                    xi = np.random.uniform(0, 2 * np.pi)
                    jobs.append(Job(
                        id=str(uuid.uuid4()),
                        chi=chi,
                        xi=xi,
                        occupation_cluster=occ_cluster,
                        workplace_id=wp_id,
                        employer_id=emp.id
                    ))
    return jobs

def generate_workers(n, residences: List[Residence]) -> List[Worker]:
    """
    Slumpar ut n arbetare på givna bostadsplatser (Residence).
    """
    workers = []
    for i in range(n):
        residence = random.choice(residences)
        chi = np.random.lognormal(mean=2.0, sigma=1.0)
        xi = np.random.uniform(0, 2 * np.pi)
        workers.append(Worker(
            id=str(uuid.uuid4()),
            chi=chi,
            xi=xi,
            residence_id=residence.place_id,
            workplace_id=None,
            work_status='unemployed'
        ))
    return workers
