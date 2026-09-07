"""
core/visualization/paperstyle.py
--------------------------------
Papper 1:s visuella språk, så att figurer ur WORM kan ställas bredvid
papprens utan att skava.

Avläst ur geometry-of-work (gts_plot._ax_style, gts_core.fam_color,
gts_plot.SHORT): polär axel med r_max 0.9, r-ticks var 0.1, r-etiketter vid
12 grader i grått, noll i öster, moturs, vinkelrutnät var 45 grader, streckat
grått rutnät med alpha 0.4 och bakgrunden #f7f7f7. Yrkesfamiljer får färg ur
tab20 i alfabetisk ordning. Titlar 11 pt fetstil, familjelegend 7.5 pt.
"""
from __future__ import annotations

import math

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

# ── Kortnamn för yrkesfamiljer (identisk med gts_plot.SHORT) ────────────────
SHORT = {
    'Architecture and Engineering':                   'Arch. & Eng.',
    'Arts, Design, Entertainment, Sports, and Media': 'Arts & Media',
    'Building and Grounds Cleaning and Maintenance':  'Building & Grounds',
    'Business and Financial Operations':              'Business & Finance',
    'Community and Social Service':                   'Community & Social',
    'Computer and Mathematical':                      'Computer & Math',
    'Construction and Extraction':                    'Construction',
    'Educational Instruction and Library':            'Education',
    'Farming, Fishing, and Forestry':                 'Farming',
    'Food Preparation and Serving Related':           'Food & Serving',
    'Healthcare Practitioners and Technical':         'Healthcare Pract.',
    'Healthcare Support':                             'Healthcare Support',
    'Installation, Maintenance, and Repair':          'Install. & Maint.',
    'Legal':                                          'Legal',
    'Life, Physical, and Social Science':             'Life & Science',
    'Management':                                     'Management',
    'Office and Administrative Support':              'Office & Admin',
    'Personal Care and Service':                      'Personal Care',
    'Production':                                     'Production',
    'Protective Service':                             'Protective Service',
    'Sales and Related':                              'Sales',
    'Transportation and Material Moving':             'Transportation',
}

FACE = '#f7f7f7'
GRID = dict(color='gray', linewidth=0.4, alpha=0.4, ls='--')
DPI = 200


def family_colors(families):
    """tab20 i alfabetisk ordning, som gts_core."""
    fams = sorted(families)
    cmap = matplotlib.colormaps.get_cmap('tab20').resampled(max(len(fams), 1))
    return {g: cmap(i) for i, g in enumerate(fams)}


def polar_axes(ax, rmax=0.9):
    """Papper 1:s polärram."""
    ax.set_rmax(rmax)
    ax.set_rticks([round(0.1 * i, 1) for i in range(1, int(rmax * 10) + 1)])
    ax.set_rlabel_position(12)
    ax.tick_params(axis='y', labelsize=7, labelcolor='gray')
    ax.set_theta_zero_location('E')
    ax.set_theta_direction(1)
    ax.set_thetagrids(range(0, 360, 45), [f'{d}°' for d in range(0, 360, 45)],
                      fontsize=8)
    ax.grid(**GRID)
    ax.set_facecolor(FACE)
    return ax


def cartesian_axes(ax):
    """Samma språk för icke-polära paneler."""
    ax.set_facecolor(FACE)
    ax.grid(**GRID)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    ax.tick_params(labelsize=8)
    return ax


def title(ax, text, pad=18):
    ax.set_title(text, fontsize=11, fontweight='bold', pad=pad)


def footnote(fig, text, y=0.02):
    fig.text(0.5, y, text, ha='center', fontsize=8.5, color='#444444')


def save(fig, path, dpi=DPI):
    fig.savefig(path, bbox_inches='tight', dpi=dpi)
    plt.close(fig)
    print(f"Sparad: {path}")


def disc_grid(n=240):
    """Rutnät över enhetsskivan i kartesiska koordinater, med mask."""
    g = np.linspace(-1, 1, n)
    gx, gy = np.meshgrid(g, g)
    return gx, gy, (gx ** 2 + gy ** 2) <= 1.0


def to_polar(x, y):
    return np.arctan2(y, x) % (2 * math.pi), np.hypot(x, y)
