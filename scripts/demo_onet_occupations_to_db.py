import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.occupational_profiles import transform_onet_skills_scaled, save_occupation_space_to_db

n_clusters = 50
df = transform_onet_skills_scaled(n_clusters=n_clusters, use_cache=False)
save_occupation_space_to_db(df, db_path="data/worm.sqlite3", n_clusters=n_clusters)
