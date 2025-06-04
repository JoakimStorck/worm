import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import matplotlib.pyplot as plt
import geopandas as gpd
from worm.geography.geoworld import GeoWorld

def plot_geoworld_layers(geoworld, layers=("municipalities", "urban_areas", "business_zones")):
    fig, ax = plt.subplots(figsize=(10, 10))

    colors = {
        "municipalities": "#aaaaaa44",
        "urban_areas": "#3377ff55",
        "business_zones": "#dd333355",
        "commercial_zones": "#33bb7755",
        "small_localities": "#55555522"
    }

    plotted = set()
    for layer in layers:
        if not hasattr(geoworld, layer):
            print(f"Warning: GeoWorld does not have layer '{layer}'.")
            continue
        gdf = getattr(geoworld, layer)
        if not isinstance(gdf, gpd.GeoDataFrame):
            print(f"Warning: Layer '{layer}' is not a GeoDataFrame.")
            continue
        if gdf.empty:
            print(f"Warning: Layer '{layer}' is empty.")
            continue
        # Plot hela lagret i ett anrop!
        gdf.plot(ax=ax, color=colors.get(layer, "#88888844"), label=layer if layer not in plotted else "", linewidth=0.5, edgecolor="#55555544")
        plotted.add(layer)

    ax.set_aspect("equal")
    ax.set_title("Overview of GeoWorld")
    ax.axis("off")
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc="upper right")
    plt.tight_layout()
    plt.show()

# --- ANVÄNDNING ---
gw = GeoWorld("data/worm.sqlite3")
plot_geoworld_layers(gw, layers=("municipalities",))
