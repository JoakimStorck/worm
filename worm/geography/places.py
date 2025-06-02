# worm/geography/places.py

from dataclasses import dataclass
from typing import Optional

@dataclass
class Place:
    place_id: str
    x: float
    y: float
    municipality_id: Optional[str] = None
    deso_id: Optional[str] = None

@dataclass
class Residence(Place):
    pass

@dataclass
class Workplace(Place):
    employer_id: Optional[str] = None
    sni_code: Optional[str] = None

