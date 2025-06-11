import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon, Point
from bokeh.plotting import figure, show, output_file
from bokeh.models import ColumnDataSource, MultiPolygons, HoverTool, CustomJS, Div
from bokeh.layouts import column
from bokeh.palettes import Category10

# ---- DEMODATA: skapa exempeldata ----
# Skapa två låtsaskommuner (fyrkanter)
polys = [
    Polygon([(0,0), (0,10), (10,10), (10,0)]),      # Kommun 1
    Polygon([(12,2), (12,8), (20,8), (20,2)])       # Kommun 2
]
muni_gdf = gpd.GeoDataFrame({
    'municipal_code': ['2080', '2081'],
    'municipality': ['Falun', 'Borlänge'],
    'geometry': polys
})

# Urban area i Falun (rektangel inuti)
urban_gdf = gpd.GeoDataFrame({
    'municipal_code': ['2080'],
    'geometry': [Polygon([(2,2), (2,7), (8,7), (8,2)])]
})

# Individer och arbetsgivare (slump)
individuals_gdf = gpd.GeoDataFrame({
    'individual_id': [f'2080_i{i:06d}' for i in range(10)],
    'municipal_code': ['2080']*10,
    'geometry': [Point(np.random.uniform(2,8), np.random.uniform(2,7)) for _ in range(10)]
})
employers_gdf = gpd.GeoDataFrame({
    'employer_id': [f'2080_e{i:05d}' for i in range(5)],
    'municipal_code': ['2080']*5,
    'geometry': [Point(np.random.uniform(2,8), np.random.uniform(2,7)) for _ in range(5)]
})

# ---- KONVERTERA POLYGONER TILL BOKEH-format ----
def gdf_to_bokeh_patches(gdf):
    xs, ys = [], []
    for geom in gdf.geometry:
        if geom.type == 'Polygon':
            x, y = geom.exterior.xy
            xs.append(list(x))
            ys.append(list(y))
        elif geom.type == 'MultiPolygon':
            # Endast enklaste fallet: ta första polygonen
            x, y = list(geom.geoms[0].exterior.xy)
            xs.append(list(x))
            ys.append(list(y))
    return dict(xs=xs, ys=ys)

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

# ----------- DEMOANROP -----------
plot_selected_municipalities_bokeh(
    muni_gdf,
    selected_codes_or_names=["Falun"],
    layers=["municipalities", "urban_areas"],
    employers_gdf=employers_gdf,
    individuals_gdf=individuals_gdf,
)
