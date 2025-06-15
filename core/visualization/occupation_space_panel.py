# core/visualization/occupation_space_panel.py

import numpy as np
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource, HoverTool

class OccupationSpacePanel:
    def __init__(
        self,
        replay_controller,
        show_jobs=True,
        show_pathways=False,
        show_H_circle=False,
        width=500,
        height=700,
        tools="lasso_select,box_select,reset,pan,wheel_zoom"
    ):
        self.replay = replay_controller
        self.show_jobs = show_jobs
        self.show_pathways = show_pathways
        self.show_H_circle = show_H_circle
        self.width = width
        self.height = height
        self.tools = tools

        # Initierar datakällor
        self.indiv_source = ColumnDataSource(self._get_indiv_data().to_dict("list"))
        self.job_source = ColumnDataSource(self._get_job_data().to_dict("list")) if show_jobs else None

        # Skapar plot
        self.plot = figure(
            title="Occupation Space",
            width=self.width,
            height=self.height,
            match_aspect=True,
            tools=self.tools
        )

        # Individer
        indiv_renderer = self.plot.scatter(
            'x_occ', 'y_occ',
            source=self.indiv_source,
            color="red",
            alpha=0.6,
            size=8,
            legend_label="Individer",
            selection_color="orange"
        )

        # Jobb
        if self.show_jobs and self.job_source:
            self.plot.scatter(
                'x_occ', 'y_occ',
                source=self.job_source,
                color="blue",
                alpha=0.3,
                size=5,
                legend_label="Jobb",
                selection_color="green"
            )

        # Pathways och H-cirklar – reserverat för utbyggnad

        # Hover och legend
        self.plot.add_tools(HoverTool(tooltips=[("ID", "@individual_id")], renderers=[indiv_renderer]))
        self.plot.legend.location = "top_left"
        self.plot.legend.click_policy = "hide"

        self.layout = self.plot

        # Koppla panelen till replay-uppdateringar
        self.replay.subscribe(self.update)

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
        # Körs automatiskt när replay ändras
        self.indiv_source.data = self._get_indiv_data().to_dict("list")
        if self.show_jobs and self.job_source is not None:
            self.job_source.data = self._get_job_data().to_dict("list")
