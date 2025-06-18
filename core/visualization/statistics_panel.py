# core/visualization/statistics_panel.py

from bokeh.models import Div

class StatisticsPanel:
    KWARGS = ['ui_state']
    def __init__(self, replay, ui_state=None, **kwargs):
        self.replay = replay
        self.ui_state = ui_state

        # Skapa Div för statistik
        self.div = Div(text=self._build_stats_html(), width=320, height=300)
        self.layout = self.div

        # Uppdatera vid replay!
        self.replay.subscribe(self.update)

        # Initial rendering
        self.update()

    def _build_stats_html(self):
        state = self.replay.get_state()
        individuals = state.get("individuals", None)
        jobs = state.get("jobs", None)
        employers = state.get("employers", None)

        n_indiv = len(individuals) if individuals is not None else 0
        n_jobs = len(jobs) if jobs is not None else 0
        n_employers = len(employers) if employers is not None else 0

        html = f"""
        <b>Statistik (aktuellt state):</b><br>
        Individer: <b>{n_indiv}</b><br>
        Jobb: <b>{n_jobs}</b><br>
        Arbetsgivare: <b>{n_employers}</b><br>
        """
        return html

    def update(self):
        self.div.text = self._build_stats_html()
