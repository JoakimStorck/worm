# core/panel_manager.py

from core.visualization.occupation_space_panel import OccupationSpacePanel
from core.visualization.map_panel import MapPanel
from core.visualization.statistics_panel import StatisticsPanel

PANEL_REGISTRY = {
    "Occupation Space": OccupationSpacePanel,
    "Karta": MapPanel,
    "Statistik": StatisticsPanel,
    # Lägg till nya paneler här...
}

from bokeh.layouts import row, column
from bokeh.models import Select, Div

class PanelManager:
    def __init__(self, replay, ui_state, panel_registry, panel_kwargs=None, n_panels=2):
        """
        replay: ReplayController (eller motsvarande state)
        ui_state: UIState
        panel_registry: dict, ex {"Karta": MapPanel, ...}
        panel_kwargs: dict med alla potentiella kwargs för paneler
        n_panels: antal panel-platser i layouten
        """
        self.replay = replay
        self.ui_state = ui_state
        self.registry = panel_registry
        self.panel_kwargs = panel_kwargs or {}
        self.n_panels = n_panels

        # Initiera selectors (en för varje plats/panel)
        panel_keys = list(panel_registry.keys())
        default_panels = panel_keys[:n_panels] if len(panel_keys) >= n_panels else (panel_keys + [""] * n_panels)
        self.selectors = [
            Select(title=f"Panel {i+1}", value=default_panels[i], options=panel_keys)
            for i in range(n_panels)
        ]
        # Här: använd en *tom Div* som placeholder
        self.panel_layouts = [Div(text="") for _ in self.selectors]

        # Knyt ihop change-callbacks
        for idx, selector in enumerate(self.selectors):
            selector.on_change("value", self._make_update_panel(idx))

        # Sätt layouten först, tomt
        self.layout = row(*(column(sel, self.panel_layouts[i]) for i, sel in enumerate(self.selectors)))
        self.instantiate_panels()

    def _make_update_panel(self, idx):
        # Workaround: lambda i loop binder på fel sätt utan default-argument
        return lambda attr, old, new: self.update_panel(idx, new)

    def _build_panel(self, panel_cls):
        # Sätt ihop samtliga kwargs, filtrera mot panelens KWARGS
        base_kwargs = dict(
            replay_controller=self.replay,
            ui_state=self.ui_state,
            **self.panel_kwargs
        )
        allowed = getattr(panel_cls, "KWARGS", None)
        if allowed:
            kwargs = {k: v for k, v in base_kwargs.items() if k in allowed}
        else:
            kwargs = base_kwargs
        try:
            instance = panel_cls(**kwargs)
            # Alltid ett .layout-attribut (ex: plot, layout, Div)
            return getattr(instance, "layout", instance)
        except Exception as e:
            print(f"Fel vid skapande av panel {panel_cls.__name__}: {e}")
            return Div(text=f"<b>Fel i panel '{panel_cls.__name__}':</b><br>{e}")

    def instantiate_panels(self):
        for idx, selector in enumerate(self.selectors):
            panel_cls = self.registry[selector.value]
            # Hämta listan av tillåtna kwargs för panelen, annars tom lista
            accepted_kwargs = getattr(panel_cls, "KWARGS", [])
            # Bygg kwargs: alltid med replay-argument i rätt namn
            kwargs = {}
            for k in accepted_kwargs:
                # Hantera replay/replay_controller
                if k == "replay" and hasattr(self, "replay"):
                    kwargs[k] = self.replay
                elif k == "replay_controller" and hasattr(self, "replay"):
                    kwargs[k] = self.replay
                elif k == "ui_state" and hasattr(self, "ui_state"):
                    kwargs[k] = self.ui_state
                elif k in self.panel_kwargs:
                    kwargs[k] = self.panel_kwargs[k]
            try:
                panel_instance = panel_cls(**kwargs)
                self.panel_layouts[idx] = panel_instance.layout
            except Exception as e:
                print(f"Fel vid initiering av panel {panel_cls.__name__}: {e}")
                self.panel_layouts[idx] = Div(text=f"Fel vid initiering av panel:<br>{e}")
        self.refresh_layout()


    def update_panel(self, idx, new_panel_name):
        panel_cls = self.registry[new_panel_name]
        accepted_kwargs = getattr(panel_cls, "KWARGS", [])
        kwargs = {}
        for k in accepted_kwargs:
            if k == "replay" and hasattr(self, "replay"):
                kwargs[k] = self.replay
            elif k == "replay_controller" and hasattr(self, "replay"):
                kwargs[k] = self.replay
            elif k == "ui_state" and hasattr(self, "ui_state"):
                kwargs[k] = self.ui_state
            elif k in self.panel_kwargs:
                kwargs[k] = self.panel_kwargs[k]
        try:
            panel_instance = panel_cls(**kwargs)
            self.panel_layouts[idx] = panel_instance.layout
        except Exception as e:
            print(f"Fel vid initiering av panel {panel_cls.__name__}: {e}")
            self.panel_layouts[idx] = Div(text=f"Fel vid initiering av panel:<br>{e}")
        self.refresh_layout()

    def refresh_layout(self):
        from bokeh.layouts import column
        self.layout.children = [
            column(self.selectors[i], self.panel_layouts[i]) for i in range(len(self.selectors))
        ]

