# core/visualization/occupation_space_panel.py

import numpy as np
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool
from bokeh.models import Dropdown, CheckboxGroup, CustomJS

from core.ui_state import UIState
from core.visualization.utils import add_occ_coordinates

from bokeh.models import MultiSelect

class OccupationSpacePanel:
    KWARGS = ['replay_controller', 'show_jobs', 'show_pathways', 'show_H_circle', 'width', 'height', 'tools', 'ui_state']
    def __init__(
        self,
        replay_controller,
        show_jobs=True,
        show_pathways=False,
        show_H_circle=False,
        width=500,
        height=700,
        tools="lasso_select,box_select,reset,pan,wheel_zoom",
        ui_state=None
    ):
        self.replay = replay_controller
        self.show_jobs = show_jobs
        self.show_pathways = show_pathways
        self.show_H_circle = show_H_circle
        self.width = width
        self.height = height
        self.tools = tools

        self.ui_state = ui_state

        # Initierar datakällor
        self.indiv_source = replay_controller.get_indiv_source()
        self.job_source = ColumnDataSource(self._get_job_data().to_dict("list")) if show_jobs else None

        # Skapar plot
        self.plot = figure(
            title="Occupation Space",
            width=self.width,
            height=self.height,
            match_aspect=True,
            tools=self.tools
        )

        from bokeh.transform import factor_cmap

        # Lägg till detta före skapandet av scatter:
        statuses = ["employed", "unemployed", "not_in_labor_force"]
        palette = ["green", "red", "gray"]

        self.indiv_renderer = self.plot.scatter(
            'x_occ', 'y_occ',
            source=self.indiv_source,
            color=factor_cmap('status', palette=palette, factors=statuses),
            alpha=0.4,
            size=3,
            legend_field="status",        # så att legend visar färgerna
            selection_color="orange"
        )

        # Jobb
        if self.show_jobs and self.job_source:
            self.plot.scatter(
                'x_occ', 'y_occ',
                source=self.job_source,
                color="blue",
                alpha=0.6,
                size=6,
                legend_label="Jobb",
                selection_color="green"
            )

        self.status_select = MultiSelect(
            title="Visa status:",
            value=statuses,     # Start med alla valda
            options=[(s, s.capitalize()) for s in statuses]
        )

        self.status_select.on_change("value", lambda attr, old, new: self.update())

        # Pathways och H-cirklar – reserverat för utbyggnad

        # Hover och legend
        # Hoververktyg – hanteras via UIState
        self.hover = HoverTool(tooltips=[("ID", "@individual_id")], renderers=[self.indiv_renderer])
        if self.ui_state and self.ui_state.show_hover:
            self.plot.add_tools(self.hover)

        if self.ui_state:
            self.ui_state.subscribe(self.set_hover_visibility)

        self.plot.legend.location = "top_left"
        self.plot.legend.click_policy = "hide"

        from bokeh.layouts import column

        self.layout = column(self.status_select, self.plot)

        # Koppla panelen till replay-uppdateringar
        self.replay.subscribe(self.update)

        self.update() 

    def _get_indiv_data(self):
        state = self.replay.get_state()
        df = state["individuals"].copy()
        if "x_occ" not in df or "y_occ" not in df:
            df["x_occ"] = df["chi"] * np.cos(df["xi"])
            df["y_occ"] = df["chi"] * np.sin(df["xi"])
        # TA BORT GEOMETRY om den finns
        if "geometry" in df.columns:
            df = df.drop(columns=["geometry"])
        return df

    def _get_job_data(self):
        state = self.replay.get_state()
        if "jobs" not in state:
            return None
        jobs = state["jobs"].copy()
        if "x_occ" not in jobs or "y_occ" not in jobs:
            jobs["x_occ"] = jobs["chi"] * np.cos(jobs["xi"])
            jobs["y_occ"] = jobs["chi"] * np.sin(jobs["xi"])
        if "geometry" in jobs.columns:
            jobs = jobs.drop(columns=["geometry"])
        return jobs

    def update(self):
        df = self.replay.get_state()["individuals"]
        df = add_occ_coordinates(df)
        if "geometry" in df.columns:
            df = df.drop(columns=["geometry"])
        
        # Filtrera på status från MultiSelect
        selected_statuses = self.status_select.value
        filtered_df = df[df['status'].isin(selected_statuses)]
        self.indiv_source.data = filtered_df.to_dict("list")


    def set_hover_visibility(self, visible: bool):
        if visible:
            if self.hover and self.hover not in self.plot.tools:
                self.plot.add_tools(self.hover)
        else:
            if self.hover and self.hover in self.plot.tools:
                self.plot.tools.remove(self.hover)
