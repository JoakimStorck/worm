
import numpy as np
from typing import List

class Geography:
    def __init__(self, size=100):
        self.size = size
        self.map = np.zeros((size, size))

    def place_agents(self, agents: List):
        for agent in agents:
            r = np.random.randint(0, self.size)
            k = np.random.randint(0, self.size)
            agent.position = (r, k)
            self.map[r % self.size, k % self.size] += 1

    def cluster(self, agents: List, iters=1000):
        for _ in range(iters):
            i = np.random.randint(len(agents))
            r, k = map(int, agents[i].position)
            dr = np.random.choice([-1, 0, 1])
            dk = np.random.choice([-1, 0, 1])
            r2, k2 = (r + dr) % self.size, (k + dk) % self.size
            if self.map[r2, k2] < self.map[r, k]:
                self.map[r, k] -= 1
                self.map[r2, k2] += 1
                agents[i].position = (r2, k2)
