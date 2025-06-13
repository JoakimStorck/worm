import numpy as np
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool

def plot_occupation_space_panel(
    result,
    selected_inds=None,
    highlight_inds=None,
    show_pathways=False,
    show_H_circle=False,
    tools="lasso_select,box_select,reset,pan,wheel_zoom",
    width=500,
    height=700
):
    """
    Skapar en Bokeh-panel med occupation space från ScenarioResult.

    - selected_inds: lista med individ-ID:n att highlighta (externt urval)
    - highlight_inds: lista med individ-ID:n att visa extra tydligt (t.ex. pathways)
    - show_pathways: visa pathways om dessa finns i ScenarioResult
    - show_H_circle: visa H-cirkel för individer om kolumnen H finns
    """
    indiv = result.get_individuals().copy()
    jobs = result.get_jobs().copy()

    # Hantera ev. geometri-kolumn
    for df in [indiv, jobs]:
        if "geometry" in df.columns:
            df.drop(columns=["geometry"], inplace=True)

    # Beräkna kartesiska koordinater
    # indiv["x_occ"] = indiv["chi"] * np.cos(indiv["xi"])
    # indiv["y_occ"] = indiv["chi"] * np.sin(indiv["xi"])
    # jobs["x_occ"] = jobs["chi"] * np.cos(jobs["xi"])
    # jobs["y_occ"] = jobs["chi"] * np.sin(jobs["xi"])

    # Skapa ColumnDataSource
    indiv_source = source = result.get_indiv_source()
    job_source = result.get_job_source()

    p = figure(
        title="Occupation space",
        width=width,
        height=height,
        match_aspect=True,
        tools=tools
    )

    # Punkter för individer (selection=linked brushing)
    indiv_renderer = p.scatter(
        'x_occ', 'y_occ',
        source=indiv_source,
        color="red",
        alpha=0.6,
        size=8,
        legend_label="Individer",
        selection_color="orange"
    )

    # Punkter för jobb
    p.scatter(
        'x_occ', 'y_occ',
        source=job_source,
        color="blue",
        alpha=0.3,
        size=5,
        legend_label="Jobb",
        selection_color="green"
    )

    # --- (Plats för pathways och H-cirklar om så önskas) ---
    # if show_pathways and hasattr(result, "get_pathways"):
    #     pass

    # if show_H_circle and "H" in indiv.columns:
    #     pass

    p.add_tools(HoverTool(tooltips=[("ID", "@individual_id")], renderers=[indiv_renderer]))
    p.legend.location = "top_left"
    p.legend.click_policy = "hide"

    return p, indiv_source
