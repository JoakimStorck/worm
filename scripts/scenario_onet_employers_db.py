import sys
import os
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import uuid

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worm.agents import Employer, Job
from worm.plotting.occupational import plot_occupation_space

# --- NYTT: Ladda transformerad O*NET occupation space-data från databasen ---
def load_occupation_space_from_db(db_path, n_clusters):
    conn = sqlite3.connect(db_path)
    sql = """
        SELECT * FROM onet_occupation_space
        WHERE n_clusters = ?
    """
    df = pd.read_sql(sql, conn, params=(n_clusters,))
    conn.close()
    return df

# 1. Ange var databasen ligger och välj antal kluster
db_path = os.path.join("data", "worm.sqlite3")
n_clusters = 50

# 2. Ladda transformerade O*NET-data (hela datasettet) från databas
all_occupations_df = load_occupation_space_from_db(db_path, n_clusters)

# 3. Välj representativa yrken per kluster (kan använda samma funktion som innan)
def select_representative_occupations(df):
    """Välj en representant per kluster baserat på närhet till centroid."""
    representatives = []
    for cluster_id in df['Cluster'].unique():
        cluster_df = df[df['Cluster'] == cluster_id]
        centroid = cluster_df[['PC1', 'PC2']].mean().values
        distances = ((cluster_df[['PC1', 'PC2']].values - centroid) ** 2).sum(axis=1)
        best_idx = distances.argmin()
        representatives.append(cluster_df.iloc[best_idx])
    return pd.DataFrame(representatives)

df = select_representative_occupations(all_occupations_df)

# 4. Skapa arbetsgivare baserat på varje occupation-kluster
employers = []
for i, row in df.iterrows():
    emp_id = str(uuid.uuid4())
    position = (np.random.uniform(0, 100), np.random.uniform(0, 100))
    segment = row['Xi']
    size = np.random.randint(3, 10)

    employer = Employer(
        id=emp_id,
        position=position,
        segment=segment,
        size=size
    )

    for _ in range(size):
        job = Job(
            id=str(uuid.uuid4()),
            chi=row['Chi'] + np.random.normal(0, 0.2),
            xi=row['Xi'] + np.random.normal(0, 0.1),
            position=position,
            employer_id=emp_id
        )
        employer.jobs.append(job)

    employers.append(employer)

# 5. Visualisera occupation space för de representativa yrkena
fig, ax = plot_occupation_space(df, bubble_scale=1.5, labels=True)
fig.suptitle("Occupation Space of Employers (Representative O*NET Occupations)")
fig.tight_layout()
plt.show()
