
"""
WORM – Worker-Occupation-Region Model

Ett forskningspaket för simulering av arbetsmarknader med fokus på:
- Kompetens (χ, ξ, H)
- Geografi
- Matchning

Moduler:
- agents
- geo
- occupation
- matching
- plotting
"""

from .agents import Worker, Job, Employer, generate_workers, generate_employers
from .geo import Geography
from .occupation import compute_utility
from .matching import match_workers_to_jobs
