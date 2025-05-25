
import matplotlib.pyplot as plt

def plot_agent_distribution(workers, jobs, title="Agent Distribution"):
    plt.figure(figsize=(8, 8))
    for w in workers:
        plt.plot(w.position[0], w.position[1], 'bo', alpha=0.5)
    for j in jobs:
        plt.plot(j.position[0], j.position[1], 'ro', alpha=0.5)
    plt.title(title)
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.legend(["Workers", "Jobs"])
    plt.grid(True)
    plt.axis('equal')
    plt.show()
