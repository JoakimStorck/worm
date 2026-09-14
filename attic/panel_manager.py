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
from bokeh.models import Select, Div, RadioButtonGroup

class PanelManager:
    def __init__(self, replay, ui_state, panel_registry, panel_kwargs=None, n_panels=2):
        self.replay = replay
        self.ui_state = ui_state
        self.registry = panel_registry
        self.panel_kwargs = panel_kwargs or {}
        self.n_panels = n_panels

        self.view_mode = RadioButtonGroup(labels=["Delad vy", "Helskärm"], active=0)
        self.view_mode.on_change("active", lambda attr, old, new: self.refresh_layout())

        panel_keys = list(panel_registry.keys())
        default_panels = panel_keys[:n_panels] if len(panel_keys) >= n_panels else (panel_keys + [""] * n_panels)
        self.selectors = [
            Select(title=f"Panel {i+1}", value=default_panels[i], options=panel_keys)
            for i in range(n_panels)
        ]
        self.panel_layouts = [Div(text="") for _ in self.selectors]

        for idx, selector in enumerate(self.selectors):
            selector.on_change("value", self._make_update_panel(idx))

        # Viktigt: Sätt sizing_mode här
        self.layout = column(
            self.view_mode,
            row(
                *(column(sel, self.panel_layouts[i], sizing_mode="stretch_both") for i, sel in enumerate(self.selectors)),
                sizing_mode="stretch_both"
            ),
            sizing_mode="stretch_both"
        )
        self.instantiate_panels()

    def _make_update_panel(self, idx):
        return lambda attr, old, new: self.update_panel(idx, new)

    def _build_panel(self, panel_cls):
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
            # Sätt även sizing_mode på layout om möjligt
            if hasattr(instance, "layout"):
                instance.layout.sizing_mode = "stretch_both"
            return getattr(instance, "layout", instance)
        except Exception as e:
            print(f"Fel vid skapande av panel {panel_cls.__name__}: {e}")
            return Div(text=f"<b>Fel i panel '{panel_cls.__name__}':</b><br>{e}")

    def instantiate_panels(self):
        for idx, selector in enumerate(self.selectors):
            panel_cls = self.registry[selector.value]
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
                # Sätt sizing_mode även här!
                if hasattr(panel_instance, "layout"):
                    panel_instance.layout.sizing_mode = "stretch_both"
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
            if hasattr(panel_instance, "layout"):
                panel_instance.layout.sizing_mode = "stretch_both"
            self.panel_layouts[idx] = panel_instance.layout
        except Exception as e:
            print(f"Fel vid initiering av panel {panel_cls.__name__}: {e}")
            self.panel_layouts[idx] = Div(text=f"Fel vid initiering av panel:<br>{e}")
        self.refresh_layout()

    def refresh_layout(self, *args, **kwargs):
        from bokeh.layouts import column, row

        if hasattr(self, "view_mode") and getattr(self.view_mode, "active", 0) == 1:
            # Helskärmsläge – bara panelen direkt under view_mode
            self.layout.children = [
                self.view_mode,
                self.panel_layouts[0]
            ]
            self.layout.sizing_mode = "stretch_both"
            if hasattr(self.panel_layouts[0], "sizing_mode"):
                self.panel_layouts[0].sizing_mode = "stretch_both"
        else:
            self.layout.children = [
                self.view_mode,
                row(
                    *(column(self.selectors[i], self.panel_layouts[i], sizing_mode="stretch_both")
                    for i in range(len(self.selectors))),
                    sizing_mode="stretch_both"
                )
            ]
            self.layout.sizing_mode = "stretch_both"
            for pnl in self.panel_layouts:
                if hasattr(pnl, "sizing_mode"):
                    pnl.sizing_mode = "stretch_both"
