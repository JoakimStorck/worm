# core/analysis/scenario_result.py
# API för analys/visualisering (ScenarioResult) ===

import pandas as pd
from typing import Callable, Optional


from bokeh.models import ColumnDataSource
import numpy as np

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
        if hasattr(self, "_indiv_source") and self._indiv_source is not None:
            return self._indiv_source
        indiv = self.get_individuals().copy()
        # Lägg till occupation space-koordinater om de saknas
        if "x_occ" not in indiv or "y_occ" not in indiv:
            indiv["x_occ"] = indiv["chi"] * np.cos(indiv["xi"])
            indiv["y_occ"] = indiv["chi"] * np.sin(indiv["xi"])
        # Lägg till x/y för karta
        if "geometry" in indiv.columns:
            indiv["x"] = [pt.x for pt in indiv.geometry]
            indiv["y"] = [pt.y for pt in indiv.geometry]
            indiv = indiv.drop(columns=["geometry"])  # <-- Viktigt!
        self._indiv_source = ColumnDataSource(indiv)
        return self._indiv_source

    def get_job_source(self):
        # Caching
        if hasattr(self, "_job_source") and self._job_source is not None:
            return self._job_source
        jobs = self.get_jobs().copy()
        # Occupation space-koordinater
        if "x_occ" not in jobs or "y_occ" not in jobs:
            jobs["x_occ"] = jobs["chi"] * np.cos(jobs["xi"])
            jobs["y_occ"] = jobs["chi"] * np.sin(jobs["xi"])
        # Kart-koordinater
        if "geometry" in jobs.columns:
            jobs["x"] = [pt.x for pt in jobs.geometry]
            jobs["y"] = [pt.y for pt in jobs.geometry]
            jobs = jobs.drop(columns=["geometry"])
        self._job_source = ColumnDataSource(jobs)
        return self._job_source

    def get_eventlog(self):
        return self.eventlog

    def get_employers(self):
        return self.employers
