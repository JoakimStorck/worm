# occupational_profiles_modular.py

import os
import pandas as pd
import numpy as np
import sqlite3
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from scipy.stats import entropy
from worm.occupations.utils import reorder_clusters_by_angle, select_representative_occupations, name_clusters_by_representative_titles



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

    # 6. Omordna kluster-ID baserat på vinklar (kan använda din befintliga funktion)
    final_df = reorder_clusters_by_angle(final_df)

    # 7. Kluster-namn och omordning (du kan använda dina befintliga hjälpfunktioner)
    # Här är förenklat, men du kan återanvända name_clusters_by_representative_titles och reorder_clusters_by_angle från din gamla kod:
    # ... (kopiera in om du vill ha stabil ordning & namn!)
    # 7. Kluster-namn och omordning (lägg in denna bit)
    reps = select_representative_occupations(final_df)
    names = name_clusters_by_representative_titles(reps)
    final_df['cluster_name'] = final_df['cluster'].map(names)

    # 8. Spara till SQL – nu med alla fält:
    final_df['n_clusters'] = n_clusters
    cols = ['onet_code', 'n_clusters', 'title', 'pc1', 'pc2', 'cluster', 'cluster_name', 'chi', 'xi', 'h']
    conn = sqlite3.connect(db_path)
    final_df[cols].to_sql("onet_occupation_space", conn, if_exists="replace", index=False)
    conn.close()
    print(f"Sparade {len(final_df)} rader till onet_occupation_space (n_clusters={n_clusters})")
    return final_df


# def save_occupation_space_to_db(df, db_path="data/worm.sqlite3", n_clusters=None):
#     """
#     Sparar occupation space-DataFrame till tabellen onet_occupation_space i SQLite.
#     Antag att df har rätt kolumner: Occupation Code, Title, PC1, PC2, Cluster, Chi, Xi, H, Cluster Name.
#     """
#     # Sätt rätt kolumnnamn och inkludera n_clusters i alla rader
#     df = df.rename(columns={
#         "Occupation Code": "onet_code",
#         "Title": "title",
#         "PC1": "pc1",
#         "PC2": "pc2",
#         "Cluster": "cluster",
#         "Cluster Name": "cluster_name",
#         "Chi": "chi",
#         "Xi": "xi",
#         "H": "h"
#     })
#     # Om n_clusters saknas, använd argument eller tvinga in det
#     if "n_clusters" not in df.columns:
#         if n_clusters is None:
#             raise ValueError("n_clusters måste anges!")
#         df["n_clusters"] = n_clusters
#     # Se till att kolumnordning och datatyper matchar exakt
#     df = df[["onet_code", "n_clusters", "title", "pc1", "pc2", "cluster", "cluster_name", "chi", "xi", "h"]]
#     # Skriv till SQL
#     conn = sqlite3.connect(db_path)
#     df.to_sql("onet_occupation_space", conn, if_exists="append", index=False)
#     conn.close()
#     print(f"Sparade {len(df)} rader till onet_occupation_space (n_clusters={df['n_clusters'].iloc[0]})")


# Om du vill köra modulen direkt för test
if __name__ == "__main__":
    df = transform_onet_skills_scaled_from_db(n_clusters=50)
    print(df.head())
