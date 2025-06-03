

from dataclasses import dataclass
from typing import Optional

@dataclass
class Job:
    id: str
    occupation_code: str              # FK till Occupation.code
    chi: float
    xi: float
    h: float
    cluster: int
    cluster_name: str
    workplace_id: str                 # FK till Workplace
    employer_id: str                  # FK till Employer
    filled_by: Optional[str] = None   # FK till Worker (om tillsatt)
