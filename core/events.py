import heapq
import itertools

class EventQueue:
    def __init__(self):
        self.queue = []
        self.counter = itertools.count()  # unik sekvens för att skilja events

    def push(self, event):
        # Lägg till en unik sekvens för att hantera events med exakt samma tid
        heapq.heappush(self.queue, (event["time"], next(self.counter), event))

    def pop(self):
        return heapq.heappop(self.queue)[2]  # returnera bara event-dict

    def peek(self):
        return self.queue[0][2] if self.queue else None  # returnera bara event-dict

    def is_empty(self):
        return not self.queue
