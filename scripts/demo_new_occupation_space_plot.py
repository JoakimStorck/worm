import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.plotting.occupational import replay_plot_occupation_space

replay_plot_occupation_space(
    'output/initial_state_individuals.csv',
    'output/initial_state_jobs.csv',
    'output/eventlog.log',
    T=None,                      # eller None för sluttid
    plot_jobs=True,
    plot_indivs=True,
    plot_lines=True,
    plot_H_circle=True,
    selected_inds=['2080_i003478', '2080_i049669','2080_i039289','2080_i059386'],
    show_pathways=True,
)
