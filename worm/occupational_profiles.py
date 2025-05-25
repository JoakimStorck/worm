import pandas as pd
import numpy as np
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from scipy.stats import entropy
from worm import PROJECT_ROOT  # Se till att detta är korrekt importerat i __init__.py
import os

def transform_onet_skills_scaled(n_clusters=50,
                                  use_cache=True,
                                  cache_dir="onet_data") -> pd.DataFrame:
    """
    Transformerar O*NET-skills till en 2D-representation med PCA och klustrar alla yrken.
    Returnerar en DataFrame med koordinater, entropi, kluster-id och klusternamn.

    Parametrar:
        n_clusters (int): Antal kluster att använda för gruppering av yrken.
        use_cache (bool): Om True används tidigare sparad CSV om den finns.
        cache_dir (str): Katalog där cache-filer och indatafiler finns.

    Returnerar:
        pd.DataFrame: DataFrame med alla yrken, koordinater och klusterdata.
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"transformed_onet_{n_clusters}.csv")

    if use_cache and os.path.exists(cache_file):
        return pd.read_csv(cache_file)

    skills_path = os.path.join(PROJECT_ROOT, "onet_data", "Skills.txt")
    occupation_path = os.path.join(PROJECT_ROOT, "onet_data", "Occupation Data.txt")

    skills_df = pd.read_csv(skills_path, sep='\t', encoding='utf-8')
    occupation_df = pd.read_csv(occupation_path, sep='\t', encoding='utf-8')

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

    def scaled_entropy(row):
        values = row.values + 1e-9
        probs = values / values.sum()
        base_entropy = entropy(probs, base=2)
        logsum = np.log2(values.sum())
        return base_entropy * logsum

    H = skill_matrix.apply(scaled_entropy, axis=1)
    chi = np.linalg.norm(skill_coords, axis=1)
    xi = np.arctan2(skill_coords[:, 1], skill_coords[:, 0])

    occupation_df = occupation_df[['O*NET-SOC Code', 'Title']].drop_duplicates()

        # Slå ihop PCA-koordinater och metadata till en dataframe
    final_df = pd.DataFrame({
        'Occupation Code': skill_matrix.index,
        'Title': occupation_df.set_index('O*NET-SOC Code').loc[skill_matrix.index, 'Title'].values,
        'PC1': skill_coords[:, 0],
        'PC2': skill_coords[:, 1],
        'Cluster': labels
    })

    # Lägg till polära koordinater
    final_df['Chi'] = np.linalg.norm(skill_coords, axis=1)
    final_df['Xi'] = np.arctan2(skill_coords[:, 1], skill_coords[:, 0])

    # Lägg till entropi
    def scaled_entropy(row):
        values = row.values + 1e-9
        probs = values / values.sum()
        base_entropy = entropy(probs, base=2)
        logsum = np.log2(values.sum())
        return base_entropy * logsum

    final_df['H'] = skill_matrix.apply(scaled_entropy, axis=1).values

    # Välj representativa yrken för varje kluster
    representatives_df = select_representative_occupations(final_df)

    # Skapa klusternamn från dessa representanter
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
        
        Parameters:
            df (pd.DataFrame): Must contain 'Cluster', 'Chi', and 'Xi'.
        
        Returns:
            pd.DataFrame: Same as input but with updated 'Cluster' and 'Cluster Name' fields.
        """
        # Beräkna centroid (medelposition) för varje kluster
        centroids = df.groupby('Cluster')[['Chi', 'Xi']].mean()
        
        # Sortera efter vinkel Xi
        sorted_clusters = centroids.sort_values('Xi').index.tolist()
        
        # Skapa en mapping från gammalt till nytt ID
        cluster_mapping = {old_id: new_id for new_id, old_id in enumerate(sorted_clusters)}
        
        # Uppdatera dataramen
        df['Cluster'] = df['Cluster'].map(cluster_mapping)
        
        # Om kolumnen 'Cluster Name' finns, uppdatera även den
        if 'Cluster Name' in df.columns:
            df['Cluster Name'] = df['Cluster'].astype(str) + ': ' + df['Cluster Name'].str.extract(r': (.*)')[0]
        
        return df
    
    final_df = reorder_clusters_by_angle(final_df)
    cluster_names = name_clusters_by_representative_titles(representatives_df)
    final_df['Cluster Name'] = final_df['Cluster'].map(cluster_names)

    # Spara till cache
    final_df.to_csv(cache_file, index=False)
    return final_df


def select_representative_occupations(df):
    """
    Select one representative occupation per cluster based on proximity to cluster centroid.

    Parameters:
        df (pd.DataFrame): A DataFrame with columns 'Cluster', 'PC1', 'PC2', and occupation identifiers.

    Returns:
        pd.DataFrame: Filtered DataFrame with one representative per cluster.
    """
    representatives = []
    for cluster_id in df['Cluster'].unique():
        cluster_df = df[df['Cluster'] == cluster_id]
        centroid = cluster_df[['PC1', 'PC2']].mean().values
        distances = ((cluster_df[['PC1', 'PC2']].values - centroid) ** 2).sum(axis=1)
        best_idx = distances.argmin()
        representatives.append(cluster_df.iloc[best_idx])
    return pd.DataFrame(representatives)


