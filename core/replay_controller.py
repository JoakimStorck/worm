# core/replay_controller.py

from copy import deepcopy
from bokeh.models import ColumnDataSource
import numpy as np

from core.visualization.utils import gdf_points_to_xy, add_occ_coordinates

def prepare_indiv_source(df):
    """
    Förbereder individdata för visualisering:
    - Lägger till x/y från geometri
    - Lägger till x_occ/y_occ från chi/xi
    - Tar bort onödig geometri
    - Säkerställer att ID är sträng
    """
    df = gdf_points_to_xy(df, id_col="individual_id")
    df = add_occ_coordinates(df)
    return ColumnDataSource(df)

def prepare_job_source(df):
    """
    Förbereder jobbdata för visualisering:
    - Lägger till x_occ/y_occ från chi/xi
    - Tar bort onödig geometri
    - Skapar 'size_marker' utifrån arbetsgivarstorlek om tillgänglig
    """
    df = df.copy()
    if "x_occ" not in df or "y_occ" not in df:
        df["x_occ"] = df["chi"] * np.cos(df["xi"])
        df["y_occ"] = df["chi"] * np.sin(df["xi"])
    if "geometry" in df.columns:
        df = df.drop(columns=["geometry"])
    if "employer_size" in df.columns:
        df["size_marker"] = 2 + 1 * np.log1p(df["employer_size"])
    else:
        df["size_marker"] = 6
    return ColumnDataSource(df)

def prepare_emp_source(df):
    """
    Förbereder arbetsgivardata (employers) för visualisering:
    - Konverterar geometri till x/y
    - Säkerställer att ID är sträng
    """
    return gdf_points_to_xy(df, id_col="employer_id") if not df.empty else ColumnDataSource(data=dict(x=[], y=[], employer_id=[]))

class ReplayController:
    def __init__(self, scenario_result):
        self.initial_state = {
            "individuals": scenario_result.individuals.copy(),
            "jobs": scenario_result.jobs.copy(),
            "employers": scenario_result.employers.copy(),
            "events": scenario_result.events.copy()
        }
        self.scenario = scenario_result
        self.eventlog = scenario_result.events
        self.current_step = 0
        self.state = deepcopy(self.initial_state)
        self.max_step = len(self.eventlog) if self.eventlog is not None else 0
        self._subscribers = []

        # Centrala datakällor
        self.indiv_source = prepare_indiv_source(self.state["individuals"])
        self.job_source = prepare_job_source(self.state["jobs"])
        self.emp_source = prepare_emp_source(self.state["employers"])

    def subscribe(self, panel_update_func):
        self._subscribers.append(panel_update_func)

    def notify_panels(self):
        for update_func in self._subscribers:
            update_func()

    def _replay_to(self, tau):
        state = {
            "individuals": self.initial_state["individuals"].copy(),
            "jobs": self.initial_state["jobs"].copy(),
            "employers": self.initial_state["employers"].copy()
        }
        for i, event in enumerate(self.eventlog.itertuples()):
            if i > tau:
                break
            self.apply_event(state, event)
        return state

    def goto(self, tau):
        self.current_step = max(0, min(tau, self.max_step - 1))
        self.state = self._replay_to(self.current_step)

        # Uppdatera datakällor
        self.indiv_source.data = prepare_indiv_source(self.state["individuals"]).data
        self.job_source.data   = prepare_job_source(self.state["jobs"]).data
        self.emp_source.data   = prepare_emp_source(self.state["employers"]).data

        self.notify_panels()

    def step_forward(self):
        self.goto(self.current_step + 1)

    def step_backward(self):
        self.goto(self.current_step - 1)

    def get_state(self):
        return self.state

    def get_indiv_source(self):
        return self.indiv_source

    def get_job_source(self):
        return self.job_source

    def get_emp_source(self):
        return self.emp_source

    def apply_event(self, state, event):
        # TODO: implementera faktisk logik
        pass
