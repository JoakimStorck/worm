import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import matplotlib.pyplot as plt
import geopandas as gpd
from worm.geography.geoworld import GeoWorld

def plot_selected_municipalities(geoworld, codes_or_names, layers=("municipalities",)):
    """
    Rita en eller flera kommuner, och overlaya andra lager för samma kommun(er).
    All matchning sker på kommunnummer (municipal_code) om möjligt.
    """
    if isinstance(codes_or_names, str):
        codes_or_names = [codes_or_names]

    # Plocka ut GeoDataFrame för kommuner
    muni_gdf = geoworld.municipalities

    # Matcha på kod eller (del av) namn, case-insensitive
    selected = muni_gdf[
        muni_gdf["municipal_code"].isin(codes_or_names) |
        muni_gdf["municipality"].str.lower().str.contains('|'.join([v.lower() for v in codes_or_names]))
    ]

    if selected.empty:
        print("Inga matchande kommuner hittades!")
        return

    print("VALDA KOMMUNER:")
    print(selected[["municipal_code", "municipality"]])

    fig, ax = plt.subplots(figsize=(8, 8))

    colors = {
        "municipalities": "#ECECEC",
        "urban_areas": "#FF7F0E",
        "small_localities": "#FFD700",
        "business_zones": "#D62728",
        "commercial_zones": "#2CA02C",
        "leisure_house_zones": "#9467BD"
    }

    # Rita valda kommuner
    selected.plot(ax=ax, color=colors["municipalities"], edgecolor="#888888", linewidth=0.7, label="Kommun")

    # Rita overlay-lager, filtrerat på kommunnummer
    for layer in layers:
        if layer == "municipalities":
            continue
        if not hasattr(geoworld, layer):
            print(f"Warning: GeoWorld does not have layer '{layer}'.")
            continue
        gdf = getattr(geoworld, layer)
        if gdf.empty:
            print(f"Layer '{layer}' är tom.")
            continue

        # Försök hitta rätt kommunnummerkolumn
        muni_col = None
        for cand in ["municipality_code", "municipal_code"]:
            if cand in gdf.columns:
                muni_col = cand
                break

        if muni_col:
            hits = gdf[gdf[muni_col].isin(selected["municipal_code"])]
            print(f"Layer: {layer}, hittade {len(hits)} objekt för valda kommuner.")
        else:
            print(f"Layer '{layer}' saknar kolumn för kommunnummer – ritar hela lagret!")
            hits = gdf

        if not hits.empty:
            hits.plot(ax=ax, color=colors.get(layer, "#88888844"), edgecolor="#444444", linewidth=0.5, label=layer)

    ax.set_aspect("equal")
    ax.axis("off")
    plt.title("Valda kommuner och lager")
    # Endast unika labels i legend
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc="upper right")
    plt.tight_layout()
    plt.show()

# --- Användning ---
gw = GeoWorld("data/worm.sqlite3")
plot_selected_municipalities(
    gw,
    ["Falun", "Borlänge"],
    layers=("municipalities","urban_areas","small_localities","commercial_zones","business_zones")
)
