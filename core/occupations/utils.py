# core/occupations/utils.py
# Euklidisk matchning i den task-baserade geometrin (x_occ, y_occ), kärnbredd = r_o.

import pandas as pd
import numpy as np
import math
from scipy.optimize import linear_sum_assignment


def select_representative_occupations(df):
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
        short_title = row['title'].split(',')[0].split('(')[0].strip()
        names[row['cluster']] = f"{short_title} ({row['cluster']})"
    return names


def reorder_clusters_by_angle(df):
    centroids = df.groupby('cluster')[['chi', 'xi']].mean()
    sorted_clusters = centroids.sort_values('xi').index.tolist()
    mapping = {old: new for new, old in enumerate(sorted_clusters)}
    df['cluster'] = df['cluster'].map(mapping)
    return df


# ---------------------------------------------------------------------------
# Matchning: euklidiskt avstånd i (x_occ, y_occ), gaussisk kärna med bredd r_o.
# sigma^2 = H_individ^2 + r_o_jobb^2  (faltning: arbetartolerans + yrkesräckvidd)
# alpha_chi/alpha_xi behålls i signaturen för bakåtkompatibilitet men används ej.
# ---------------------------------------------------------------------------
def _occ_distance(inds_df, jobs_df):
    ix = inds_df["x_occ"].values[:, None]; iy = inds_df["y_occ"].values[:, None]
    jx = jobs_df["x_occ"].values[None, :]; jy = jobs_df["y_occ"].values[None, :]
    return np.sqrt((ix - jx) ** 2 + (iy - jy) ** 2)          # (n_ind, n_jobs)


def _occ_prob(inds_df, jobs_df, occ_dist, sigma_gamma=1.0):
    """Matchproduktivitet som gaussisk kärna i planet.

    Bredden är GEOMETRISK: yrkets task-radie r_o (Ekv. 2) faltad med arbetarens
    erfarenhetsradie r_i (spridningen i det egna yrkeshistoriken). Bägge är RMS-
    avstånd i samma plan och därmed kommensurabla med occ_dist.

        sigma = sigma_gamma * sqrt(r_o^2 + r_i^2)

    r_i saknas eller = 0 ger sigma = sigma_gamma * r_o, vilket är formuleringen
    i pappret och i GTS-motorn (dar bredden sitter helt pa yrket/familjen).
    sigma_gamma < 1 skarper matchningen; den ar avsedd som kalibreringsratt mot
    en malvakansgrad.
    """
    ro = jobs_df["r_o"].values[None, :]
    if "r_i" in inds_df.columns:
        ri = np.nan_to_num(inds_df["r_i"].values)[:, None]
    else:
        ri = 0.0
    sigma2 = np.maximum((sigma_gamma ** 2) * (ro ** 2 + ri ** 2), 1e-9)
    return np.exp(-0.5 * occ_dist ** 2 / sigma2)


def _geo_km(inds_df, jobs_df):
    dx = inds_df["x"].values[:, None] - jobs_df["x"].values[None, :]
    dy = inds_df["y"].values[:, None] - jobs_df["y"].values[None, :]
    return np.sqrt(dx ** 2 + dy ** 2) / 1000.0


def compute_utility_matrix(individuals_df, jobs_df,
                           alpha_chi=5.0, alpha_xi=5.0, alpha_geo=1.0,
                           sigma_gamma=1.0):
    occ_dist = _occ_distance(individuals_df, jobs_df)
    occ_prob = _occ_prob(individuals_df, jobs_df, occ_dist, sigma_gamma)
    geo_km   = _geo_km(individuals_df, jobs_df)
    return occ_prob * np.exp(-alpha_geo * geo_km)


def global_greedy_matching(individuals_df, jobs_df,
                           alpha_chi=5.0, alpha_xi=5.0, alpha_geo=1.0,
                           sigma_gamma=1.0, utility_min=0.05):
    N, M = len(individuals_df), len(jobs_df)
    inds_id = individuals_df["individual_id"].values
    jobs_id = jobs_df["job_id"].values

    utility = compute_utility_matrix(individuals_df, jobs_df, alpha_geo=alpha_geo,
                                     sigma_gamma=sigma_gamma)

    # Reservationsnytta: under denna accepteras inget jobb. Styr vakansgraden.
    inds_i, jobs_j = np.where(utility > utility_min)
    matches = list(zip(utility[inds_i, jobs_j], inds_i, jobs_j))
    matches.sort(reverse=True, key=lambda t: t[0])

    used_inds, used_jobs, results = set(), set(), []
    for util, i, j in matches:
        if i in used_inds or j in used_jobs:
            continue
        results.append({"individual_id": inds_id[i], "job_id": jobs_id[j], "utility": util})
        used_inds.add(i); used_jobs.add(j)
        if len(used_inds) == N or len(used_jobs) == M:
            break
    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Kompetensdynamik (oförändrad) + kartesisk sampling i enhetsskivan
# ---------------------------------------------------------------------------
def chi_add(chi, delta):
    return min(max(chi + delta, 0.0), 1.0)

def r_add(r_i, delta):
    """Justerar erfarenhetsradien (bredd i planet)."""
    return min(max(r_i + delta, 0.0), 1.0)


# Bakåtkompatibelt alias (H hette tidigare kompetensbredd/entropi)
H_add = r_add

def xi_add(xi, delta):
    return (xi + delta) % (2 * np.pi)


def sample_centers_xy_jitter(x_vals, y_vals, weights, n_samples, sigma_xy, power=1.5):
    """Välj yrkescentrum efter vikt och lägg kartesisk gaussisk jitter; klipp till enhetsskivan."""
    w = np.asarray(weights, dtype=float)
    w = (w ** power); w = w / w.sum()
    idx = np.random.choice(len(x_vals), size=n_samples, p=w)
    x = x_vals[idx] + np.random.normal(0, sigma_xy, size=n_samples)
    y = y_vals[idx] + np.random.normal(0, sigma_xy, size=n_samples)
    r = np.hypot(x, y)
    over = r > 1.0
    x[over] /= r[over]; y[over] /= r[over]      # projicera in i skivan
    return x, y


def sample_from_centers_jitter(xi_vals, chi_vals, weights, n_samples, sigma_xi, sigma_chi):
    """Bevarad polär sampler (bakåtkompatibilitet)."""
    w = np.asarray(weights, dtype=float)
    w = (w ** 1.5); w = w / w.sum()
    idx = np.random.choice(len(xi_vals), size=n_samples, p=w)
    xi = (xi_vals[idx] + np.random.normal(0, sigma_xi, size=n_samples)) % (2 * np.pi)
    chi = np.clip(chi_vals[idx] + np.random.normal(0, sigma_chi, size=n_samples), 0, 1)
    return xi, chi


def apply_capability_update(chi, xi, r_i, delta_chi=0.0, delta_xi=0.0, delta_r=0.0,
                            switch_cost_kappa=0.0, breadth_from_move=0.25):
    """
    Uppdaterar (chi, xi, r_i) i enhetsskivan och returnerar synkade (x_occ, y_occ).

    Tva geometriska mekanismer:

    1. BYTARKOSTNAD. Vinkelforflyttning drar av djup (chi) proportionellt mot
       kortaste vinkelavstandet: riktningsbyte urholkar riktningsspecifikt
       humankapital (Gathmann-Schonberg; storre vinkelgap <-> storre
       kapabilitetsskillnad).

    2. BREDDNING. Erfarenhetsradien r_i vaxer med den faktiska forflyttningen i
       planet, som ett lopande RMS: r_i' = sqrt(r_i^2 + breadth_from_move * d^2).
       En arbetare som rort sig langt mellan yrken tacker ett bredare omrade;
       en som stannat kvar forblir en punkt. Det ersatter den tidigare
       entropin H, som lag pa en skala som inte var kommensurabel med planet.

    Returnerar (chi, xi, r_i, x_occ, y_occ).
    """
    chi, xi, r_i = float(chi), float(xi), float(r_i)
    x0, y0 = chi * np.cos(xi), chi * np.sin(xi)

    ang = abs((float(delta_xi) + np.pi) % (2 * np.pi) - np.pi)      # kortaste vinkel
    xi_new = (xi + float(delta_xi)) % (2 * np.pi)
    chi_new = min(max(chi + float(delta_chi) - switch_cost_kappa * ang, 0.0), 1.0)
    x1, y1 = chi_new * np.cos(xi_new), chi_new * np.sin(xi_new)

    moved = float(np.hypot(x1 - x0, y1 - y0))
    r_new = np.sqrt(max(r_i ** 2 + breadth_from_move * moved ** 2, 0.0))
    r_new = min(max(r_new + float(delta_r), 0.0), 1.0)
    return chi_new, xi_new, r_new, x1, y1
