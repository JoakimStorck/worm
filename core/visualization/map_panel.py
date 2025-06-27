# core/visualization/map_panel.py

import numpy as np
import pandas as pd
import geopandas as gpd
from bokeh.plotting import figure
from bokeh.models import (
    ColumnDataSource, HoverTool, CheckboxGroup, CustomJS,
    Button, TabPanel
)
from bokeh.layouts import row, column
from bokeh.io import curdoc

from core.visualization.selection_sync import sync_selections
from core.visualization.utils import gdf_to_bokeh_patches, gdf_points_to_xy
from core.ui_state import UIState

def make_panel(
    replay_controller,
    muni_gdf,
    selected_codes_or_names,
    layers,
    gdf_layers,
    ui_state,
    indiv_source,
    emp_source,
    job_source
):
    panel = MapPanel(
        replay_controller,
        muni_gdf,
        selected_codes_or_names,
        layers=layers,
        gdf_layers=gdf_layers,
        ui_state=ui_state,
        indiv_source=indiv_source,
        emp_source=emp_source,
        job_source=job_source
    )
    return TabPanel(child=panel.layout, title="Karta")

class MapPanel:
    def __init__(
        self,
        replay_controller,
        muni_gdf,
        selected_codes_or_names,
        layers=None,
        gdf_layers=None,
        tools="tap,lasso_select,box_select,box_zoom,reset,pan,wheel_zoom,save",
        ui_state=None,
        indiv_source=None,
        emp_source=None,
        job_source=None,
    ):
        self.replay = replay_controller
        self.muni_gdf = muni_gdf
        self.selected_codes_or_names = selected_codes_or_names
        self.layers = layers or ["municipalities"]
        self.gdf_layers = gdf_layers or {}
        self.tools = tools
        self.ui_state = ui_state
        self.indiv_source = indiv_source
        self.emp_source = emp_source
        self.job_source = job_source

        # Renderers för punktlager (måste alltid finnas)
        self.emp_renderer = None
        self.job_renderer = None
        self.indiv_renderer = None

        # Kopplingslinjer individ-jobb
        self.employment_lines_source = ColumnDataSource(data=dict(xs=[], ys=[]))

        # Checkbox för hover
        self.show_hover_checkbox = CheckboxGroup(labels=["Visa ID vid hover"], active=[])
        self.hover = None

        self._build_panel()

        if self.ui_state:
            self.ui_state.subscribe(self.set_hover_visibility)
        self.show_hover_checkbox.on_change("active", self.on_checkbox_change)
        self.replay.subscribe(self.update)

    def _build_panel(self):
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
            "jobs": "#00aaff",
        }

        # Filtrera valda kommuner för att sätta zoom-bounds
        selected_names = [v.lower() for v in self.selected_codes_or_names if isinstance(v, str)]
        if selected_names:
            name_mask = self.muni_gdf["municipality"].str.lower().str.contains('|'.join(selected_names))
        else:
            name_mask = False

        selected = self.muni_gdf[
            self.muni_gdf["municipal_code"].isin(self.selected_codes_or_names) |
            name_mask
        ]

        if not selected.empty:
            bounds = selected.total_bounds  # [minx, miny, maxx, maxy]
            margin_x = (bounds[2] - bounds[0]) * 0.05
            margin_y = (bounds[3] - bounds[1]) * 0.05
        else:
            bounds = [0, 0, 1, 1]
            margin_x = margin_y = 0

        self.figure = figure(
            title="Karta: valda lager",
            match_aspect=True,
            tools=self.tools,
            sizing_mode="stretch_both",
            aspect_ratio=1,
            height=800,
            x_range=(bounds[0] - margin_x, bounds[2] + margin_x),
            y_range=(bounds[1] - margin_y, bounds[3] + margin_y),
        )

        self.renderers = {}

        # Polygonlager
        for layer in self.layers:
            if layer == "municipalities":
                selected = self.muni_gdf[
                    self.muni_gdf["municipal_code"].isin(self.selected_codes_or_names) |
                    self.muni_gdf["municipality"].str.lower().str.contains('|'.join([v.lower() for v in self.selected_codes_or_names]))
                ]
                if not selected.empty:
                    source = ColumnDataSource(gdf_to_bokeh_patches(selected))
                    renderer = self.figure.patches(
                        'xs', 'ys', source=source,
                        fill_color=colors.get(layer, "#CCCCCC"),
                        line_color="#888888",
                        alpha=0.8, legend_label="Kommun"
                    )
                    self.renderers[layer] = renderer
            else:
                gdf = self.gdf_layers.get(layer)
                if gdf is not None and not gdf.empty:
                    if layer == "deso":
                        col_candidates = ["deso_code"]
                    else:
                        col_candidates = ["municipal_code", "municipality_code"]
                    muni_col = next((c for c in col_candidates if c in gdf.columns), None)
                    if muni_col:
                        hits = gdf[gdf[muni_col].isin(self.selected_codes_or_names)]
                    else:
                        hits = gdf
                    if not hits.empty:
                        color = colors.get(layer, "#88888844")
                        patch_dict = gdf_to_bokeh_patches(hits)
                        source = ColumnDataSource(patch_dict)
                        renderer = self.figure.patches(
                            'xs', 'ys', source=source,
                            fill_color=color, line_color="#444444", alpha=0.5,
                            legend_label=layer.replace("_", " ").capitalize()
                        )
                        self.renderers[layer] = renderer

        self.show_employment_lines = CheckboxGroup(labels=["Visa jobb-linjer"], active=[])
        self.show_employment_lines.on_change("active", lambda attr, old, new: self.update_points())

        # Punktlager: Employers, Jobs, Individuals
        self.update_points()  # Skapar alla renderers och sources

        # Skapa lagerlistan för CheckboxGroup
        point_offset = len(self.renderers)
        checkbox_labels = [layer.replace("_", " ").capitalize() for layer in self.renderers.keys()]
        checkbox_labels += ["Jobb", "Individer", "Arbetsgivare"]
        self.checkbox_group = CheckboxGroup(labels=checkbox_labels, active=list(range(len(checkbox_labels))))

        # Synlighet med CustomJS
        cb_code = ""
        for idx, layer in enumerate(self.renderers.keys()):
            cb_code += f"renderers[{idx}].visible = cb_obj.active.includes({idx});\n"
        cb_code += f"if (renderers_job) {{ renderers_job.visible = cb_obj.active.includes({point_offset}); }}\n"
        cb_code += f"if (renderers_indiv) {{ renderers_indiv.visible = cb_obj.active.includes({point_offset+1}); }}\n"
        cb_code += f"if (renderers_emp) {{ renderers_emp.visible = cb_obj.active.includes({point_offset+2}); }}\n"

        callback = CustomJS(args={
            "renderers": list(self.renderers.values()),
            "renderers_job": self.job_renderer,
            "renderers_indiv": self.indiv_renderer,
            "renderers_emp": self.emp_renderer
        }, code=cb_code)
        self.checkbox_group.js_on_change('active', callback)

        # Hover för individer (kan utökas)
        if self.indiv_renderer:
            self.hover = HoverTool(tooltips=[("ID", "@individual_id")], renderers=[self.indiv_renderer])

        self.figure.legend.location = "top_left"
        self.figure.legend.click_policy = "hide"

        self.zoom_button = Button(label="Zooma till valda kommuner", width=220)
        self.zoom_button.on_click(self.zoom_to_selected)

        self.lines_renderer = self.figure.multi_line(
            xs="xs", ys="ys",
            source=self.employment_lines_source,
            line_color="black", line_alpha=0.08, line_width=1
        )


        # Layout för kontrollpanelen
        control_column = column(
            self.checkbox_group, 
            self.show_employment_lines, 
            self.show_hover_checkbox, 
            self.zoom_button, 
            width=220
        )
        # Layout för hela panelen
        self.layout = row(
            self.figure,
            control_column,
            sizing_mode="stretch_both",
            height=800,
        )

        curdoc().add_next_tick_callback(self.zoom_to_selected)
        curdoc().add_next_tick_callback(self._lock_range)
        self.zoom_to_selected()

    def _lock_range(self):
        self.figure.x_range.bounds = (self.figure.x_range.start, self.figure.x_range.end)
        self.figure.y_range.bounds = (self.figure.y_range.start, self.figure.y_range.end)

    def zoom_to_selected(self):
        selected = self.muni_gdf[
            self.muni_gdf["municipal_code"].isin(self.selected_codes_or_names) |
            self.muni_gdf["municipality"].str.lower().str.contains('|'.join([v.lower() for v in self.selected_codes_or_names]))
        ]
        if not selected.empty:
            bounds = selected.total_bounds  # [minx, miny, maxx, maxy]
            margin_x = (bounds[2] - bounds[0]) * 0.05
            margin_y = (bounds[3] - bounds[1]) * 0.05
            self.figure.x_range.start = bounds[0] - margin_x
            self.figure.x_range.end   = bounds[2] + margin_x
            self.figure.y_range.start = bounds[1] - margin_y
            self.figure.y_range.end   = bounds[3] + margin_y

        self.figure.x_range.bounds = (self.figure.x_range.start, self.figure.x_range.end)
        self.figure.y_range.bounds = (self.figure.y_range.start, self.figure.y_range.end)

    def update_points(self):
        state = self.replay.get_state()

        # --- EMPLOYERS ---
        employers = state.get("employers")
        if employers is not None and not employers.empty:
            emp_df = gdf_points_to_xy(employers, id_col="employer_id")
            if self.emp_source is None:
                self.emp_source = ColumnDataSource(emp_df)
            else:
                self.emp_source.data = emp_df.to_dict("list")
            if not self.emp_renderer:
                self.emp_renderer = self.figure.scatter(
                    "x", "y", source=self.emp_source, size=12,
                    color="#1f77b4", alpha=0.8, legend_label="Arbetsgivare",
                    marker="diamond", selection_color="#ff00ff", nonselection_alpha=0.12
                )

        # --- JOBS ---
        jobs = state.get("jobs")
        if jobs is not None and not jobs.empty:
            job_df = gdf_points_to_xy(jobs, id_col="job_id")
            if self.job_source is None:
                self.job_source = ColumnDataSource(job_df)
            else:
                self.job_source.data = job_df.to_dict("list")
            if not self.job_renderer:
                self.job_renderer = self.figure.scatter(
                    'x', 'y', source=self.job_source, size=8,
                    color="#00aaff", alpha=0.7, legend_label="Jobb",
                    selection_color="yellow", nonselection_alpha=0.15
                )

        # --- INDIVIDUALS ---
        individuals = state.get("individuals")
        if individuals is not None and not individuals.empty:
            indiv_df = gdf_points_to_xy(individuals, id_col="individual_id")
            if self.indiv_source is None:
                self.indiv_source = ColumnDataSource(indiv_df)
            else:
                self.indiv_source.data = indiv_df.to_dict("list")
            if not self.indiv_renderer:
                self.indiv_renderer = self.figure.scatter(
                    'x', 'y', source=self.indiv_source, size=5,
                    color="#000000", alpha=0.3, legend_label="Individer",
                    selection_color="orange", nonselection_alpha=0.08
                )

        # Hantera linjer mellan individer och jobb
        if 0 in getattr(self.show_employment_lines, "active", []):
            indivs = pd.DataFrame(self.indiv_source.data)
            jobs = pd.DataFrame(self.job_source.data)
            jobs_dict = {j["job_id"]: (j["x"], j["y"]) for j in jobs.to_dict("records")}
            xs, ys = [], []
            for _, row in indivs.iterrows():
                jid = row.get("job_id")
                if jid and jid in jobs_dict:
                    xs.append([row["x"], jobs_dict[jid][0]])
                    ys.append([row["y"], jobs_dict[jid][1]])
            self.employment_lines_source.data = dict(xs=xs, ys=ys)
        else:
            self.employment_lines_source.data = dict(xs=[], ys=[])

        # Koppla selection sync
        if self.emp_source and self.job_source and self.indiv_source:
            sync_selections(self.emp_source, self.job_source, self.indiv_source)

    def update(self):
        print("Updating Map Panel...")
        self.update_points()
        self.zoom_to_selected()

    def on_checkbox_change(self, attr, old, new):
        if self.ui_state:
            self.ui_state.set_show_hover(0 in new)

    def set_hover_visibility(self, visible: bool):
        if visible:
            if self.hover and self.hover not in self.figure.tools:
                self.figure.add_tools(self.hover)
        else:
            if self.hover and self.hover in self.figure.tools:
                self.figure.tools.remove(self.hover)
