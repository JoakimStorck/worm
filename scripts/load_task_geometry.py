"""
load_task_geometry.py  (placera i scripts/ i WORM)
--------------------------------------------------
Läser den FÄRDIGA task-baserade geometrin från geometry-of-work (ingen embedding/
PCA körs här) och skriver den till WORM:s databas som tabellen onet_occupation_space
(drop-in: behåller onet_code, chi, xi och lägger till x_occ, y_occ, r_o).

Konvention: koordinaterna lagras i den SKALADE enhetsskivan,
    x_occ = chi*cos(xi),  y_occ = chi*sin(xi),   chi in [0,1]
så att euklidiskt avstånd, chi och task-radien r_o alla lever i samma enhet.
r_o (Ekv. 2) härleds ur task-filen som rt-viktad RMS-distans till centroiden,
skalad med samma r_max som chi, eftersom occupationsfilen inte bär r_o.

Full täckning: alla O*NET-koder i occ_meta tas med. Koder utan egen
task-geometri ärver sitt familjecentrum (geom_source='family'); kvarvarande
saknade får global median (geom_source='global'). Så varje kod WORM refererar
via SNI-mappningen får en position.

Kopiera dessa fyra filer från geometry-of-works valda körning till EXPORT_DIR:
    occupation_embeddings_polar_scaled.csv
    task_embeddings_polar_scaled.csv
    job_family_centers_polar_scaled.csv
    occ_meta.csv
    radial_scale.json          (valfri men rekommenderad: exakt skalfaktor)
    wage_field_coefficients.csv (valfri: prisfält Π från technology-fields;
                                 ger w_rel per yrke och tabellen wage_field_coefficients)
Primär körning i pappret: openai text-embedding-3-large d3072 v30_1.
"""
import os
import json
import sqlite3
import numpy as np
import pandas as pd

sys_path_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
import sys
if sys_path_root not in sys.path:
    sys.path.insert(0, sys_path_root)
from core.occupations.price_field import PriceField

EXPORT_DIR = "data/geometry"          # dit du kopierat CSV-filerna
DB_PATH    = "data/worm.sqlite3"


def _radial_scale(export_dir, occ):
    """Skalparametrar (r0, r1) ur radial_scale.json om den finns, annars härledda.

    chi = (r - r0) / (r1 - r0). I läget 'zero_max' är r0 = 0 och r1 = max-radien.
    Att läsa filen är säkrare än att härleda, eftersom percentilbaserade lägen
    kan ha r0 != 0 vilket gor kvoten r/chi missvisande.
    """
    path = os.path.join(export_dir, "radial_scale.json")
    if os.path.exists(path):
        with open(path) as f:
            cfg = json.load(f)
        rot = float(cfg.get("SECTOR_ROTATION", 0.0))
        r0, r1 = float(cfg.get("r0", 0.0)), float(cfg["r1"])
        print(f"skala: radial_scale.json (mode={cfg.get('mode','?')}, r0={r0:.6f}, r1={r1:.6f})")
        if rot:
            print(f"OBS: SECTOR_ROTATION={rot} — kompassetiketterna i panelen kan behöva roteras.")
        # Konsistenskontroll: stämmer filens skala med CSV-filernas chi?
        derived = float(np.median((occ["r"] - r0) / occ["chi"])) + r0
        if abs(derived - r1) / max(r1, 1e-9) > 0.001:
            print(f"VARNING: härledd skala {derived:.6f} avviker >0.1% från r1={r1:.6f}. "
                  f"Kommer radial_scale.json och CSV-filerna från SAMMA körning?")
        return r0, r1
    # Fallback: anta r0 = 0
    print("skala: radial_scale.json SAKNAS — härleder ur median(r/chi). "
          "Kopiera filen för exakt skala.")
    return 0.0, float(np.median(occ["r"] / occ["chi"]))


def _scaled_xy(df):
    return df["chi"] * np.cos(df["xi"]), df["chi"] * np.sin(df["xi"])


def build_tables(export_dir=EXPORT_DIR):
    occ  = pd.read_csv(os.path.join(export_dir, "occupation_embeddings_polar_scaled.csv"))
    task = pd.read_csv(os.path.join(export_dir, "task_embeddings_polar_scaled.csv"))
    fam  = pd.read_csv(os.path.join(export_dir, "job_family_centers_polar_scaled.csv"))
    meta = pd.read_csv(os.path.join(export_dir, "occ_meta.csv"))

    r0, r1 = _radial_scale(export_dir, occ)
    r_max = r1 - r0                                   # chi = (r - r0) / (r1 - r0)

    # --- r_o per yrke: rt-viktad RMS-distans (pc1,pc2)->centroid, skalad ---
    cent = occ.set_index("onet_code")[["pc1", "pc2"]]
    def occ_radius(g):
        w = g["rt"].to_numpy(dtype=float)
        if w.sum() <= 0 or len(g) == 1:
            return np.nan
        w = w / w.sum()
        cx, cy = cent.loc[g.name]
        d2 = (g["pc1"] - cx) ** 2 + (g["pc2"] - cy) ** 2
        return float(np.sqrt((w * d2).sum()) / r_max)
    r_o = task.groupby("onet_code").apply(occ_radius, include_groups=False).rename("r_o")
    occ = occ.merge(r_o, on="onet_code", how="left")
    occ["r_o"] = occ["r_o"].fillna(occ.groupby("Job Family")["r_o"].transform("median"))
    occ["x_occ"], occ["y_occ"] = _scaled_xy(occ)

    # --- Prisfält Π och bundle-lön (om koefficientfil finns) ---------------
    pf_path = os.path.join(export_dir, "wage_field_coefficients.csv")
    pf = None
    if os.path.exists(pf_path):
        pf0 = PriceField.from_csv(pf_path)
        # Bundle-lön: w_o = sum_t b_t Π(r_t), b = rt normerad per yrke (Technology fields)
        tw = task.dropna(subset=["xi", "chi", "rt"]).copy()
        tw["b"] = tw["rt"] / tw.groupby("onet_code")["rt"].transform("sum")
        tw["pi_t"] = pf0.pi(tw["xi"].to_numpy(), tw["chi"].to_numpy())
        w_bundle = (tw["b"] * tw["pi_t"]).groupby(tw["onet_code"]).sum().rename("w_bundle_abs")
        occ = occ.merge(w_bundle, on="onet_code", how="left")
        occ["pi_centroid_abs"] = pf0.pi(occ["xi"].to_numpy(), occ["chi"].to_numpy())
        # Normera till relativpris: medel 1 över yrken med egen geometri
        norm = float(occ["w_bundle_abs"].mean())
        pf = pf0.with_norm(norm)
        occ["w_rel"] = occ["w_bundle_abs"] / norm
        occ["pi_rel"] = occ["pi_centroid_abs"] / norm
        occ["w_rel"] = occ["w_rel"].fillna(occ["pi_rel"])      # enstaka-task-yrken
        print(f"prisfält: laddat (spec S1_field), norm = {norm:.4f}; "
              f"w_rel spann {occ['w_rel'].min():.3f}–{occ['w_rel'].max():.3f}")
    else:
        occ["w_rel"] = np.nan; occ["pi_rel"] = np.nan
        print("prisfält: wage_field_coefficients.csv SAKNAS — w_rel/pi_rel blir NaN.")

    # --- Familjegeometri (centrum + familje-r_o ur tasks) ---
    fam = fam.rename(columns={"Job Family": "job_family"})
    fam_cent = fam.set_index("job_family")[["pc1", "pc2"]]
    def fam_radius(g):
        w = g["rt"].to_numpy(dtype=float); w = w / w.sum()
        cx, cy = fam_cent.loc[g.name]
        d2 = (g["pc1"] - cx) ** 2 + (g["pc2"] - cy) ** 2
        return float(np.sqrt((w * d2).sum()) / r_max)
    fam["r_o"] = fam["job_family"].map(task.groupby("Job Family").apply(fam_radius, include_groups=False))
    fam["x_occ"], fam["y_occ"] = _scaled_xy(fam)
    fam_geom = fam[["job_family", "xi", "chi", "x_occ", "y_occ", "r_o"]].copy()

    # --- Full tabell: alla occ_meta-koder, fallback till familj, sedan global ---
    direct = occ[["onet_code", "Title", "Job Family", "xi", "chi", "x_occ", "y_occ", "r_o",
                  "w_rel", "pi_rel"]].copy()
    direct["geom_source"] = "occupation"
    full = meta[["onet_code", "Title", "Job Family"]].merge(
        direct.drop(columns=["Title", "Job Family"]), on="onet_code", how="left")

    miss = full["x_occ"].isna()
    if miss.any():
        fam_lookup = fam_geom.set_index("job_family")
        for col in ["xi", "chi", "x_occ", "y_occ", "r_o"]:
            full.loc[miss, col] = full.loc[miss, "Job Family"].map(fam_lookup[col])
        if pf is not None:
            # Familje-fallback för lön: Π vid familjecentrum
            full.loc[miss, "pi_rel"] = pf.pi_rel(full.loc[miss, "xi"].to_numpy(),
                                                 full.loc[miss, "chi"].to_numpy())
            full.loc[miss, "w_rel"] = full.loc[miss, "pi_rel"]
        full.loc[miss & full["x_occ"].notna(), "geom_source"] = "family"

    still = full["x_occ"].isna()
    if still.any():
        full.loc[still, "x_occ"] = occ["x_occ"].mean()
        full.loc[still, "y_occ"] = occ["y_occ"].mean()
        full.loc[still, "chi"]   = np.hypot(occ["x_occ"].mean(), occ["y_occ"].mean())
        full.loc[still, "xi"]    = np.arctan2(occ["y_occ"].mean(), occ["x_occ"].mean()) % (2*np.pi)
        full.loc[still, "r_o"]   = occ["r_o"].median()
        if pf is not None:
            full.loc[still, "pi_rel"] = pf.pi_rel(full.loc[still, "xi"].to_numpy(),
                                                  full.loc[still, "chi"].to_numpy())
            full.loc[still, "w_rel"] = full.loc[still, "pi_rel"]
        full.loc[still, "geom_source"] = "global"

    occ_geom = full[["onet_code", "Title", "Job Family", "xi", "chi",
                     "x_occ", "y_occ", "r_o", "w_rel", "pi_rel", "geom_source"]].copy()
    occ_geom["code_system"] = "onet_soc"     # vilket kodsystem onet_code är uttryckt i
    return occ_geom, fam_geom, r_max, pf


def write_to_db(occ_geom, fam_geom, db_path=DB_PATH, pf=None):
    conn = sqlite3.connect(db_path)
    occ_geom.to_sql("onet_occupation_space", conn, if_exists="replace", index=False)
    fam_geom.to_sql("onet_job_family_geometry", conn, if_exists="replace", index=False)
    if pf is not None:
        pd.DataFrame(pf.to_rows()).to_sql("wage_field_coefficients", conn,
                                          if_exists="replace", index=False)
    conn.commit(); conn.close()


if __name__ == "__main__":
    occ_geom, fam_geom, r_max, pf = build_tables()
    print(f"r_max = {r_max:.5f}")
    print(f"yrken totalt: {len(occ_geom)}")
    print(occ_geom["geom_source"].value_counts().to_string())
    print(occ_geom.head(5).to_string(index=False))
    write_to_db(occ_geom, fam_geom)   # avkommentera för att skriva till worm.sqlite3
