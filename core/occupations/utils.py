# core/occupations/utils.py

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

def angular_distance_vec(xi1, xi2):
    """
    Vektoriserad kortaste vinkelavståndsmatris (n_ind, n_jobs).
    xi1: (n_ind,) vektor
    xi2: (n_jobs,) vektor
    Returnerar (n_ind, n_jobs)-matris.
    """
    diff = np.abs(xi1[:, None] - xi2[None, :]) % (2 * np.pi)
    return np.minimum(diff, 2 * np.pi - diff)

# def compute_utility_matrix(individuals_df, jobs_df, alpha_chi=5.0, alpha_xi=5.0, alpha_geo=1.0):
#     inds_chi = individuals_df["chi"].values  # (n_ind,)
#     inds_xi = individuals_df["xi"].values
#     inds_x = individuals_df["x"].values
#     inds_y = individuals_df["y"].values

#     jobs_chi = jobs_df["chi"].values  # (n_jobs,)
#     jobs_xi = jobs_df["xi"].values
#     jobs_x = jobs_df["x"].values
#     jobs_y = jobs_df["y"].values

#     # |chi_i - chi_j|
#     chi_diff = np.abs(inds_chi[:, None] - jobs_chi[None, :])  # (n_ind, n_jobs)

#     # angular distance (wrap-around)
#     xi_diff = angular_distance_vec(inds_xi, jobs_xi)  # (n_ind, n_jobs)

#     # Geografiskt avstånd
#     dx = inds_x[:, None] - jobs_x[None, :]  # (n_ind, n_jobs)
#     dy = inds_y[:, None] - jobs_y[None, :]
#     geo_dist = np.sqrt(dx ** 2 + dy ** 2)  # (n_ind, n_jobs)

#     # Utility: exponentiell penalty för diffar i occupation space och geografi
#     U = np.exp(-alpha_chi * chi_diff - alpha_xi * xi_diff - alpha_geo * geo_dist)

#     return U

def compute_utility_matrix(
    individuals_df, jobs_df,
    alpha_chi=5.0, alpha_xi=5.0, alpha_geo=1.0
):
    inds_chi = individuals_df["chi"].values  # (n_ind,)
    inds_xi = individuals_df["xi"].values
    inds_H = individuals_df["H"].values      # (n_ind,)
    inds_x = individuals_df["x"].values
    inds_y = individuals_df["y"].values

    jobs_chi = jobs_df["chi"].values         # (n_jobs,)
    jobs_xi = jobs_df["xi"].values
    jobs_x = jobs_df["x"].values
    jobs_y = jobs_df["y"].values

    # Beräkna occupation-space-avståndet (euklidiskt, med wrap för xi)
    chi_diff = inds_chi[:, None] - jobs_chi[None, :]
    xi_diff = angular_distance_vec(inds_xi, jobs_xi)  # wrap runt 2pi

    occ_dist = np.sqrt(chi_diff**2 + xi_diff**2)     # (n_ind, n_jobs)

    # Mask för "innanför individens cirkel"
    H_expand = inds_H[:, None]                       # (n_ind, 1)
    within_circle = occ_dist <= H_expand             # boolean (n_ind, n_jobs)

    # Geografiskt avstånd
    dx = inds_x[:, None] - jobs_x[None, :]
    dy = inds_y[:, None] - jobs_y[None, :]
    geo_dist = np.sqrt(dx ** 2 + dy ** 2)            # (n_ind, n_jobs)

    # Utility – beräkna bara där within_circle, övriga = 0
    min_val = -1e6  # eller np.nan om du föredrar att maska så
    U = np.full_like(occ_dist, min_val, dtype=float)
    U[within_circle] = np.exp(-alpha_chi * np.abs(chi_diff[within_circle])
                              - alpha_xi * xi_diff[within_circle]
                              - alpha_geo * geo_dist[within_circle])

    return U

import numpy as np
import pandas as pd

def global_greedy_matching(
    individuals_df, jobs_df, 
    alpha_chi=5.0, alpha_xi=5.0, alpha_geo=1.0
):
    N = len(individuals_df)
    M = len(jobs_df)

    inds_chi = individuals_df["chi"].values
    inds_xi = individuals_df["xi"].values
    inds_H = individuals_df["H"].values
    inds_x = individuals_df["x"].values
    inds_y = individuals_df["y"].values
    inds_id = individuals_df["individual_id"].values

    jobs_chi = jobs_df["chi"].values
    jobs_xi = jobs_df["xi"].values
    jobs_x = jobs_df["x"].values
    jobs_y = jobs_df["y"].values
    jobs_id = jobs_df["job_id"].values

    # 1. Occupation space-avstånd
    chi_diff = inds_chi[:, None] - jobs_chi[None, :]
    xi_diff = np.abs(inds_xi[:, None] - jobs_xi[None, :]) % (2 * np.pi)
    xi_diff = np.minimum(xi_diff, 2 * np.pi - xi_diff)
    occ_dist = np.sqrt(chi_diff**2 + xi_diff**2)

    # 2. Geografiskt avstånd i kilometer
    dx = inds_x[:, None] - jobs_x[None, :]
    dy = inds_y[:, None] - jobs_y[None, :]
    geo_dist_m = np.sqrt(dx ** 2 + dy ** 2)
    geo_dist_km = geo_dist_m / 1000.0

    # 3. Halvnormal sannolikhet för matchning utifrån occupational distance (mjuk gräns)
    # (H broadcastas över jobb)
    occ_prob = np.exp(-0.5 * (occ_dist / inds_H[:, None])**2)

    # 4. Utility: nu överallt (ingen -inf utanför cirkel!)
    utility = occ_prob * np.exp(
        -alpha_chi * np.abs(chi_diff)
        - alpha_xi * xi_diff
        - alpha_geo * geo_dist_km
    )

    # 5. Matchningslogik som tidigare
    P_MIN = 1e-4  # eller vad du tycker är rimligt

    inds_i, jobs_j = np.where(utility > P_MIN)

    utility_flat = utility[inds_i, jobs_j]
    matches = list(zip(utility_flat, inds_i, jobs_j))

    matches.sort(reverse=True, key=lambda t: t[0])

    used_inds = set()
    used_jobs = set()
    results = []
    for util, i, j in matches:
        if i in used_inds or j in used_jobs:
            continue
        results.append({
            "individual_id": inds_id[i],
            "job_id": jobs_id[j],
            "utility": util
        })
        used_inds.add(i)
        used_jobs.add(j)
        if len(used_inds) == N or len(used_jobs) == M:
            break

    return pd.DataFrame(results)



# def optimal_assignment(individuals_df, jobs_df, alpha_chi=5.0, alpha_xi=5.0, alpha_geo=1.0):
#     """
#     Utför optimal matchning mellan individer och jobb med hjälp av Hungarian-algoritmen.
#     """
#     n_inds = len(individuals_df)
#     n_jobs = len(jobs_df)
#     if n_inds == 0 or n_jobs == 0:
#         return pd.DataFrame(columns=["individual_id", "job_id", "utility"])
#     U = compute_utility_matrix(individuals_df, jobs_df, alpha_chi=alpha_chi, alpha_xi=alpha_xi, alpha_geo=alpha_geo)

#     # Hitta giltiga rader och kolumner
#     valid_row_mask = np.any(np.isfinite(U), axis=1)
#     valid_col_mask = np.any(np.isfinite(U), axis=0)
#     valid_inds = np.where(valid_row_mask)[0]
#     valid_jobs = np.where(valid_col_mask)[0]

#     if not np.any(valid_row_mask) or not np.any(valid_col_mask):
#         return pd.DataFrame(columns=["individual_id", "job_id", "utility"])

#     U_valid = U[np.ix_(valid_row_mask, valid_col_mask)]

#     if not np.all(np.isfinite(U_valid)):
#         min_utility = np.nanmin(U_valid[np.isfinite(U_valid)]) if np.any(np.isfinite(U_valid)) else 0
#         U_valid = np.where(np.isfinite(U_valid), U_valid, min_utility - 1e6)

#     row_ind, col_ind = linear_sum_assignment(-U_valid)

#     # Vektorisera plock av id och utility
#     individual_ids = individuals_df.iloc[valid_inds[row_ind]]["individual_id"].values
#     job_ids = jobs_df.iloc[valid_jobs[col_ind]]["job_id"].values
#     utilities = U_valid[row_ind, col_ind]

#     # Skapa DataFrame direkt
#     return pd.DataFrame({
#         "individual_id": individual_ids,
#         "job_id": job_ids,
#         "utility": utilities
#     })
