from dataclasses import dataclass

@dataclass
class Job:
    id: str
    chi: float
    xi: float
    occupation_cluster: str
    workplace_id: str
    employer_id: str
