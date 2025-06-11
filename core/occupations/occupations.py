
from core.agents import Worker
from core.jobs import Job

from dataclasses import dataclass
from typing import Dict

@dataclass
class Occupation:
    code: str                         # T.ex. O*NET-SOC eller SSYK/ISCO
    title: str
    skill_profile: Dict[str, float]   # {skill_id: vikt/level}
    cluster: int                      # Cluster-ID (från KMeans/occupational space)
    cluster_name: str
    chi: float
    xi: float
    h: float


