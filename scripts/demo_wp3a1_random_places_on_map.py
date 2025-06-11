import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.geography.geoworld import GeoWorld
from core.geography.places import Residence, Workplace
from core.geography.geoutils import random_points_in_polygon

gw = GeoWorld("data/worm.sqlite3")
falun = [m for m in gw.municipalities.values() if m.name.lower() == "falun"][0]

# Slumpa 100 residences, 20 workplaces
res_coords = random_points_in_polygon(falun.polygon, 100)
wp_coords = random_points_in_polygon(falun.polygon, 20)

residences = [Residence(place_id=f"r{i}", x=x, y=y, municipality_id="2080") for i, (x, y) in enumerate(res_coords)]
workplaces = [Workplace(place_id=f"w{i}", x=x, y=y, municipality_id="2080") for i, (x, y) in enumerate(wp_coords)]

# Plotta
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(8,8))
# Falun polygon
x, y = falun.polygon.exterior.xy
ax.fill(x, y, color="#ececec", label="Falun kommun")
# Residences
ax.scatter([r.x for r in residences], [r.y for r in residences], color="blue", label="Bostäder", alpha=0.7)
# Workplaces
ax.scatter([w.x for w in workplaces], [w.y for w in workplaces], color="red", marker="s", label="Arbetsplatser", alpha=0.7)
ax.set_aspect("equal")
ax.legend()
ax.set_title("Slumpade bostäder och arbetsplatser i Falun")
plt.show()
