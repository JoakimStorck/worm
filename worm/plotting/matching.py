
import matplotlib.pyplot as plt

def plot_matches(workers, jobs, matches, title="Job Matches"):
    plt.figure(figsize=(8, 8))
    for worker, job, score in matches:
        x1, y1 = worker.position
        x2, y2 = job.position
        plt.plot([x1, x2], [y1, y2], 'gray', alpha=0.3)
    for w in workers:
        plt.plot(w.position[0], w.position[1], 'bo', alpha=0.5)
    for j in jobs:
        plt.plot(j.position[0], j.position[1], 'ro', alpha=0.5)
    plt.title(title)
    plt.xlabel("X")
    plt.ylabel("Y")
    plt.axis('equal')
    plt.grid(True)
    plt.legend(["Matches", "Workers", "Jobs"])
    plt.show()
