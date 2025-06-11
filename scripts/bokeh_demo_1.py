import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
from bokeh.plotting import figure, show, output_file
from bokeh.models import ColumnDataSource, LassoSelectTool, BoxSelectTool, CustomJS, Div
from bokeh.layouts import column, row

# Ladda data
indiv_path = 'output/initial_state_individuals.csv'
job_path = 'output/initial_state_jobs.csv'

indiv = pd.read_csv(indiv_path)
jobs = pd.read_csv(job_path)

# Skapa kartsiska scatterdata (vi antar xi = vinkel, chi = radie)
# Om du vill visa i polärt kan vi konvertera: x = chi * cos(xi), y = chi * sin(xi)
indiv['x'] = indiv['chi'] * np.cos(indiv['xi'])
indiv['y'] = indiv['chi'] * np.sin(indiv['xi'])
jobs['x'] = jobs['chi'] * np.cos(jobs['xi'])
jobs['y'] = jobs['chi'] * np.sin(jobs['xi'])

indiv_source = ColumnDataSource(indiv)
job_source = ColumnDataSource(jobs)

p = figure(
    title="Occupation space: Individer (röd) och jobb (blå) - interaktivt",
    width=800, height=600,
    tools=["lasso_select", "box_select", "reset", "pan", "wheel_zoom", "tap"],
    match_aspect=True,
)

# Individer (röd)
p.circle('x', 'y', source=indiv_source, size=7, color="red", alpha=0.6, legend_label="Individer", selection_color="orange")

# Jobb (blå)
p.circle('x', 'y', source=job_source, size=5, color="blue", alpha=0.3, legend_label="Jobb", selection_color="green")

p.legend.location = "top_left"
p.legend.click_policy = "hide"

# Textdiv som visar markerade individers ID
div = Div(text="""<b>Markerade individer:</b> Ingen""", width=400)

# JS callback för att visa markerade ID:n
callback = CustomJS(args=dict(source=indiv_source, div=div), code="""
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
""")
indiv_source.selected.js_on_change('indices', callback)

layout = column(p, div)
output_file("occupation_space_interactive.html")
show(layout)
