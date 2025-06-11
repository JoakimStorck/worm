import pandas as pd
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.occupations.occupational_profiles import transform_onet_skills_scaled_from_db
from core.plotting.occupational import plot_full_occupation_space_polar

import matplotlib.pyplot as plt

# Hämta hela datasetet från databasen, med alla yrken och kluster (t.ex. 50 kluster)
df = transform_onet_skills_scaled_from_db(n_clusters=50)

# Skapa plotten
plot_full_occupation_space_polar(df, clusterlabels=True, show_axes=True)

plt.show()

