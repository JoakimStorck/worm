import json
import os

from bokeh.models import Div

class StatisticsPanel:
    KWARGS = ['replay_controller', 'ui_state']

    def __init__(self, replay_controller, ui_state=None, outdir=None, **kwargs):
        self.replay = replay_controller
        self.ui_state = ui_state
        self.outdir = replay_controller.scenario.outdir  # Directory där stats-filer finns

        self.div = Div(text=self._build_stats_html(), width=420, height=380)
        self.layout = self.div

        self.replay.subscribe(self.update)
        self.update()

    def _load_stats(self, tag):
        # Hjälpfunktion för att ladda json-filer (before/after)
        path = os.path.join(self.outdir, f"basic_stats_{tag}.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        else:
            print(f'Nonexisting path {path}')
        return {}

    def _build_stats_html(self):
        before = self._load_stats("before")
        after = self._load_stats("after")

        # Utvalda variabler
        indivs_before = before.get("n_individuals", "-")
        indivs_after = after.get("n_individuals", "-")
        jobs_before = before.get("n_jobs", "-")
        jobs_after = after.get("n_jobs", "-")
        employers_before = before.get("n_employers", "-")
        employers_after = after.get("n_employers", "-")

        # Status
        status_b = before.get("individual_status_counts", {})
        status_a = after.get("individual_status_counts", {})
        emp_b = status_b.get("employed", "-")
        emp_a = status_a.get("employed", "-")
        unemp_b = status_b.get("unemployed", "-")
        unemp_a = status_a.get("unemployed", "-")
        nlf_b = status_b.get("not_in_labor_force", "-")
        nlf_a = status_a.get("not_in_labor_force", "-")

        # OCS
        xi_b = before.get("OCS_individuals", {}).get("xi", {})
        xi_a = after.get("OCS_individuals", {}).get("xi", {})
        xi_mean_b = f"{xi_b.get('mean', '-'):0.3f}" if 'mean' in xi_b else "-"
        xi_mean_a = f"{xi_a.get('mean', '-'):0.3f}" if 'mean' in xi_a else "-"
        chi_b = before.get("OCS_individuals", {}).get("chi", {})
        chi_a = after.get("OCS_individuals", {}).get("chi", {})
        chi_mean_b = f"{chi_b.get('mean', '-'):0.3f}" if 'mean' in chi_b else "-"
        chi_mean_a = f"{chi_a.get('mean', '-'):0.3f}" if 'mean' in chi_a else "-"
        H_b = before.get("OCS_individuals", {}).get("H", {})
        H_a = after.get("OCS_individuals", {}).get("H", {})
        H_mean_b = f"{H_b.get('mean', '-'):0.3f}" if 'mean' in H_b else "-"
        H_mean_a = f"{H_a.get('mean', '-'):0.3f}" if 'mean' in H_a else "-"

        html = f"""
        <b>Statistik före och efter simulering</b>
        <table style="border-collapse:collapse;">
            <tr style="background:#f0f0f0;">
                <th style="padding:4px;">Kategori</th>
                <th style="padding:4px;">Före</th>
                <th style="padding:4px;">Efter</th>
            </tr>
            <tr><td style="padding:4px;">Individer</td><td>{indivs_before}</td><td>{indivs_after}</td></tr>
            <tr><td style="padding:4px;">Jobb</td><td>{jobs_before}</td><td>{jobs_after}</td></tr>
            <tr><td style="padding:4px;">Arbetsgivare</td><td>{employers_before}</td><td>{employers_after}</td></tr>
            <tr style="background:#f0f0f0;"><td colspan="3"><b>Individstatus</b></td></tr>
            <tr><td style="padding:4px;">&nbsp;&nbsp;Anställda</td><td>{emp_b}</td><td>{emp_a}</td></tr>
            <tr><td style="padding:4px;">&nbsp;&nbsp;Arbetslösa</td><td>{unemp_b}</td><td>{unemp_a}</td></tr>
            <tr><td style="padding:4px;">&nbsp;&nbsp;Ej i arbetskraft</td><td>{nlf_b}</td><td>{nlf_a}</td></tr>
            <tr style="background:#f0f0f0;"><td colspan="3"><b>OCS (medelvärde)</b></td></tr>
            <tr><td style="padding:4px;">&nbsp;&nbsp;xi</td><td>{xi_mean_b}</td><td>{xi_mean_a}</td></tr>
            <tr><td style="padding:4px;">&nbsp;&nbsp;chi</td><td>{chi_mean_b}</td><td>{chi_mean_a}</td></tr>
            <tr><td style="padding:4px;">&nbsp;&nbsp;H</td><td>{H_mean_b}</td><td>{H_mean_a}</td></tr>
        </table>
        """
        return html

    def update(self):
        self.div.text = self._build_stats_html()
