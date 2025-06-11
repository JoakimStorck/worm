
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worm import generate_employers, generate_workers, Geography, match_workers_to_jobs

from core.plotting.geographic import plot_agent_distribution
from core.plotting.matching import plot_matches

# 1. Generera data
employers = generate_employers(10, map_size=100)
workers = generate_workers(50, map_size=100)

# 2. Extrahera alla jobb
jobs = [job for employer in employers for job in employer.jobs]

# 3. Placera och klustra
geo = Geography(size=100)
geo.place_agents(jobs)
geo.cluster(jobs)
geo.place_agents(workers)
geo.cluster(workers)

# 4. Matchning
matches = match_workers_to_jobs(workers, employers, alpha=1.0)

# 5. Visualisering
plot_agent_distribution(workers, jobs, title="Geografisk fördelning")
plot_matches(workers, jobs, matches, title="Matchade par")

# 6. Utskrift
log("\nMatchade par:")
for w, j, score in matches[:5]:
    log(f"Worker {w.id[:6]} matched with Job {j.id[:6]} (Employer {j.employer_id[:6]})")
    log(f"  χ_w = {w.chi:.2f}, ξ_w = {w.xi:.2f}")
    log(f"  χ_j = {j.chi:.2f}, ξ_j = {j.xi:.2f}")
    log(f"  Utility score: {score:.4f}\n")
