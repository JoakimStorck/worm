# plotting/plot_selected_municipalities.py

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import geopandas as gpd
from worm.geography.geoworld import GeoWorld

def plot_selected_municipalities(geoworld, codes_or_names, layers=("municipalities",), save_path=None, dpi=200, file_format=None):
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
        for cand in ["municipal_code", "municipal_code"]:
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

    legend_handles = [
        mpatches.Patch(color=colors["municipalities"], label="Municipality"),
    ]
    for layer in layers:
        if layer == "municipalities":
            continue
        if layer in colors:
            legend_handles.append(
                mpatches.Patch(color=colors[layer], label=layer.replace("_", " ").capitalize())
            )
    ax.legend(handles=legend_handles, loc="upper right")

    plt.tight_layout()

    # --- NYTT: Spara till fil om angivet ---
    if save_path:
        if file_format:
            plt.savefig(save_path, format=file_format, dpi=dpi)
        else:
            plt.savefig(save_path, dpi=dpi)
        print(f"Karta sparad till {save_path}")
    else:
        plt.show()
