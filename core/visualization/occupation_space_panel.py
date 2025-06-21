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
        self.employment_lines_source = ColumnDataSource(data=dict(xs=[], ys=[]))

        # Skapar plot
        self.plot = figure(
            title="Occupation Space",
            match_aspect=True,
            sizing_mode="stretch_both",
            tools=self.tools
        )

        self.plot.min_width = 600
        self.plot.min_height = 600
        self.plot.max_width = 2000
        self.plot.max_height = 1200
        self.plot.sizing_mode = "stretch_both"


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
                size='size_marker',
                legend_label="Jobb",
                selection_color="green"
            )


        self.lines_renderer = self.plot.multi_line(
            xs="xs", ys="ys",
            source=self.employment_lines_source,
            line_color="black", line_alpha=0.08, line_width=1
        )

        self.status_select = MultiSelect(
            title="Visa status:",
            value=statuses,     # Start med alla valda
            options=[(s, s.capitalize()) for s in statuses]
        )
        self.status_select.on_change("value", lambda attr, old, new: self.update())

        self.show_employment_lines = CheckboxGroup(
            labels=["Visa jobb-linjer"], 
            active=[0] if self.show_pathways else []
        )
        self.show_employment_lines.on_change("active", lambda attr, old, new: self.update())

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

        from bokeh.layouts import column, row

        self.layout = column(
            row(self.status_select, self.show_employment_lines, sizing_mode="stretch_both"),
            self.plot,
            sizing_mode="stretch_both"
        )

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
        if "employer_size" in jobs.columns:
            jobs["size_marker"] = 2 + 1 * np.log1p(jobs["employer_size"])
        else:
            jobs["size_marker"] = 6

        return jobs

    def update(self):
        df = self.replay.get_state()["individuals"]
        df = add_occ_coordinates(df)
        if "geometry" in df.columns:
            df = df.drop(columns=["geometry"])
        selected_statuses = self.status_select.value
        filtered_df = df[df['status'].isin(selected_statuses)]
        self.indiv_source.data = filtered_df.to_dict("list")

        # Hantera linjer till jobb
        if 0 in self.show_employment_lines.active:
            # Endast employed
            employed = filtered_df[filtered_df["status"] == "employed"].copy()
            if len(employed) > 0:
                jobs = self.replay.get_state()["jobs"]
                jobs = add_occ_coordinates(jobs)
                jobs_dict = {j["job_id"]: (j["x_occ"], j["y_occ"]) for j in jobs.to_dict("records")}
                xs, ys = [], []
                for _, row in employed.iterrows():
                    jid = row.get("job_id")
                    if jid and jid in jobs_dict:
                        xs.append([row["x_occ"], jobs_dict[jid][0]])
                        ys.append([row["y_occ"], jobs_dict[jid][1]])
                self.employment_lines_source.data = dict(xs=xs, ys=ys)
            else:
                self.employment_lines_source.data = dict(xs=[], ys=[])
        else:
            self.employment_lines_source.data = dict(xs=[], ys=[])


    def set_hover_visibility(self, visible: bool):
        if visible:
            if self.hover and self.hover not in self.plot.tools:
                self.plot.add_tools(self.hover)
        else:
            if self.hover and self.hover in self.plot.tools:
                self.plot.tools.remove(self.hover)
