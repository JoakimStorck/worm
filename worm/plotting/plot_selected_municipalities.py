# plotting/plot_selected_municipalities.py

from worm.statistics.log import log

def plot_selected_municipalities(
    geoworld,
    municipal_codes_or_names,
    layers=("municipalities",),
    employers_gdf=None,
    individuals_gdf=None,
    save_path=None,
    dpi=200,
    file_format=None,
    show=True
):
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    if isinstance(municipal_codes_or_names, str):
        municipal_codes_or_names = [municipal_codes_or_names]
    municipal_codes_or_names = [str(v) for v in municipal_codes_or_names]

    muni_gdf = geoworld.municipalities

    selected = muni_gdf[
        muni_gdf["municipal_code"].isin(municipal_codes_or_names) |
        muni_gdf["municipality"].str.lower().str.contains('|'.join([v.lower() for v in municipal_codes_or_names]))
    ]
    if selected.empty:
        log("Inga matchande kommuner hittades!")
        return

    log("VALDA KOMMUNER:")
    log(selected[["municipal_code", "municipality"]])

    fig, ax = plt.subplots(figsize=(10, 10))

    colors = {
        "municipalities": "#ECECEC",
        "urban_areas": "#FF7F0E",
        "small_localities": "#FFD700",
        "business_zones": "#D62728",
        "commercial_zones": "#2CA02C",
        "leisure_house_zones": "#9467BD",
        "employers": "#1f77b4",
        "individuals": "#000000",
    }

    # Rita polygonlager
    selected.plot(ax=ax, color=colors["municipalities"], edgecolor="#888888", linewidth=0.7, label="Kommun")
    for layer in layers:
        if layer == "municipalities":
            continue
        if hasattr(geoworld, layer):
            gdf = getattr(geoworld, layer)
            if gdf.empty:
                continue
            muni_col = next((c for c in ["municipal_code", "municipality_code"] if c in gdf.columns), None)
            if muni_col:
                hits = gdf[gdf[muni_col].isin(selected["municipal_code"])]
            else:
                hits = gdf
            if not hits.empty:
                hits.plot(ax=ax, color=colors.get(layer, "#88888844"), edgecolor="#444444", linewidth=0.5, label=layer)
        if layer == "employers" and employers_gdf is not None:
            employers_gdf.plot(ax=ax, color=colors["employers"], markersize=6, alpha=0.7, label="Employers", zorder=10)
        if layer == "individuals" and individuals_gdf is not None:
            individuals_gdf.plot(ax=ax, color=colors["individuals"], markersize=2, alpha=0.5, label="Individuals", zorder=11)

    ax.set_aspect("equal")
    ax.axis("off")
    plt.title("Valda kommuner och lager")

    legend_handles = [
        mpatches.Patch(color=colors["municipalities"], label="Municipality"),
    ]
    for layer in layers:
        if layer == "municipalities":
            continue
        if layer in colors:
            if layer in ["employers", "individuals"]:
                legend_handles.append(
                    mpatches.Patch(color=colors[layer], label=layer.capitalize())
                )
            else:
                legend_handles.append(
                    mpatches.Patch(color=colors[layer], label=layer.replace("_", " ").capitalize())
                )
    ax.legend(handles=legend_handles, loc="upper right")

    plt.tight_layout()
    if save_path:
        if file_format:
            plt.savefig(save_path, format=file_format, dpi=dpi)
        else:
            plt.savefig(save_path, dpi=dpi)
        log(f"Karta sparad till {save_path}")
    if show:
        plt.show()
