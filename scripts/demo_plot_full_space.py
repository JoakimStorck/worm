import pandas as pd
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worm.occupational_profiles import transform_onet_skills_scaled
from worm.plotting.occupational import plot_full_occupation_space_polar

# Hämta hela datasetet med alla yrken, klustrat i 50 kluster (eller ändra antalet om du vill)
df = transform_onet_skills_scaled(n_clusters=50, use_cache=True)

# Skapa plotten
import matplotlib.pyplot as plt

plot_full_occupation_space_polar(df, clusterlabels=True, show_axes=True)

plt.show()
