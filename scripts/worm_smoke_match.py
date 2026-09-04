"""
worm_smoke_match.py  (placera i scripts/)
-----------------------------------------
Databaslöst smoke-test av den euklidiska matchningskärnan.
Verifierar att geometrin fungerar utan att worm.sqlite3 behöver finnas.

    python scripts/worm_smoke_match.py
"""
import os
import sys

import numpy as np
import pandas as pd


def find_repo_root(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, "core")) and os.path.isdir(os.path.join(d, "scenarios")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            raise RuntimeError("Hittade ingen repo-rot (mapp med core/ och scenarios/).")
        d = parent


sys.path.insert(0, find_repo_root(os.path.dirname(__file__)))

from core.occupations.utils import (
    global_greedy_matching,
    sample_centers_xy_jitter,
    apply_capability_update,
)

rng = np.random.default_rng(0)
N, M = 300, 320


def sample_disc(n):
    r = np.sqrt(rng.uniform(0, 1, n))
    t = rng.uniform(0, 2 * np.pi, n)
    return r * np.cos(t), r * np.sin(t)


ix, iy = sample_disc(N)
jx, jy = sample_disc(M)

individuals = pd.DataFrame({
    "individual_id": np.arange(N),
    "x_occ": ix, "y_occ": iy,
    "r_i": np.zeros(N),          # färsk arbetare = punkt i planet
    "w_res": rng.uniform(0.3, 0.7, N),         # reservationslön i löneandelar
    "x": rng.uniform(0, 30_000, N), "y": rng.uniform(0, 30_000, N),
})
jobs = pd.DataFrame({
    "job_id": np.arange(1000, 1000 + M),
    "x_occ": jx, "y_occ": jy,
    "r_o": rng.uniform(0.10, 0.40, M),
    "wage": rng.uniform(0.5, 1.8, M),          # relativlön ur prisfältet
    "x": rng.uniform(0, 30_000, M), "y": rng.uniform(0, 30_000, M),
})

# 1. Euklidisk matchning
res = global_greedy_matching(individuals, jobs, sigma_gamma=0.6,
                             commute_cost_per_km=0.005, min_surplus=0.0)
assert len(res) > 0, "Ingen matchning – kontrollera x_occ/y_occ/r_o"
assert (res["surplus"] > 0).all(), "Alla matchningar ska ha positivt överskott"
print(f"[1] Matchning OK: {len(res)} par, medel-överskott {res['surplus'].mean():.4f} (alla > 0)")

# 2. Kartesisk sampler håller sig i enhetsskivan
xs, ys = sample_centers_xy_jitter(jx, jy, np.ones(M), 500, sigma_xy=0.1)
rmax = float(np.hypot(xs, ys).max())
assert rmax <= 1.0 + 1e-9, f"Sampler utanför skivan: r={rmax}"
print(f"[2] Sampler OK: max radie {rmax:.3f} (<= 1.0)")

# 3. Bytarkostnad: ren fördjupning gratis, omorientering kostar djup
chi_a, *_ = apply_capability_update(0.5, 0.0, 0.0, delta_chi=0.1, switch_cost_kappa=0.05)
chi_b, xi_b, ri_b, xb, yb = apply_capability_update(0.5, 0.0, 0.0, delta_xi=1.5, switch_cost_kappa=0.05)
assert abs(chi_a - 0.6) < 1e-9, "Radiell fördjupning ska inte kosta"
assert chi_b < 0.5, "Omorientering ska kosta djup"
assert abs(xb - chi_b * np.cos(xi_b)) < 1e-9, "x_occ ur synk med chi/xi"
assert ri_b > 0, "Erfarenhetsradien ska växa vid förflyttning"
print(f"[3] Dynamik OK: fördjupning 0.5->{chi_a:.3f}, omorientering 0.5->{chi_b:.3f}, r_i 0->{ri_b:.3f}")

print("\nAlla smoke-tester passerade.")
