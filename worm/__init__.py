"""
WORM – Worker-Occupation-Region Model

Ett forskningspaket för simulering av arbetsmarknader med fokus på:
- Kompetens (χ, ξ, H)
- Geografi
- Matchning

Moduler:
- agents (Worker)
- jobs (Job)
- employers (Employer)
- places (Place, Residence, Workplace)
- occupation
- matching
- generate
- plotting
"""

import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Individer (arbetstagare)
from .agents import Worker
# Jobb
from .jobs import Job
# Arbetsgivare
from .employers import Employer
# Genereringsfunktioner
from .generate import generate_employers, generate_jobs, generate_workers
# Platser/geografi
from .geography.places import Place, Residence, Workplace
# Matchning
from .matching import match_workers_to_jobs
