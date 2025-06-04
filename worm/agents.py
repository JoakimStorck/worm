
from dataclasses import dataclass, field
from typing import List, Tuple
from typing import Optional, Dict


@dataclass
class Worker:
    id: str
    chi: float
    xi: float
    residence_id: str                 # FK till Residence
    workplace_id: Optional[str] = None
    occupation_code: Optional[str] = None   # Om du vill ange “yrkesbakgrund”
    skill_profile: Optional[Dict[str, float]] = None
    work_status: str = 'unemployed'
    h: float = 0.0
