# core/visualization/map_panel.py

import numpy as np
import pandas as pd
import geopandas as gpd
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool, CheckboxGroup, CustomJS
from bokeh.models import Button
from bokeh.io import curdoc

from bokeh.layouts import row, column
from core.visualization.utils import gdf_to_bokeh_patches, gdf_points_to_xy
from core.ui_state import UIState

class MapPanel:
    KWARGS = ['replay_controller', 'muni_gdf', 'selected_codes_or_names', 'layers', 'gdf_layers', 'width', 'height', 'tools', 'ui_state']
    def __init__(
        self,
        replay_controller,
        muni_gdf,
        selected_codes_or_names,
        layers=None,
        gdf_layers=None,
        width=600,
        height=700,
        tools="lasso_select,box_select,box_zoom,reset,pan,wheel_zoom",
        ui_state=None
    ):
        self.replay = replay_controller
        self.muni_gdf = muni_gdf
        self.selected_codes_or_names = selected_codes_or_names
        self.layers = layers or ["municipalities"]
        self.gdf_layers = gdf_layers or {}
        self.width = width
        self.height = height
        self.tools = tools
        self.ui_state = ui_state

        # Kontroll
        print(muni_gdf.crs)

        # Checkbox för hover med id
        self.show_hover_checkbox = CheckboxGroup(labels=["Visa ID vid hover"], active=[])
        self.hover = None  # Sätts i _build_panel()

        # Initiera
        self._build_panel()

        if self.ui_state:
            self.ui_state.subscribe(self.set_hover_visibility)
        self.show_hover_checkbox.on_change("active", self.on_checkbox_change)

        # Koppla till replay
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


        print("Valda kommuner (selected_codes_or_names):", self.selected_codes_or_names)
        print("Typ på varje:", [type(x) for x in self.selected_codes_or_names])
        print("Antal rader i muni_gdf:", len(self.muni_gdf))
        print("Kommunkoder i muni_gdf:", self.muni_gdf["municipal_code"].unique())

        # Skapa lista av bara strängar (kommunnamn)
        selected_names = [v.lower() for v in self.selected_codes_or_names if isinstance(v, str)]
        if selected_names:
            name_mask = self.muni_gdf["municipality"].str.lower().str.contains('|'.join(selected_names))
        else:
            name_mask = False  # Eller: name_mask = pd.Series([False] * len(self.muni_gdf))

        selected = self.muni_gdf[
            self.muni_gdf["municipal_code"].isin(self.selected_codes_or_names) |
            name_mask
        ]

        if not selected.empty:
            bounds = selected.total_bounds  # [minx, miny, maxx, maxy]
            margin_x = (bounds[2] - bounds[0]) * 0.05
            margin_y = (bounds[3] - bounds[1]) * 0.05

        # Exempel: bounds = [minx, miny, maxx, maxy]

        self.figure = figure(
            title="Karta: valda lager",
            width=self.width,
            height=self.height,
            match_aspect=True,
            tools=self.tools,
            x_range=(bounds[0] - margin_x, bounds[2] + margin_x),
            y_range=(bounds[1] - margin_y, bounds[3] + margin_y)
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
                    renderer = self.figure.patches('xs', 'ys', source=source,
                                                   fill_color=colors.get(layer, "#CCCCCC"),
                                                   line_color="#888888",
                                                   alpha=0.8, legend_label="Kommun")
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

        # Points: Employers och Individuals läses ur REPLAY
        self.emp_renderer = None
        self.indiv_renderer = None
        self.emp_source = None
        self.indiv_source = None
        self.update_points()

        # Hover och legend
        if self.indiv_renderer:
            if self.indiv_renderer:
                self.hover = HoverTool(tooltips=[("ID", "@individual_id")], renderers=[self.indiv_renderer])
                # Lägg INTE till hover här ännu

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
        def zoom_callback():
            self.zoom_to_selected()
        self.zoom_button.on_click(zoom_callback)


        # Lägg till i layout sist i _build_panel
        self.layout = row(self.figure, column(self.checkbox_group, self.show_hover_checkbox, self.zoom_button))

        curdoc().add_next_tick_callback(self.zoom_to_selected)
        curdoc().add_next_tick_callback(self._lock_range)

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

        print("Zoom bounds:", bounds)
        print("x_range före:", self.figure.x_range.start, self.figure.x_range.end)
        print("y_range före:", self.figure.y_range.start, self.figure.y_range.end)


    def update_points(self):
        # EMPLOYERS
        state = self.replay.get_state()
        employers = state["employers"] if "employers" in state else None
        if employers is not None and not employers.empty:
            emp_df = gdf_points_to_xy(employers, id_col="employer_id")
            self.emp_source = ColumnDataSource(emp_df)
            if not self.emp_renderer:
                self.emp_renderer = self.figure.scatter(
                    "x", "y", source=self.emp_source, size=6,
                    color="#1f77b4", alpha=0.6, legend_label="Employers"
                )
            else:
                self.emp_renderer.data_source.data = emp_df.to_dict("list")

        # INDIVIDUALS
        if self.indiv_source is None:
            self.indiv_source = self.replay.get_indiv_source()
            self.indiv_renderer = self.figure.scatter(
                'x', 'y', source=self.indiv_source, size=3,
                color="#000000", alpha=0.4, legend_label="Individuals",
                selection_color="orange"
            )
        else:
            # Uppdatera bara datan i den redan delade källan
            self.indiv_source.data = self.replay.get_indiv_source().data


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


