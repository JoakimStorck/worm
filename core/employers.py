from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Employer:
    id: str
    name: Optional[str]
    sni_codes: List[str]
    workplace_ids: List[str]
    job_profile: dict


@dataclass
class Employment:
    id: str
    worker_id: str
    job_id: str
    employer_id: str
    start_time: int                   # Tidssteg eller datetime
    end_time: Optional[int] = None

