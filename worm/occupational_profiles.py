
import pandas as pd
import numpy as np
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from scipy.stats import entropy
import os

def transform_onet_skills_scaled(skills_path="onet_data/Skills.txt",
                                  occupation_path="onet_data/Occupation Data.txt",
                                  n_clusters=50,
                                  use_cache=True,
                                  cache_file="onet_data/transformed_onet.csv"):
    if use_cache and os.path.exists(cache_file):
        return pd.read_csv(cache_file)

    skills_df = pd.read_csv(skills_path, sep='\t', encoding='utf-8')
    imp_df = skills_df[skills_df['Scale ID'] == 'IM']
    lvl_df = skills_df[skills_df['Scale ID'] == 'LV']

    merged = pd.merge(
        imp_df[['O*NET-SOC Code', 'Element ID', 'Data Value']],
        lvl_df[['O*NET-SOC Code', 'Element ID', 'Data Value']],
        on=['O*NET-SOC Code', 'Element ID'],
        suffixes=('_IM', '_LV')
    )

    merged['Weighted'] = merged['Data Value_IM'] * merged['Data Value_LV']
    skill_matrix = merged.pivot(index='O*NET-SOC Code', columns='Element ID', values='Weighted').fillna(0)

    pca = PCA(n_components=2)
    skill_coords = pca.fit_transform(skill_matrix.values)

    kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=0)
    labels = kmeans.fit_predict(skill_coords)

    representatives = []
    for cluster_id in range(n_clusters):
        cluster_indices = (labels == cluster_id)
        cluster_points = skill_coords[cluster_indices]
        centroid = kmeans.cluster_centers_[cluster_id]
        distances = ((cluster_points - centroid) ** 2).sum(axis=1)
        best_idx = distances.argmin()
        original_idx = skill_matrix.index[cluster_indices][best_idx]
        representatives.append(original_idx)

    rep_matrix = skill_matrix.loc[representatives]
    rep_coords = pca.transform(rep_matrix.values)

    chi = np.linalg.norm(rep_coords, axis=1)
    xi = np.arctan2(rep_coords[:, 1], rep_coords[:, 0])

    def scaled_entropy(row):
        values = row.values + 1e-9
        probs = values / values.sum()
        base_entropy = entropy(probs, base=2)
        logsum = np.log2(values.sum())
        return base_entropy * logsum

    H = rep_matrix.apply(scaled_entropy, axis=1)

    occupation_df = pd.read_csv(occupation_path, sep='\t', encoding='utf-8')
    occupation_df = occupation_df[['O*NET-SOC Code', 'Title']].drop_duplicates()

    final_df = pd.DataFrame({
        'Occupation Code': rep_matrix.index,
        'Title': occupation_df.set_index('O*NET-SOC Code').loc[rep_matrix.index, 'Title'].values,
        'Chi': chi,
        'Xi': xi,
        'H': H.values,
        'PC1': rep_coords[:, 0],
        'PC2': rep_coords[:, 1]
    })

    final_df.to_csv(cache_file, index=False)
    return final_df
