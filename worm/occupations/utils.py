#occupations/utils.py

import pandas as pd
import numpy as np
import math

from worm.agents import Worker
from worm.jobs import Job


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
    diff = abs(xi1 - xi2)
    return min(diff, 2 * np.pi - diff)

def compute_utility(worker: Worker, job: Job, alpha=1.0) -> float:
    if worker.chi < job.chi:
        return -np.inf
    angle_penalty = np.exp(-alpha * angular_distance(worker.xi, job.xi))
    dx = worker.position[0] - job.position[0]
    dy = worker.position[1] - job.position[1]
    distance = math.sqrt(dx**2 + dy**2)
    return (job.chi / (distance + 1e-6)) * angle_penalty
