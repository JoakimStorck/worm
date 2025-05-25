
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
