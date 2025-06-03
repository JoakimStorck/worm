# occupational_profiles_modular.py

import os
import pandas as pd
import numpy as np
import sqlite3
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from scipy.stats import entropy

# Om du kör i projektstruktur, importera PROJECT_ROOT annars byt till "."
try:
    from worm import PROJECT_ROOT
except ImportError:
    PROJECT_ROOT = "."


def make_weighted_skill_matrix(skills_df):
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
    return skill_matrix

def reduce_and_cluster(skill_matrix, n_clusters):
    pca = PCA(n_components=2)
    skill_coords = pca.fit_transform(skill_matrix.values)
    kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=0)
    labels = kmeans.fit_predict(skill_coords)
    return skill_coords, labels

def calc_polar_and_entropy(skill_matrix, skill_coords):
    def scaled_entropy(row):
        values = row.values + 1e-9
        probs = values / values.sum()
        base_entropy = entropy(probs, base=2)
        logsum = np.log2(values.sum())
        return base_entropy * logsum

    H = skill_matrix.apply(scaled_entropy, axis=1)
    chi = np.linalg.norm(skill_coords, axis=1)
    xi = np.arctan2(skill_coords[:, 1], skill_coords[:, 0])
    return chi, xi, H

def build_final_df(skill_matrix, occupation_df, skill_coords, labels, chi, xi, H):
    occupation_df = occupation_df[['O*NET-SOC Code', 'Title']].drop_duplicates()
    final_df = pd.DataFrame({
        'Occupation Code': skill_matrix.index,
        'Title': occupation_df.set_index('O*NET-SOC Code').loc[skill_matrix.index, 'Title'].values,
        'PC1': skill_coords[:, 0],
        'PC2': skill_coords[:, 1],
        'Cluster': labels,
        'Chi': chi,
        'Xi': xi,
        'H': H.values
    })
    return final_df

def select_representative_occupations(df):
    """
    Select one representative occupation per cluster based on proximity to cluster centroid.
    """
    representatives = []
    for cluster_id in df['Cluster'].unique():
        cluster_df = df[df['Cluster'] == cluster_id]
        centroid = cluster_df[['PC1', 'PC2']].mean().values
        distances = ((cluster_df[['PC1', 'PC2']].values - centroid) ** 2).sum(axis=1)
        best_idx = distances.argmin()
        representatives.append(cluster_df.iloc[best_idx])
    return pd.DataFrame(representatives)

def name_clusters_by_representative_titles(df):
    names = {}
    for _, row in df.iterrows():
        cluster_id = row['Cluster']
        title = row['Title']
        short_title = title.split(',')[0].split('(')[0].strip()
        names[cluster_id] = f"{short_title} ({cluster_id})"
    return names

def reorder_clusters_by_angle(df):
    """
    Reassign cluster IDs based on angular position of cluster centroids in polar space (Chi, Xi).
    The new cluster IDs increase with angle (Xi), i.e. counter-clockwise.
    """
    centroids = df.groupby('Cluster')[['Chi', 'Xi']].mean()
    sorted_clusters = centroids.sort_values('Xi').index.tolist()
    cluster_mapping = {old_id: new_id for new_id, old_id in enumerate(sorted_clusters)}
    df['Cluster'] = df['Cluster'].map(cluster_mapping)
    return df

def transform_onet_skills_scaled(n_clusters=50, use_cache=True, cache_dir="onet_data"):
    """
    Transformerar O*NET-skills till en 2D-representation med PCA och klustrar alla yrken.
    Returnerar en DataFrame med koordinater, entropi, kluster-id och klusternamn.
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"transformed_onet_{n_clusters}.csv")
    if use_cache and os.path.exists(cache_file):
        print(f"Loading cached data from {cache_file}")
        return pd.read_csv(cache_file)

    skills_path = os.path.join(PROJECT_ROOT, "onet_data", "Skills.txt")
    occupation_path = os.path.join(PROJECT_ROOT, "onet_data", "Occupation Data.txt")

    # 1. Läs data
    skills_df, occupation_df = load_onet_data(skills_path, occupation_path)
    # 2. Gör skill-matris
    skill_matrix = make_weighted_skill_matrix(skills_df)
    # 3. PCA och klustring
    skill_coords, labels = reduce_and_cluster(skill_matrix, n_clusters)
    # 4. Polära koordinater och entropi
    chi, xi, H = calc_polar_and_entropy(skill_matrix, skill_coords)
    # 5. Bygg slutdataframe
    final_df = build_final_df(skill_matrix, occupation_df, skill_coords, labels, chi, xi, H)
    # 6. Kluster-namn och omordning
    representatives_df = select_representative_occupations(final_df)
    cluster_names = name_clusters_by_representative_titles(representatives_df)
    final_df = reorder_clusters_by_angle(final_df)
    final_df['Cluster Name'] = final_df['Cluster'].map(cluster_names)
    # 7. Spara och returnera
    final_df.to_csv(cache_file, index=False)
    print(f"Saved transformed data to {cache_file}")
    return final_df

import os
import pandas as pd
import numpy as np
import sqlite3
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from scipy.stats import entropy


def transform_onet_skills_scaled_from_db(n_clusters=50, db_path="data/worm.sqlite3"):
    """
    Skapar occupation space från SQL-databas: läser occupations, skills och occupation_skill_link,
    bygger skill-matris, gör PCA, klustrar, räknar chi/xi/H, sparar till onet_occupation_space.
    """

    # 1. Läs data från databas
    conn = sqlite3.connect(db_path)
    occ_df = pd.read_sql("SELECT onet_code, title FROM onet_occupations", conn)
    skill_df = pd.read_sql("SELECT skill_id, skill_name FROM onet_skills", conn)
    link_df = pd.read_sql("SELECT onet_code, skill_id, scale_id, data_value FROM occupation_skill_link", conn)
    conn.close()

    # 2. Bygg skill-matris (liknar din gamla make_weighted_skill_matrix)
    imp_df = link_df[link_df['scale_id'] == 'IM']
    lvl_df = link_df[link_df['scale_id'] == 'LV']
    merged = pd.merge(
        imp_df[['onet_code', 'skill_id', 'data_value']],
        lvl_df[['onet_code', 'skill_id', 'data_value']],
        on=['onet_code', 'skill_id'],
        suffixes=('_IM', '_LV')
    )
    merged['Weighted'] = merged['data_value_IM'].astype(float) * merged['data_value_LV'].astype(float)
    skill_matrix = merged.pivot(index='onet_code', columns='skill_id', values='Weighted').fillna(0)

    # 3. PCA och klustring
    pca = PCA(n_components=2)
    skill_coords = pca.fit_transform(skill_matrix.values)
    kmeans = KMeans(n_clusters=n_clusters, n_init=10, random_state=0)
    labels = kmeans.fit_predict(skill_coords)

    # 4. Polära koordinater och entropi
    def scaled_entropy(row):
        values = row.values + 1e-9
        probs = values / values.sum()
        base_entropy = entropy(probs, base=2)
        logsum = np.log2(values.sum())
        return base_entropy * logsum

    H = skill_matrix.apply(scaled_entropy, axis=1)
    chi = np.linalg.norm(skill_coords, axis=1)
    xi = np.arctan2(skill_coords[:, 1], skill_coords[:, 0])

    # 5. Bygg slutdataframe
    occ_titles = occ_df.set_index('onet_code').reindex(skill_matrix.index)['title']
    final_df = pd.DataFrame({
        'onet_code': skill_matrix.index,
        'title': occ_titles.values,
        'pc1': skill_coords[:, 0],
        'pc2': skill_coords[:, 1],
        'cluster': labels,
        'chi': chi,
        'xi': xi,
        'h': H.values
    })

    # 6. Kluster-namn och omordning (du kan använda dina befintliga hjälpfunktioner)
    # Här är förenklat, men du kan återanvända name_clusters_by_representative_titles och reorder_clusters_by_angle från din gamla kod:
    # ... (kopiera in om du vill ha stabil ordning & namn!)

    # 7. Spara till SQL
    final_df['n_clusters'] = n_clusters
    cols = ['onet_code', 'n_clusters', 'title', 'pc1', 'pc2', 'cluster', 'chi', 'xi', 'h']
    conn = sqlite3.connect(db_path)
    final_df[cols].to_sql("onet_occupation_space", conn, if_exists="replace", index=False)
    conn.close()
    print(f"Sparade {len(final_df)} rader till onet_occupation_space (n_clusters={n_clusters})")
    return final_df

# Kör så här:
if __name__ == "__main__":
    df = transform_onet_skills_scaled_from_db(n_clusters=50)
    print(df.head())


def save_occupation_space_to_db(df, db_path="data/worm.sqlite3", n_clusters=None):
    """
    Sparar occupation space-DataFrame till tabellen onet_occupation_space i SQLite.
    Antag att df har rätt kolumner: Occupation Code, Title, PC1, PC2, Cluster, Chi, Xi, H, Cluster Name.
    """
    # Sätt rätt kolumnnamn och inkludera n_clusters i alla rader
    df = df.rename(columns={
        "Occupation Code": "onet_code",
        "Title": "title",
        "PC1": "pc1",
        "PC2": "pc2",
        "Cluster": "cluster",
        "Cluster Name": "cluster_name",
        "Chi": "chi",
        "Xi": "xi",
        "H": "h"
    })
    # Om n_clusters saknas, använd argument eller tvinga in det
    if "n_clusters" not in df.columns:
        if n_clusters is None:
            raise ValueError("n_clusters måste anges!")
        df["n_clusters"] = n_clusters
    # Se till att kolumnordning och datatyper matchar exakt
    df = df[["onet_code", "n_clusters", "title", "pc1", "pc2", "cluster", "cluster_name", "chi", "xi", "h"]]
    # Skriv till SQL
    conn = sqlite3.connect(db_path)
    df.to_sql("onet_occupation_space", conn, if_exists="append", index=False)
    conn.close()
    print(f"Sparade {len(df)} rader till onet_occupation_space (n_clusters={df['n_clusters'].iloc[0]})")


# Om du vill köra modulen direkt för test
if __name__ == "__main__":
    df = transform_onet_skills_scaled(n_clusters=50, use_cache=False)
    print(df.head())
