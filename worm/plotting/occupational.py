
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
import numpy as np

def plot_occupation_space(df, xi_col='Xi', chi_col='Chi', h_col='H',
                          bubble_scale=0.5, labels=False, title="Occupation Space"):
    df['X'] = df[chi_col] * np.cos(df[xi_col])
    df['Y'] = df[chi_col] * np.sin(df[xi_col])

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_aspect('equal')
    ax.set_title(title, fontsize=13)

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['left'].set_position('center')
    ax.spines['bottom'].set_position('center')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(False)

    r_max = df[chi_col].max() + 5
    r_rings = np.arange(5, r_max, 5)
    theta_lines = np.linspace(0, 2 * np.pi, 12, endpoint=False)

    ax.set_xlim(-r_max, r_max)
    ax.set_ylim(-r_max, r_max)

    for r in r_rings:
        ring = plt.Circle((0, 0), r, color='gray', fill=False, linestyle='--', linewidth=0.5)
        ax.add_artist(ring)
        ax.text(r, 0.5, f'{r:.0f}', fontsize=8, color='gray')

    for theta in theta_lines:
        ax.plot([0, r_max * np.cos(theta)], [0, r_max * np.sin(theta)],
                color='gray', linestyle='--', linewidth=0.5)

    H_max = df[h_col].max()
    for _, row in df.iterrows():
        x, y, H = row['X'], row['Y'], row[h_col]
        ax.plot(x, y, 'go', markersize=3)
        if labels and "Title" in row:
            ax.text(x, y, row["Title"], fontsize=6, ha='center', va='center', alpha=0.7)
        radius = bubble_scale * (H / H_max)
        bubble = Circle((x, y), radius=radius, transform=ax.transData, facecolor='green', alpha=0.4)
        ax.add_patch(bubble)

    return fig, ax

def plot_occupation_space_clusters(df, label_subset=None, save_path=None):
    import matplotlib.pyplot as plt
    import matplotlib.cm as cm
    import numpy as np

    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_facecolor("white")

    # Färgkarta för kluster
    n_clusters = df['Cluster'].nunique()
    colormap = cm.get_cmap("tab20", n_clusters)
    colors = df["Cluster"].apply(lambda c: colormap(c))

    # Bubblor
    sizes = np.clip(df["H"].values * 200, 20, 500)
    scatter = ax.scatter(
        df["PC1"], df["PC2"],
        s=sizes,
        c=colors,
        alpha=0.7,
        edgecolors='k',
        linewidths=0.5
    )

    # Etiketter – valfritt
    if label_subset is not None:
        for _, row in df[df['Title'].isin(label_subset)].iterrows():
            ax.text(row["PC1"], row["PC2"], row["Title"],
                    fontsize=8, ha='center', va='center',
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="gray", lw=0.5))

    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title("Occupation Space by Skill Cluster")

    # Ingen ram
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    if save_path:
        plt.savefig(save_path, bbox_inches="tight", dpi=300)
    else:
        plt.show()

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from matplotlib.cm import get_cmap
from matplotlib.lines import Line2D

def plot_full_occupation_space_polar(
    df: pd.DataFrame,
    clusterlabels: bool = True,
    show_axes: bool = True,
    figsize=(10, 10),
    save_path: str = None
):
    """
    Plot all occupations in polar-like space, color-coded by cluster.

    Parameters:
        df (pd.DataFrame): DataFrame with 'Chi', 'Xi', 'Cluster', and 'Cluster Name'.
        clusterlabels (bool): If True, display cluster IDs in the center of each cluster.
        show_axes (bool): If True, display radial and circular gridlines.
        figsize (tuple): Size of the figure.
        save_path (str): Path to save the figure (optional).
    """
    fig, ax = plt.subplots(figsize=figsize, subplot_kw={'projection': 'polar'})

    cmap = get_cmap('tab20')
    clusters = sorted(df['Cluster'].unique())
    colors = {cluster: cmap(cluster % 20) for cluster in clusters}

    # Plot each occupation as a small dot
    for cluster in clusters:
        sub_df = df[df['Cluster'] == cluster]
        ax.scatter(sub_df['Xi'], sub_df['Chi'], s=10, color=colors[cluster], alpha=0.8)

    if clusterlabels:
        # Display cluster ID near visual centroid
        for cluster in clusters:
            sub_df = df[df['Cluster'] == cluster]
            mean_xi = sub_df['Xi'].mean()
            mean_chi = sub_df['Chi'].mean()
            ax.text(mean_xi, mean_chi, str(cluster), fontsize=8, ha='center', va='center', color='gray')

    if not show_axes:
        ax.set_axis_off()
    else:
        ax.set_rlabel_position(0)
        ax.grid(True, linestyle=':', alpha=0.4)

    # Build legend below the figure
    legend_elements = [
        Line2D([0], [0], marker='o', color='w',
               markerfacecolor=colors[cluster], markersize=6,
               label=f"{cluster}: {df[df['Cluster'] == cluster]['Cluster Name'].iloc[0]}")
        for cluster in clusters
    ]

    legend = ax.legend(
        handles=legend_elements,
        loc='lower center',
        bbox_to_anchor=(0.5, -0.38),  # Centrerad under figuren, justera -0.25 vid behov
        ncol=5,  # eller fler kolumner beroende på antal kluster
        fontsize=5,
        frameon=False
    )

    #plt.tight_layout()
    plt.subplots_adjust(top=0.92, bottom=0.25)

    if save_path:
        plt.savefig(save_path, bbox_inches='tight', dpi=300)
    else:
        plt.show()

    return fig, ax




