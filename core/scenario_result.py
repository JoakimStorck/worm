# core/analysis/scenario_result.py

import os
import pandas as pd
import numpy as np
from typing import Callable, Optional
from bokeh.models import ColumnDataSource

class ScenarioResult:
    def __init__(self, snapshot):
        self.individuals = snapshot["individuals"]
        self.jobs = snapshot["jobs"]
        self.eventlog = snapshot["eventlog"]
        self.employers = snapshot.get("employers")
        self._indiv_source = None
        self._job_source = None

    def get_individuals(self, filter_func=None):
        df = self.individuals
        if filter_func:
            df = df[df.apply(filter_func, axis=1)]
        return df

    def get_jobs(self, filter_func=None):
        df = self.jobs
        if filter_func:
            df = df[df.apply(filter_func, axis=1)]
        return df

    def get_indiv_source(self):
        if self._indiv_source is not None:
            return self._indiv_source
        indiv = self.get_individuals().copy()
        if "x_occ" not in indiv or "y_occ" not in indiv:
            indiv["x_occ"] = indiv["chi"] * np.cos(indiv["xi"])
            indiv["y_occ"] = indiv["chi"] * np.sin(indiv["xi"])
        if "geometry" in indiv.columns:
            indiv["x"] = [pt.x for pt in indiv.geometry]
            indiv["y"] = [pt.y for pt in indiv.geometry]
            indiv = indiv.drop(columns=["geometry"])
        if "cluster" not in indiv.columns:
            indiv["cluster"] = "Unassigned"
        self._indiv_source = ColumnDataSource(indiv)
        return self._indiv_source

    def get_job_source(self):
        if self._job_source is not None:
            return self._job_source
        jobs = self.get_jobs().copy()
        if "x_occ" not in jobs or "y_occ" not in jobs:
            jobs["x_occ"] = jobs["chi"] * np.cos(jobs["xi"])
            jobs["y_occ"] = jobs["chi"] * np.sin(jobs["xi"])
        if "geometry" in jobs.columns:
            jobs["x"] = [pt.x for pt in jobs.geometry]
            jobs["y"] = [pt.y for pt in jobs.geometry]
            jobs = jobs.drop(columns=["geometry"])
        if "cluster" not in jobs.columns:
            jobs["cluster"] = "Unassigned"
        self._job_source = ColumnDataSource(jobs)
        return self._job_source

    def get_eventlog(self):
        return self.eventlog

    def get_employers(self):
        return self.employers

    @classmethod
    def from_run(cls, run_path):
        # Ladda snapshot på samma sätt
        snapshot = load_snapshot(run_path)
        return cls(snapshot)

import geopandas as gpd
from shapely import wkt

def restore_geometry(df):
    if "geometry" in df.columns and df["geometry"].dtype == object:
        try:
            df["geometry"] = gpd.GeoSeries.from_wkt(df["geometry"])
        except Exception:
            pass
    return df

def load_snapshot(run_path):
    # Läs alltid de tre huvudfilerna (krävs i din pipeline)
    individuals = pd.read_csv(f"{run_path}/initial_state_individuals.csv")
    if "geometry" in individuals.columns:
        individuals = restore_geometry(individuals)
    jobs = pd.read_csv(f"{run_path}/initial_state_jobs.csv")
    if "geometry" in jobs.columns:
        jobs = restore_geometry(jobs)
    employers_path = os.path.join(run_path, "employers.csv")
    if os.path.exists(employers_path):
        employers = pd.read_csv(employers_path)
        if "geometry" in employers.columns:
            employers = restore_geometry(employers)
    else:
        employers = None

    # Eventlog: försök läsa eventlog.csv, annars None
    eventlog_path = os.path.join(run_path, "eventlog.csv")
    if os.path.exists(eventlog_path):
        eventlog = pd.read_csv(eventlog_path)
    else:
        eventlog = None  # eller pd.DataFrame() om du vill ha en tom ram

    return {
        "individuals": individuals,
        "jobs": jobs,
        "eventlog": eventlog,
        "employers": employers
    }
