import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
from bokeh.plotting import figure, show, output_file
from bokeh.models import ColumnDataSource, CustomJS, Div
from bokeh.layouts import gridplot, column

# Ladda data
indiv_path = 'output/initial_state_individuals.csv'
job_path = 'output/initial_state_jobs.csv'

indiv = pd.read_csv(indiv_path)
jobs = pd.read_csv(job_path)

# Occupation space: x, y (kartesiskt)
indiv['x'] = indiv['chi'] * np.cos(indiv['xi'])
indiv['y'] = indiv['chi'] * np.sin(indiv['xi'])
jobs['x'] = jobs['chi'] * np.cos(jobs['xi'])
jobs['y'] = jobs['chi'] * np.sin(jobs['xi'])

# Anta kartkoordinater (byt till rätt kolumnnamn om det skiljer sig!)
# Om du har SWEREF99 eller UTM-koordinater i indiv, använd dem istället.
if 'lon' in indiv.columns and 'lat' in indiv.columns:
    indiv['x_map'] = indiv['lon']
    indiv['y_map'] = indiv['lat']
else:
    raise Exception("Din individ-data behöver kolumner för karta, t.ex. 'lon' och 'lat'.")

indiv_source = ColumnDataSource(indiv)
job_source = ColumnDataSource(jobs)

# Occupation space-plot
p_occ = figure(
    title="Occupation space (chi, xi)",
    width=600, height=600,
    tools=["lasso_select", "box_select", "reset", "pan", "wheel_zoom", "tap"],
    match_aspect=True,
)
p_occ.circle('x', 'y', source=indiv_source, size=7, color="red", alpha=0.6, legend_label="Individer", selection_color="orange")
p_occ.circle('x', 'y', source=job_source, size=5, color="blue", alpha=0.3, legend_label="Jobb", selection_color="green")
p_occ.legend.location = "top_left"
p_occ.legend.click_policy = "hide"

# Karta-plot
p_map = figure(
    title="Karta: individer (markerbar)",
    width=600, height=600,
    tools=["lasso_select", "box_select", "reset", "pan", "wheel_zoom", "tap"],
    match_aspect=True,
)
# Här kan du lägga till bas-karta (t ex med TileRenderer för OpenStreetMap, om du har longitud/latitud)
# p_map.add_tile(get_provider(Vendors.CARTODBPOSITRON))  # kräver bokeh.tile_providers

p_map.circle('x_map', 'y_map', source=indiv_source, size=7, color="red", alpha=0.6, selection_color="orange")

# Textdiv som visar markerade individers ID
div = Div(text="""<b>Markerade individer:</b> Ingen""", width=400)
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

# Gridplot med occupation space och karta sida vid sida
layout = column(
    gridplot([[p_occ, p_map]]),
    div
)

output_file("occupation_space_linked_map.html")
show(layout)
