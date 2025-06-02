import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worm.generate import generate_employers, generate_jobs, generate_workers
from worm.geography.places import Residence
import uuid
import numpy as np

# Skapa arbetsgivare och arbetsplatser
employers, workplaces = generate_employers(10, map_size=100)

# Skapa n residens (residences)
residences = [
    Residence(
        place_id=str(uuid.uuid4()),
        x=np.random.uniform(0, 100),
        y=np.random.uniform(0, 100),
        municipality_id=None,
        deso_id=None
    )
    for _ in range(50)
]

# Skapa arbetare
workers = generate_workers(100, residences)

# Skapa jobb
jobs = generate_jobs(employers)

print(f"Antal arbetsgivare: {len(employers)}")
print(f"Antal arbetsplatser: {len(workplaces)}")
print(f"Antal arbetare: {len(workers)}")
print(f"Antal jobb: {len(jobs)}")
