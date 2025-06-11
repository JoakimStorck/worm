import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


import pandas as pd
from core.plotting.occupational import replay_plot_occupation_space

EVENTLOG_PATH = 'output/eventlog.log'
INDIV_PATH = 'output/initial_state_individuals.csv'
JOB_PATH = 'output/initial_state_jobs.csv'
TOP_N = 10

def extract_individual_ids(eventlog_path):
    """Returnerar en lista med alla individual_id som förekommer i eventloggen."""
    individual_ids = []
    with open(eventlog_path, encoding='utf-8') as f:
        for line in f:
            parts = [x.strip() for x in line.strip().split(",")]
            for p in parts:
                if p.startswith("individual_id "):
                    ind_id = p.split(" ", 1)[1]
                    individual_ids.append(ind_id)
    return individual_ids

def get_most_active_individuals(eventlog_path, top_n=10):
    individual_ids = extract_individual_ids(eventlog_path)
    if not individual_ids:
        print("Ingen individual_id hittades i loggen.")
        return []
    counts = pd.Series(individual_ids).value_counts()
    print("Topp", top_n, "individer med flest events:")
    print(counts.head(top_n))
    return counts.head(top_n).index.tolist()

if __name__ == "__main__":
    selected_inds = get_most_active_individuals(EVENTLOG_PATH, TOP_N)
    if not selected_inds:
        print("Inga individer att plotta.")
    else:
        replay_plot_occupation_space(
            INDIV_PATH,
            JOB_PATH,
            EVENTLOG_PATH,
            selected_inds=selected_inds,
            show_pathways=True,
            plot_jobs=True,
            plot_indivs=True,
            plot_lines=True,
            plot_H_circle=True
        )
