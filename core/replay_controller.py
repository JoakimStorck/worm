# core/replay_controller.py

from copy import deepcopy
from bokeh.models import ColumnDataSource
import numpy as np

from core.visualization.utils import gdf_points_to_xy
from core.visualization.utils import add_occ_coordinates

def get_indiv_source(self):
    df = add_occ_coordinates(self.state["individuals"])
    
    return ColumnDataSource(df)

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

def prepare_indiv_data(gdf):
    """
    Förbereder data från GeoDataFrame med individer inför användning i ColumnDataSource.
    Lägger till x/y-koordinater, tar bort geometrin och säkerställer att ID är sträng.
    """
    return gdf_points_to_xy(gdf, id_col="individual_id")

class ReplayController:
    def __init__(self, scenario_result):
        self.initial_state = {
            "individuals": scenario_result.individuals.copy(),
            "jobs": scenario_result.jobs.copy(),
            "employers": scenario_result.employers.copy()
        }
        self.eventlog = scenario_result.eventlog
        self.current_step = 0
        self.state = deepcopy(self.initial_state)
        self.max_step = len(self.eventlog) if self.eventlog is not None else 0
        self._subscribers = []

        # Gemensam ColumnDataSource för individer (skapas direkt)
        self.indiv_source = prepare_indiv_source(self.state["individuals"])

        
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

        new_data = prepare_indiv_source(self.state["individuals"]).data
        self.indiv_source.data = new_data

        self.notify_panels()

    def step_forward(self):
        self.goto(self.current_step + 1)

    def step_backward(self):
        self.goto(self.current_step - 1)

    def get_state(self):
        return self.state

    def get_indiv_source(self):
        return self.indiv_source

    def apply_event(self, state, event):
        # TODO: implementera faktisk logik
        pass
