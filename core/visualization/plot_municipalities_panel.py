import numpy as np
import pandas as pd

from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool, CheckboxGroup, CustomJS
from bokeh.layouts import row, column

from core.visualization.utils import gdf_to_bokeh_patches
from core.analysis.scenario_result import ScenarioResult

import geopandas as gpd
from shapely.geometry import Point, Polygon


def plot_selected_municipalities_bokeh_panel(
    muni_gdf,
    selected_codes_or_names,
    result: ScenarioResult,
    layers=None,         # ["municipalities", "urban_areas", "business_zones", ...]
    gdf_layers=None      # dict: {layer_namn: GeoDataFrame}
):
    if layers is None:
        layers = ["municipalities"]
    if gdf_layers is None:
        gdf_layers = {}

    # Färgkarta för lager
    colors = {
        "municipalities": "#ECECEC",
        "deso": "#4FC3F7",
        "urban_areas": "#FF7F0E",
        "small_localities": "#FFD700",
        "business_zones": "#D62728",
        "commercial_zones": "#2CA02C",
        "leisure_house_zones": "#9467BD",
        "employers": "#1f77b4",
        "individuals": "#000000",
    }

    # --- Skapa plot ---
    p = figure(
        title="Karta: valda lager",
        width=600, height=700,
        match_aspect=True,
        tools="lasso_select,box_select,reset,pan,wheel_zoom"
    )

    # --- Rita lager i ordning ---
    renderers = {}
    for layer in layers:
        if layer == "municipalities":
            selected = muni_gdf[
                muni_gdf["municipal_code"].isin(selected_codes_or_names) |
                muni_gdf["municipality"].str.lower().str.contains('|'.join([v.lower() for v in selected_codes_or_names]))
            ]
            if not selected.empty:
                source = ColumnDataSource(gdf_to_bokeh_patches(selected))
                #source = result.get_indiv_source()

                renderer = p.patches('xs', 'ys', source=source,
                                     fill_color=colors.get(layer, "#CCCCCC"),
                                     line_color="#888888",
                                     alpha=0.8, legend_label="Kommun")
                renderers[layer] = renderer
        else:
            gdf = gdf_layers.get(layer)
            if gdf is not None and not gdf.empty:
                # Välj kolumn att matcha på beroende på lager
                if layer == "deso":
                    col_candidates = ["deso_code"]    # <-- DeSO-filer brukar heta så!
                else:
                    col_candidates = ["municipal_code", "municipality_code"]
                muni_col = next((c for c in col_candidates if c in gdf.columns), None)
                # Filtrera rätt polygoner, annars rita allt
                if muni_col:
                    hits = gdf[gdf[muni_col].isin(selected_codes_or_names)]
                else:
                    hits = gdf
                if not hits.empty:
                    color = colors.get(layer, "#88888844")
                    patch_dict = gdf_to_bokeh_patches(hits)
                    source = ColumnDataSource(patch_dict)
                    renderer = p.patches(
                        'xs', 'ys', source=source,
                        fill_color=color, line_color="#444444", alpha=0.5,
                        legend_label=layer.replace("_", " ").capitalize()
                    )
                    renderers[layer] = renderer

    # --- Employers ---
    employers = result.get_employers() if hasattr(result, "get_employers") else getattr(result, "employers", None)
    if employers is not None and not employers.empty and "geometry" in employers.columns:
        x_emp = [pt.x for pt in employers.geometry]
        y_emp = [pt.y for pt in employers.geometry]
        emp_rend = p.scatter(x_emp, y_emp, size=12, color=colors["employers"], alpha=0.8, legend_label="Employers")
        renderers["employers"] = emp_rend

    # --- Individuals ---
    indiv_source = result.get_indiv_source()   # (Hantera geometry, x/y och cache internt)
    ind_rend = p.scatter('x', 'y', source=indiv_source, size=8, color=colors["individuals"], alpha=0.7, legend_label="Individuals", selection_color="orange")
    hover = HoverTool(tooltips=[("ID", "@individual_id")], renderers=[ind_rend])
    p.add_tools(hover)
    renderers["individuals"] = ind_rend

    p.legend.location = "top_left"
    p.legend.click_policy = "hide"

    # --- Lagerstyrning med CheckboxGroup ---
    checkbox_labels = [layer.replace("_", " ").capitalize() for layer in renderers.keys()]
    checkbox_group = CheckboxGroup(labels=checkbox_labels, active=list(range(len(checkbox_labels))))
    # Koppla visibilitet till checkboxar
    cb_code = ""
    for idx, layer in enumerate(renderers.keys()):
        cb_code += f"renderers[{idx}].visible = cb_obj.active.includes({idx});\n"
    callback = CustomJS(args={"renderers": list(renderers.values())}, code=cb_code)
    checkbox_group.js_on_change('active', callback)

    layout = row(p, column(checkbox_group))
    return layout
