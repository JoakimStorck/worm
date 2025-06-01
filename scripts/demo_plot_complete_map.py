import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon
from shapely.geometry import Polygon, MultiPolygon

def plot_geoworld_layers(geoworld, layers=("municipalities", "urban_areas", "business_zones")):
    fig, ax = plt.subplots(figsize=(10, 10))

    colors = {
        "municipalities": "#aaaaaa44",  # ljusgrå med transparens
        "urban_areas": "#3377ff55",     # blå
        "business_zones": "#dd333355",  # röd
        "commercial_zones": "#33bb7755",# grön
        "small_localities": "#55555522" # mörkgrå
    }

    for layer in layers:
        if not hasattr(geoworld, layer):
            continue
        for entity in getattr(geoworld, layer).values():
            poly = entity.polygon
            if poly is None:
                continue
            if isinstance(poly, (MultiPolygon,)):
                for subpoly in poly.geoms:
                    x, y = subpoly.exterior.xy
                    ax.fill(x, y, color=colors.get(layer, "#88888844"), label=layer if layer not in ax.get_legend_handles_labels()[1] else "")
            elif isinstance(poly, Polygon):
                x, y = poly.exterior.xy
                ax.fill(x, y, color=colors.get(layer, "#88888844"), label=layer if layer not in ax.get_legend_handles_labels()[1] else "")

    ax.set_aspect("equal")
    ax.set_title("Overview of GeoWorld")
    ax.axis("off")
    # Gör legend tydlig (en gång per kategori)
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc="upper right")
    plt.tight_layout()
    plt.show()

# --- ANVÄNDNING ---
from worm.geography.geoworld import GeoWorld
gw = GeoWorld("data/worm.sqlite3")
plot_geoworld_layers(gw, layers=("municipalities", "urban_areas", "business_zones"))
