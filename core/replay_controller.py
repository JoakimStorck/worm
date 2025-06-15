# core/replay_controller.py

from copy import deepcopy

class ReplayController:
    def __init__(self, scenario_result):
        # Initialdata (vid t=0) är snapshot från output/run, eller scenario.
        # Detta är din “ground truth” för replay.
        self.initial_state = {
            "individuals": scenario_result.individuals.copy(),
            "jobs": scenario_result.jobs.copy(),
            "employers": scenario_result.employers.copy()
        }
        self.eventlog = scenario_result.eventlog
        self.current_step = 0
        self.state = deepcopy(self.initial_state)  # Det här blir state vid t=0 (direkt efter load)
        self.max_step = len(self.eventlog) if self.eventlog is not None else 0
        self._subscribers = []

    def subscribe(self, panel_update_func):
        self._subscribers.append(panel_update_func)

    def notify_panels(self):
        for update_func in self._subscribers:
            update_func()

    def _replay_to(self, tau):
        # Alltid börja från en *copy* av initial_state och applicera events upp till och med tau.
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
        self.current_step = max(0, min(tau, self.max_step-1))
        self.state = self._replay_to(self.current_step)
        self.notify_panels()

    def step_forward(self):
        self.goto(self.current_step + 1)

    def step_backward(self):
        self.goto(self.current_step - 1)

    def get_state(self):
        return self.state

    def apply_event(self, state, event):
        # Här skriver du logik för hur event påverkar individer, jobb osv.
        # Exempel: ändra status, flytta individer, uppdatera jobb
        pass
