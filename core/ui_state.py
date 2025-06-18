
# core/ui_state.py

class UIState:
    def __init__(self):
        self._subscribers = []
        self.show_hover = False

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def set_show_hover(self, value: bool):
        self.show_hover = value
        for cb in self._subscribers:
            cb(value)
