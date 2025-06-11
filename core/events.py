import heapq

class Event:
    def __init__(self, time, agent_id, event_type, params=None):
        self.time = time
        self.agent_id = agent_id
        self.event_type = event_type
        self.params = params or {}

    def __lt__(self, other):
        return self.time < other.time

class EventQueue:
    def __init__(self):
        self.queue = []

    def push(self, event):
        heapq.heappush(self.queue, event)

    def pop(self):
        return heapq.heappop(self.queue)

    def is_empty(self):
        return not self.queue

