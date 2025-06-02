
from dataclasses import dataclass, field
from typing import List, Tuple
import numpy as np
import uuid

from dataclasses import dataclass
from typing import Optional

@dataclass
class Worker:
    id: str
    chi: float
    xi: float
    residence_id: str                 # FK till Residence/Place
    workplace_id: Optional[str] = None  # FK till Workplace/Place, None=arbetslös
    work_status: str = 'unemployed'     # 'employed' eller 'unemployed'

