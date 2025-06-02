from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Employer:
    id: str
    name: Optional[str]
    sni_codes: List[str]
    workplace_ids: List[str]
    job_profile: dict

