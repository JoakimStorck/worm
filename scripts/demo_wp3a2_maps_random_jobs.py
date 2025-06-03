import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worm.geography.geoworld import GeoWorld
from worm.geography.places import Residence, Workplace
from worm.geography.geoutils import random_points_in_polygon
from worm.agents import Worker
from worm.jobs import Job

import uuid
import numpy as np
import matplotlib.pyplot as plt

# 1. Läs in Faluns kommunpolygon
gw = GeoWorld("data/worm.sqlite3")
falun = [m for m in gw.municipalities.values() if m.name.lower() == "falun"][0]

# 2. Slumpa ut 100 bostäder och 20 arbetsplatser inom Falun
res_coords = random_points_in_polygon(falun.polygon, 100)
wp_coords = random_points_in_polygon(falun.polygon, 20)

residences = [
    Residence(
        place_id=f"r{i}",
        x=x,
        y=y,
        municipality_id="2080"
    ) for i, (x, y) in enumerate(res_coords)
]

workplaces = [
    Workplace(
        place_id=f"w{i}",
        x=x,
        y=y,
        municipality_id="2080"
    ) for i, (x, y) in enumerate(wp_coords)
]

# 3. Skapa Workers (en per residence)
workers = [
    Worker(
        id=str(uuid.uuid4()),
        chi=np.random.lognormal(mean=2.0, sigma=1.0),
        xi=np.random.uniform(0, 2 * np.pi),
        residence_id=r.place_id,
        workplace_id=None,
        work_status='unemployed'
    )
    for r in residences
]

# 4. Skapa Jobs (3 per arbetsplats)
jobs = []
for w in workplaces:
    for i in range(3):
        jobs.append(
            Job(
                id=str(uuid.uuid4()),
                chi=np.random.lognormal(mean=1.0, sigma=0.5),
                xi=np.random.uniform(0, 2 * np.pi),
                occupation_cluster='A',  # placeholder
                workplace_id=w.place_id,
                employer_id=None
            )
        )

# 5. Enkel 1:1-matchning mellan Workers och Jobs (så långt det går)
for worker, job in zip(workers, jobs):
    worker.workplace_id = job.workplace_id
    worker.work_status = 'employed'
    # (Vill du, kan du lägga till job.filled_by = worker.id)

# 6. Plotta resultatet
fig, ax = plt.subplots(figsize=(8,8))

# Falun polygon
x, y = falun.polygon.exterior.xy
ax.fill(x, y, color="#ececec", label="Falun kommun")

# Bostäder (blå)
ax.scatter([r.x for r in residences], [r.y for r in residences], color="blue", label="Bostäder", alpha=0.7)

# Arbetsplatser (röd fyrkant)
ax.scatter([w.x for w in workplaces], [w.y for w in workplaces], color="red", marker="s", label="Arbetsplatser", alpha=0.7)

# Pendlingslinjer (hem → arbete)
for worker in workers:
    if worker.workplace_id:
        home = next(r for r in residences if r.place_id == worker.residence_id)
        work = next(w for w in workplaces if w.place_id == worker.workplace_id)
        ax.plot([home.x, work.x], [home.y, work.y], color="gray", alpha=0.25)

ax.set_aspect("equal")
ax.legend()
ax.set_title("Bostäder, arbetsplatser och pendling i Falun (slumpad demo)")
ax.axis("off")
plt.tight_layout()
plt.show()
