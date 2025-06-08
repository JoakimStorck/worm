import pandas as pd
import numpy as np
import math
from scipy.optimize import linear_sum_assignment

def select_representative_occupations(df):
    """
    Select one representative occupation per cluster based on proximity to cluster centroid.
    """
    representatives = []
    for cluster_id in df['cluster'].unique():
        cluster_df = df[df['cluster'] == cluster_id]
        centroid = cluster_df[['pc1', 'pc2']].mean().values
        distances = ((cluster_df[['pc1', 'pc2']].values - centroid) ** 2).sum(axis=1)
        best_idx = distances.argmin()
        representatives.append(cluster_df.iloc[best_idx])
    return pd.DataFrame(representatives)

def name_clusters_by_representative_titles(df):
    names = {}
    for _, row in df.iterrows():
        cluster_id = row['cluster']
        title = row['title']
        short_title = title.split(',')[0].split('(')[0].strip()
        names[cluster_id] = f"{short_title} ({cluster_id})"
    return names

def reorder_clusters_by_angle(df):
    """
    Reassign cluster IDs based on angular position of cluster centroids in polar space (Chi, Xi).
    The new cluster IDs increase with angle (Xi), i.e. counter-clockwise.
    """
    centroids = df.groupby('cluster')[['chi', 'xi']].mean()
    sorted_clusters = centroids.sort_values('xi').index.tolist()
    cluster_mapping = {old_id: new_id for new_id, old_id in enumerate(sorted_clusters)}
    df['cluster'] = df['cluster'].map(cluster_mapping)
    return df

def angular_distance(xi1, xi2):
    """Shortest angular distance in radians on [0, 2π]."""
    diff = abs(xi1 - xi2)
    return min(diff, 2 * np.pi - diff)

def compute_utility(individual_row, job_row, alpha=1.0):
    """
    Beräknar utility-score mellan en individ och ett jobb (rad från respektive DataFrame).
    Kräver att båda har chi, xi, x, y som kolumner.
    """
    if individual_row["chi"] < job_row["chi"]:
        return -np.inf
    xi1 = individual_row["xi"]
    xi2 = job_row["xi"]
    angle_penalty = np.exp(-alpha * angular_distance(xi1, xi2))
    dx = individual_row["x"] - job_row["x"]
    dy = individual_row["y"] - job_row["y"]
    distance = math.sqrt(dx**2 + dy**2)
    return (job_row["chi"] / (distance + 1e-6)) * angle_penalty

def compute_utility_matrix(individuals_df, jobs_df, alpha=1.0):
    """
    Returnerar en (n_individer x n_job)-matris med utility för varje möjlig matchning.
    Antag: båda DataFrames har kolumnerna chi, xi, x, y.
    """
    n_ind = len(individuals_df)
    n_jobs = len(jobs_df)
    U = np.full((n_ind, n_jobs), -np.inf)

    inds_chi = individuals_df["chi"].values
    inds_xi = individuals_df["xi"].values
    inds_x = individuals_df["x"].values
    inds_y = individuals_df["y"].values

    jobs_chi = jobs_df["chi"].values
    jobs_xi = jobs_df["xi"].values
    jobs_x = jobs_df["x"].values
    jobs_y = jobs_df["y"].values

    print("Individuals chi, min/max/mean:", inds_chi.min(), inds_chi.max(), inds_chi.mean())
    print("Jobs chi, min/max/mean:", jobs_chi.min(), jobs_chi.max(), jobs_chi.mean())

    for i in range(n_ind):
        for j in range(n_jobs):
            if inds_chi[i] < jobs_chi[j]:
                continue
            angle_penalty = np.exp(-alpha * angular_distance(inds_xi[i], jobs_xi[j]))
            dx = inds_x[i] - jobs_x[j]
            dy = inds_y[i] - jobs_y[j]
            dist = math.sqrt(dx**2 + dy**2)
            U[i, j] = (jobs_chi[j] / (dist + 1e-6)) * angle_penalty
    return U


def optimal_assignment(individuals_df, jobs_df, alpha=1.0):
    n_inds = len(individuals_df)
    n_jobs = len(jobs_df)
    if n_inds == 0 or n_jobs == 0:
        return pd.DataFrame(columns=["individual_id", "job_id", "utility"])
    U = compute_utility_matrix(individuals_df, jobs_df, alpha=alpha)

    # Hitta giltiga rader och kolumner
    valid_row_mask = np.any(np.isfinite(U), axis=1)
    valid_col_mask = np.any(np.isfinite(U), axis=0)
    valid_inds = np.where(valid_row_mask)[0]
    valid_jobs = np.where(valid_col_mask)[0]

    if not np.any(valid_row_mask) or not np.any(valid_col_mask):
        # Ingen möjlig matchning i denna batch
        return pd.DataFrame(columns=["individual_id", "job_id", "utility"])

    # Skapa submatris
    U_valid = U[np.ix_(valid_row_mask, valid_col_mask)]

    # Hantera om även submatrisen har -inf kvar (ovanligt, men värt att kolla)
    if not np.all(np.isfinite(U_valid)):
        # Ersätt kvarvarande -inf med mycket dåliga, men ändå tillåtna, värden
        min_utility = np.nanmin(U_valid[np.isfinite(U_valid)]) if np.any(np.isfinite(U_valid)) else 0
        U_valid = np.where(np.isfinite(U_valid), U_valid, min_utility - 1e6)

    # Kör assignment på bara de möjliga
    row_ind, col_ind = linear_sum_assignment(-U_valid)
    matches = []
    for i, j in zip(row_ind, col_ind):
        matches.append({
            "individual_id": individuals_df.iloc[valid_inds[i]]["individual_id"],
            "job_id": jobs_df.iloc[valid_jobs[j]]["job_id"],
            "utility": U_valid[i, j]
        })
    return pd.DataFrame(matches)
