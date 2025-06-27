# core/visualization/occupation_space_panel.py

import numpy as np
import pandas as pd
from bokeh.plotting import figure
from bokeh.models import (
    ColumnDataSource, HoverTool, CheckboxGroup, MultiSelect, TabPanel, Button, RadioButtonGroup
)
from core.ui_state import UIState
from core.visualization.utils import add_occ_coordinates
from core.visualization.selection_sync import sync_selections


def make_panel(replay_controller, ui_state, indiv_source, job_source=None, emp_source=None):
    panel = OccupationSpacePanel(
        replay_controller=replay_controller,
        ui_state=ui_state,
        indiv_source=indiv_source,
        job_source=job_source,
        emp_source=emp_source
    )
    return TabPanel(child=panel.layout, title="Occupation Space")

class OccupationSpacePanel:
    def __init__(
        self,
        replay_controller,
        ui_state,
        indiv_source,
        job_source=None,
        emp_source=None,
        show_jobs=True,
        show_pathways=False,
        show_H_circle=False,
        tools="tap,lasso_select,box_select,reset,pan,wheel_zoom,save"
    ):
        self.replay = replay_controller
        self.ui_state = ui_state
        self.indiv_source = indiv_source
        self.job_source = job_source
        self.emp_source = emp_source
        self.show_jobs = show_jobs
        self.show_pathways = show_pathways
        self.show_H_circle = show_H_circle
        self.tools = tools

        # Kopplingslinjer individ-jobb
        self.employment_lines_source = ColumnDataSource(data=dict(xs=[], ys=[]))
        self.indiv_job_lines_source = ColumnDataSource(data=dict(xs=[], ys=[], line_alpha=[], line_width=[]))
        self.emp_job_lines_source = ColumnDataSource(data=dict(xs=[], ys=[], line_alpha=[], line_width=[]))

        # --- Skapa figur ---
        self.plot = figure(
            title="Occupation Space",
            match_aspect=True,
            sizing_mode="stretch_both",
            #height_policy="max",
            #min_height=800,
            height=800,
            tools=self.tools,
        )

        from bokeh.transform import factor_cmap
        palette = ["green", "red", "purple", "black", "gray"]
        statuses = ["employed", "unemployed", "in_education", "career_break", "not_in_labor_force"]

        # Standard-alfa-värden för markörer
        self.base_alpha_indiv = 0.4
        self.base_alpha_job = 0.6
        self.base_alpha_emp = 0.7

        # Individer
        self.indiv_renderer = self.plot.scatter(
            'x_occ', 'y_occ',
            source=self.indiv_source,
            color=factor_cmap('status', palette=palette, factors=statuses),
            alpha='render_alpha',
            size=3,
            legend_field="status",
            selection_color="orange"
        )

        # Jobb (yrken)
        if self.show_jobs and self.job_source:
            self.plot.scatter(
                'x_occ', 'y_occ',
                source=self.job_source,
                color="blue",
                alpha='render_alpha',
                size='size_marker',
                legend_label="Jobb",
                selection_color="orange"
            )

        # Arbetsgivare (employers)
        if self.emp_source is not None:
            self.emp_renderer = self.plot.scatter(
                'x_occ', 'y_occ',
                source=self.emp_source,
                color="navy",
                alpha='render_alpha',
                size='size_marker',
                legend_label="Employers",
                marker="diamond",
                selection_color="orange"
            )
        else:
            self.emp_renderer = None

        # Linjer mellan individ-jobb
        self.lines_renderer = self.plot.multi_line(
            xs="xs", ys="ys",
            line_alpha="line_alpha", line_width="line_width",
            source=self.indiv_job_lines_source, line_color="black"
        )
        # Linjer arbetsgivare-jobb
        self.emp_job_lines_renderer = self.plot.multi_line(
            xs="xs", ys="ys",
            line_alpha="line_alpha", line_width="line_width",
            source=self.emp_job_lines_source, line_color="black"
        )

        # --- UI-kontroller ---
        self.status_select = MultiSelect(
            title="Visa status:",
            value=statuses,
            options=[(s, s.capitalize()) for s in statuses],
            height=120
        )
        self.status_select.on_change("value", lambda attr, old, new: self.update())


        # --- UI-kontroller ---
        self.show_employment_lines = CheckboxGroup(
            labels=["Visa jobb-linjer"],
            active=[0] if self.show_pathways else [],
            width=160
        )

        self.line_display_mode = RadioButtonGroup(
            labels=["Visa alla", "Visa endast markerade"],
            active=0,  # default: visa alla
            width=220,
            disabled=not (0 in self.show_employment_lines.active)
        )

        def on_checkbox_change(attr, old, new):
            # Radioknappar aktiva bara om checkboxen är ibockad
            self.line_display_mode.disabled = not (0 in self.show_employment_lines.active)
            self.update()

        self.show_employment_lines.on_change("active", on_checkbox_change)
        self.line_display_mode.on_change("active", lambda attr, old, new: self.update())

        # Knapp för att exportera tabeller
        self.export_button = Button(label="Exportera tabeller till CSV", width=220)
        self.export_button.on_click(self.export_tables)

        # --- Hover och legend ---
        self.hover = HoverTool(tooltips=[("ID", "@individual_id")], renderers=[self.indiv_renderer])
        if self.ui_state and self.ui_state.show_hover:
            self.plot.add_tools(self.hover)
        if self.ui_state:
            self.ui_state.subscribe(self.set_hover_visibility)

        self.plot.legend.location = "top_left"
        self.plot.legend.click_policy = "hide"

        # --- The Main Layout ---
        from bokeh.layouts import column, row

        self.layout = row(
            self.plot,
            column(
                self.status_select,
                self.show_employment_lines,
                self.line_display_mode,
                self.export_button,
                sizing_mode="fixed"
            ),
            sizing_mode="stretch_both",
            height=None,
        )

        
        if self.replay:
            # Om replay_controller är satt, prenumerera på uppdateringar
            self.replay.subscribe(self.update)
        else:
            print("occ-panel: Replay controller is not set, cannot subscribe to updates.")
        
        #self.indiv_source.on_change("data", lambda attr, old, new: self.update())
        #self.update()

        from bokeh.io import curdoc
        curdoc().add_next_tick_callback(self.update)


    def _get_indiv_data(self):
        state = self.replay.get_state()
        df = state["individuals"].copy()
        if "x_occ" not in df or "y_occ" not in df:
            df["x_occ"] = df["chi"] * np.cos(df["xi"])
            df["y_occ"] = df["chi"] * np.sin(df["xi"])
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
        if self.replay is None:
            print("occ-panel: Replay controller is not set, cannot update.")
            return

        # --- 1. Läs in och processa state ---
        # Individer
        df = self.replay.get_state()["individuals"]
        df = add_occ_coordinates(df)
        if "geometry" in df.columns:
            df = df.drop(columns=["geometry"])
        selected_statuses = self.status_select.value
        filtered_df = df[df['status'].isin(selected_statuses)].copy()  # <--- viktigt!

        # Jobb
        jobs = self.replay.get_state()["jobs"]
        jobs = add_occ_coordinates(jobs)
        if "geometry" in jobs.columns:
            jobs = jobs.drop(columns=["geometry"])
        if "employer_size" in jobs.columns:
            jobs["size_marker"] = 2 + 1 * np.log1p(jobs["employer_size"])
        else:
            jobs["size_marker"] = 6
        jobs = jobs.copy()  # Säkerställ äkta kopia

        # Arbetsgivare
        employers = None
        if self.emp_source is not None:
            employers = self.replay.get_state()["employers"]
            employers = add_occ_coordinates(employers)
            if "geometry" in employers.columns:
                employers = employers.drop(columns=["geometry"])
            employers["size_marker"] = 10
            employers = employers.copy()  # Säkerställ äkta kopia

        # --- 2. Avgör fokus baserat på selection ---
        focused_emp_indices = set(self.emp_source.selected.indices) if self.emp_source else set()
        focused_emp_ids = set()
        if employers is not None and focused_emp_indices:
            eid_list = employers['employer_id'].tolist()
            focused_emp_ids = {eid_list[i] for i in focused_emp_indices}

        focused_job_ids = set()
        if focused_emp_ids and not jobs.empty:
            for eid in focused_emp_ids:
                focused_job_ids.update(jobs[jobs['employer_id'] == eid]['job_id'].tolist())

        focused_indiv_ids = set()
        if focused_job_ids and not filtered_df.empty:
            focused_indiv_ids = set(filtered_df[filtered_df['job_id'].isin(focused_job_ids)].get('individual_id', []))

        # --- 3. Sätt render_alpha för individer, jobb och arbetsgivare beroende på läge ---

        show_all = self.line_display_mode.active == 0  # 0: "Visa alla", 1: "Endast markerade"
        min_focus_all = 0.13   # Minimum synlighet i "Visa alla"
        min_focus_selected = 0.05  # Minimum synlighet i "Endast markerade"

        # 3a. Individer
        if show_all:
            if focused_job_ids:
                filtered_df['focus_alpha'] = filtered_df['job_id'].apply(
                    lambda jid: 1.0 if jid in focused_job_ids else min_focus_all
                )
            else:
                filtered_df['focus_alpha'] = 1.0
        else:
            if focused_job_ids:
                filtered_df['focus_alpha'] = filtered_df['job_id'].apply(
                    lambda jid: 1.0 if jid in focused_job_ids else min_focus_selected
                )
            else:
                filtered_df['focus_alpha'] = min_focus_selected
        filtered_df['render_alpha'] = self.base_alpha_indiv * filtered_df['focus_alpha']
        self.indiv_source.data = filtered_df.to_dict("list")

        # 3b. Jobb
        if show_all:
            if focused_emp_ids:
                jobs['focus_alpha'] = jobs['employer_id'].apply(
                    lambda eid: 1.0 if eid in focused_emp_ids else min_focus_all
                )
            else:
                jobs['focus_alpha'] = 1.0
        else:
            if focused_emp_ids:
                jobs['focus_alpha'] = jobs['employer_id'].apply(
                    lambda eid: 1.0 if eid in focused_emp_ids else min_focus_selected
                )
            else:
                jobs['focus_alpha'] = min_focus_selected
        jobs['render_alpha'] = self.base_alpha_job * jobs['focus_alpha']
        self.job_source.data = jobs.to_dict("list")

        # 3c. Arbetsgivare
        if employers is not None:
            if show_all:
                if focused_emp_ids:
                    employers['focus_alpha'] = employers['employer_id'].apply(
                        lambda eid: 1.0 if eid in focused_emp_ids else min_focus_all
                    )
                else:
                    employers['focus_alpha'] = 1.0
            else:
                if focused_emp_ids:
                    employers['focus_alpha'] = employers['employer_id'].apply(
                        lambda eid: 1.0 if eid in focused_emp_ids else min_focus_selected
                    )
                else:
                    employers['focus_alpha'] = min_focus_selected
            employers['render_alpha'] = self.base_alpha_emp * employers['focus_alpha']
            self.emp_source.data = employers.to_dict("list")


        # --- 6. Synka selections ---
        sync_selections(self.emp_source, self.job_source, self.indiv_source)

        # --- 7. Hantera visning av linjer beroende på kontrollpanelen ---
        show_lines = 0 in self.show_employment_lines.active
        show_only_selected = self.line_display_mode.active == 1  # 0: Visa alla, 1: Endast markerade

        # Vilka arbetsgivare ska vara "aktiva" för linjedragning?
        if employers is not None:
            if show_only_selected and focused_emp_ids:
                active_emp_ids = focused_emp_ids
            else:
                # Visa alla om ingen är markerad eller om "Visa alla" är valt
                active_emp_ids = set(employers['employer_id'].tolist())
        else:
            active_emp_ids = set()

        # --- 8. Hantera linjer ARBETSGIVARE → JOBB ---
        if employers is not None and show_lines:
            xs_emp, ys_emp, alpha_emp, width_emp = [], [], [], []
            emp_records = employers.to_dict("records")
            jobs_records = jobs.to_dict("records")
            job_emp_map = {}
            for job in jobs_records:
                eid = job.get("employer_id")
                if eid is not None:
                    job_emp_map.setdefault(eid, []).append((job["x_occ"], job["y_occ"]))
            for eidx, erow in enumerate(emp_records):
                eid = erow.get("employer_id")
                ex, ey = erow["x_occ"], erow["y_occ"]
                if eid in active_emp_ids and eid in job_emp_map:
                    for jx, jy in job_emp_map[eid]:
                        xs_emp.append([ex, jx])
                        ys_emp.append([ey, jy])
                        # Extra: dämpa om radioknapp "visa alla" och ej markerad
                        if focused_emp_ids and eid in focused_emp_ids:
                            alpha_emp.append(0.7)
                            width_emp.append(3)
                        else:
                            alpha_emp.append(0.09 if show_only_selected else 0.25)
                            width_emp.append(1)
            self.emp_job_lines_source.data = dict(xs=xs_emp, ys=ys_emp, line_alpha=alpha_emp, line_width=width_emp)
        else:
            self.emp_job_lines_source.data = dict(xs=[], ys=[], line_alpha=[], line_width=[])

        # --- 9. Hantera linjer INDIVID → JOBB ---
        if show_lines:
            xs, ys, line_alpha, line_width = [], [], [], []
            indiv_records = filtered_df.to_dict("records")
            jobs_dict = {j["job_id"]: (j["x_occ"], j["y_occ"], j["employer_id"]) for j in jobs.to_dict("records")}
            for idx, row in enumerate(indiv_records):
                jid = row.get("job_id")
                if jid and jid in jobs_dict:
                    jx, jy, eid = jobs_dict[jid]
                    # Visa linje om arbetsgivaren är aktiv
                    if eid in active_emp_ids:
                        xs.append([row["x_occ"], jx])
                        ys.append([row["y_occ"], jy])
                        if focused_job_ids and jid in focused_job_ids:
                            line_alpha.append(0.7)
                            line_width.append(1)
                        else:
                            line_alpha.append(0.12 if show_only_selected else 0.22)
                            line_width.append(1)
            self.indiv_job_lines_source.data = dict(xs=xs, ys=ys, line_alpha=line_alpha, line_width=line_width)
        else:
            self.indiv_job_lines_source.data = dict(xs=[], ys=[], line_alpha=[], line_width=[])

        # --- 10. Synka synligheten på renderers ---
        self.lines_renderer.visible = show_lines
        if hasattr(self, "emp_job_lines_renderer"):
            self.emp_job_lines_renderer.visible = show_lines



    def set_hover_visibility(self, visible: bool):
        if visible:
            if self.hover and self.hover not in self.plot.tools:
                self.plot.add_tools(self.hover)
        else:
            if self.hover and self.hover in self.plot.tools:
                self.plot.tools.remove(self.hover)

    def export_tables(self):
        # Exportera huvudtabeller
        pd.DataFrame(self.indiv_source.data).to_csv("occupation_space_individuals.csv", index=False)
        pd.DataFrame(self.job_source.data).to_csv("occupation_space_jobs.csv", index=False)
        if self.emp_source is not None:
            pd.DataFrame(self.emp_source.data).to_csv("occupation_space_employers.csv", index=False)
        
        # --- Exportera linjedata ---
        def linesource_to_df(source, label):
            xs = source.data.get('xs', [])
            ys = source.data.get('ys', [])
            line_alpha = source.data.get('line_alpha', [])
            line_width = source.data.get('line_width', [])
            lines = []
            for i in range(len(xs)):
                x0, x1 = xs[i][0], xs[i][1]
                y0, y1 = ys[i][0], ys[i][1]
                alpha = line_alpha[i] if i < len(line_alpha) else None
                width = line_width[i] if i < len(line_width) else None
                lines.append({
                    "x0": x0, "y0": y0,
                    "x1": x1, "y1": y1,
                    "line_alpha": alpha,
                    "line_width": width
                })
            pd.DataFrame(lines).to_csv(f"occupation_space_lines_{label}.csv", index=False)

        linesource_to_df(self.indiv_job_lines_source, label="indiv_job")
        linesource_to_df(self.emp_job_lines_source, label="emp_job")
