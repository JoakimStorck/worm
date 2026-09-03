"""
diagnose_mismatch.py  (placera i scripts/)
------------------------------------------
Diagnostiserar VARFÖR de kvarvarande arbetslösa inte matchas, genom att skilja
på två helt olika orsaker:

  GEOMETRISKT BLOCKERADE : bästa uppnåeliga nytta < utility_min. Ingen ledig
      vakans ligger nära nog i planet. Äkta strukturell mismatch.
  KONKURRENS/TAJMING     : bästa nytta >= utility_min, men individen fick ändå
      inget jobb. Vakansen fanns men gick till någon annan, eller söktillfället
      inföll fel.

Andelen mellan dessa avgör om sigma_gamma/utility_min är felkalibrerade eller om
friktionen är genuint geometrisk.

    python scripts/diagnose_mismatch.py output/run_YYYYMMDD_HHMMSS
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
        p = os.path.dirname(d)
        if p == d:
            raise RuntimeError("Hittade ingen repo-rot.")
        d = p


ROOT = find_repo_root(os.path.dirname(__file__))
sys.path.insert(0, ROOT)


def analyse(run_dir, sigma_gamma=0.6, utility_min=0.05, alpha_geo=0.1, chunk=2000):
    ind = pd.read_csv(os.path.join(run_dir, "final_state_individuals.csv"))
    jobs = pd.read_csv(os.path.join(run_dir, "final_state_jobs.csv"))

    unemp = ind[ind["status"] == "unemployed"].copy()
    vac = jobs[jobs["individual_id"].isna()].copy()
    print(f"Arbetslösa: {len(unemp)}   Vakanser: {len(vac)}")
    if unemp.empty or vac.empty:
        print("Inget att analysera.")
        return

    jx = vac["x_occ"].to_numpy(); jy = vac["y_occ"].to_numpy()
    jro = vac["r_o"].to_numpy()
    jgx = vac["x"].to_numpy(); jgy = vac["y"].to_numpy()

    best_u, best_d, best_geo = [], [], []
    ri_col = "r_i" if "r_i" in unemp.columns else None

    for s in range(0, len(unemp), chunk):
        b = unemp.iloc[s:s + chunk]
        ix = b["x_occ"].to_numpy()[:, None]; iy = b["y_occ"].to_numpy()[:, None]
        ri = (np.nan_to_num(b[ri_col].to_numpy())[:, None] if ri_col else 0.0)

        d = np.sqrt((ix - jx[None, :]) ** 2 + (iy - jy[None, :]) ** 2)
        sigma2 = np.maximum((sigma_gamma ** 2) * (jro[None, :] ** 2 + ri ** 2), 1e-9)
        occ_prob = np.exp(-0.5 * d ** 2 / sigma2)

        gkm = np.sqrt((b["x"].to_numpy()[:, None] - jgx[None, :]) ** 2 +
                      (b["y"].to_numpy()[:, None] - jgy[None, :]) ** 2) / 1000.0
        u = occ_prob * np.exp(-alpha_geo * gkm)

        k = u.argmax(axis=1)
        best_u.append(u[np.arange(len(b)), k])
        best_d.append(d[np.arange(len(b)), k])
        best_geo.append(gkm[np.arange(len(b)), k])

    best_u = np.concatenate(best_u)
    best_d = np.concatenate(best_d)
    best_geo = np.concatenate(best_geo)

    blocked = best_u < utility_min
    n_b, n_c = int(blocked.sum()), int((~blocked).sum())
    print(f"\nGeometriskt blockerade : {n_b:5d} ({100*n_b/len(best_u):.1f} %)")
    print(f"Konkurrens/tajming     : {n_c:5d} ({100*n_c/len(best_u):.1f} %)")

    print("\nBästa uppnåeliga nytta (alla arbetslösa):")
    for q in (10, 25, 50, 75, 90):
        print(f"  p{q:<3d} {np.percentile(best_u, q):.4f}")

    print("\nAvstånd i planet till bästa vakans:")
    print(f"  median {np.median(best_d):.3f}   p90 {np.percentile(best_d, 90):.3f}")
    print("Geografiskt avstånd till bästa vakans (km):")
    print(f"  median {np.median(best_geo):.1f}   p90 {np.percentile(best_geo, 90):.1f}")

    # Hur mycket skulle en mjukare kalibrering hjälpa?
    print("\nAndel geometriskt blockerade vid andra trösklar:")
    for um in (0.01, 0.03, 0.05, 0.10):
        print(f"  utility_min={um:<5} -> {100*(best_u < um).mean():.1f} %")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        outdir = os.path.join(ROOT, "output")
        # Endast kataloger som faktiskt HAR sluttillstånd, senast ändrad först
        cands = [os.path.join(outdir, d) for d in os.listdir(outdir)
                 if os.path.isfile(os.path.join(outdir, d, "final_state_individuals.csv"))]
        if not cands:
            raise SystemExit(
                "Hittade ingen körning med final_state_individuals.csv under output/.\n"
                "Kör en full simulering först (scenario_runner), eller ange katalog:\n"
                "  python scripts/diagnose_mismatch.py output/run_YYYYMMDD_HHMMSS")
        run_dir = max(cands, key=os.path.getmtime)
        print(f"(ingen katalog angiven – använder senaste: {os.path.basename(run_dir)})\n")
    else:
        run_dir = sys.argv[1]
    analyse(run_dir)
