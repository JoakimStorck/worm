# plotting/plot_selected_municipalities.py

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon, Point
from bokeh.plotting import figure, show, output_file
from bokeh.models import ColumnDataSource, MultiPolygons, HoverTool, CustomJS, Div
from bokeh.layouts import column
from bokeh.palettes import Category10
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


from core.statistics.log import log

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

# ---- PLOTNING ----
def plot_selected_municipalities_bokeh(
    muni_gdf,
    selected_codes_or_names,
    layers=None,
    employers_gdf=None,
    individuals_gdf=None
):
    if layers is None:
        layers = ["municipalities"]

    # Filtrera kommuner
    selected = muni_gdf[
        muni_gdf["municipal_code"].isin(selected_codes_or_names) |
        muni_gdf["municipality"].str.lower().str.contains('|'.join([v.lower() for v in selected_codes_or_names]))
    ]
    if selected.empty:
        print("Inga matchande kommuner hittades!")
        return

    # Bokeh-plot
    p = figure(title="Valda kommuner och lager (interaktiv)", width=700, height=700, match_aspect=True, tools="pan,wheel_zoom,reset")

    # Färgkarta
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

    # 1. Kommun-polygoner
    muni_source = ColumnDataSource(gdf_to_bokeh_patches(selected))
    p.patches('xs', 'ys', source=muni_source, fill_color=colors["municipalities"], line_color="#888888", alpha=0.8, legend_label="Kommun")

    # 2. Urban area-lager, om det finns
    if "urban_areas" in layers:
        try:
            urban_gdf_sel = urban_gdf[urban_gdf["municipal_code"].isin(selected["municipal_code"])]
            if not urban_gdf_sel.empty:
                urban_source = ColumnDataSource(gdf_to_bokeh_patches(urban_gdf_sel))
                p.patches('xs', 'ys', source=urban_source, fill_color=colors["urban_areas"], line_color="#444444", alpha=0.5, legend_label="Urban area")
        except Exception as e:
            print(e)

    # 3. Employers som scatter
    if employers_gdf is not None and not employers_gdf.empty:
        p.scatter(
            [pt.x for pt in employers_gdf.geometry], [pt.y for pt in employers_gdf.geometry],
            size=12, color=colors["employers"], alpha=0.8, legend_label="Employers"
        )

    # 4. Individuals som scatter, interaktiv markering
    indiv_ids = []
    indiv_x, indiv_y = [], []
    if individuals_gdf is not None and not individuals_gdf.empty:
        indiv_ids = individuals_gdf['individual_id'].tolist()
        indiv_x = [pt.x for pt in individuals_gdf.geometry]
        indiv_y = [pt.y for pt in individuals_gdf.geometry]
        indiv_source = ColumnDataSource(data=dict(x=indiv_x, y=indiv_y, individual_id=indiv_ids))
        renderer = p.scatter('x', 'y', source=indiv_source, size=8, color=colors["individuals"], alpha=0.7, legend_label="Individuals", selection_color="orange")
        # Hover och urvalsvisning
        hover = HoverTool(tooltips=[("ID", "@individual_id")], renderers=[renderer])
        p.add_tools(hover)

        div = Div(text="<b>Markerade individer:</b> Ingen")
        indiv_source.selected.js_on_change('indices', CustomJS(args=dict(source=indiv_source, div=div), code="""
            var inds = cb_obj.indices;
            var data = source.data;
            var txt = "<b>Markerade individer:</b> ";
            if (inds.length == 0) {
                txt += "Ingen";
            } else {
                var ids = [];
                for (var i = 0; i < inds.length; i++) {
                    ids.push(data['individual_id'][inds[i]]);
                }
                txt += ids.join(", ");
            }
            div.text = txt;
        """))
        layout = column(p, div)
    else:
        layout = column(p)

    p.legend.location = "top_left"
    p.legend.click_policy = "hide"

    output_file("bokeh_selected_municipalities.html")
    show(layout)
