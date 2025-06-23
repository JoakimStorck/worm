# core/visualization/map_panel.py

import numpy as np
import pandas as pd
import geopandas as gpd
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool, CheckboxGroup, CustomJS
from bokeh.models import Button, TabPanel
from bokeh.io import curdoc

from bokeh.layouts import row, column
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
):
    panel = MapPanel(
        replay_controller,
        muni_gdf,
        selected_codes_or_names,
        layers=layers,
        gdf_layers=gdf_layers,
        ui_state=ui_state,
        indiv_source=indiv_source,
        emp_source=emp_source
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
        tools="lasso_select,box_select,box_zoom,reset,pan,wheel_zoom,save",
        ui_state=None,
        indiv_source=None,
        emp_source=None,
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

        # Punktlager: Employers och Individuals
        self.emp_renderer = None
        self.indiv_renderer = None
        self.update_points()

        # Hover för individer
        if self.indiv_renderer:
            self.hover = HoverTool(tooltips=[("ID", "@individual_id")], renderers=[self.indiv_renderer])

        self.figure.legend.location = "top_left"
        self.figure.legend.click_policy = "hide"

        # Lagerstyrning: CheckboxGroup
        checkbox_labels = [layer.replace("_", " ").capitalize() for layer in self.renderers.keys()]
        self.checkbox_group = CheckboxGroup(labels=checkbox_labels, active=list(range(len(checkbox_labels))))
        cb_code = ""
        for idx, layer in enumerate(self.renderers.keys()):
            cb_code += f"renderers[{idx}].visible = cb_obj.active.includes({idx});\n"
        callback = CustomJS(args={"renderers": list(self.renderers.values())}, code=cb_code)
        self.checkbox_group.js_on_change('active', callback)

        self.zoom_button = Button(label="Zooma till valda kommuner", width=220)
        self.zoom_button.on_click(self.zoom_to_selected)

        # I _build_panel
        control_column = column(self.checkbox_group, self.show_hover_checkbox, self.zoom_button, width=220)
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
        # EMPLOYERS
        state = self.replay.get_state()
        employers = state.get("employers")
        if employers is not None and not employers.empty:
            emp_df = gdf_points_to_xy(employers, id_col="employer_id")
            if self.emp_source is None:
                self.emp_source = ColumnDataSource(emp_df)
            else:
                self.emp_source.data = emp_df.to_dict("list")
            if not self.emp_renderer:
                self.emp_renderer = self.figure.scatter(
                    "x", "y", source=self.emp_source, size=8,
                    color="#1f77b4", alpha=0.7, legend_label="Employers", marker="diamond"
                )

        # INDIVIDUALS
        if self.indiv_source is None:
            self.indiv_source = self.replay.get_indiv_source()
        else:
            self.indiv_source.data = dict(self.replay.get_indiv_source().data)
        if not self.indiv_renderer:
            self.indiv_renderer = self.figure.scatter(
                'x', 'y', source=self.indiv_source, size=3,
                color="#000000", alpha=0.4, legend_label="Individuals",
                selection_color="orange"
            )

    def update(self):
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
