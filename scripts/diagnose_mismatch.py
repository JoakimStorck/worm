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


def _event_flows(run_dir):
    """Räknar sökningar, träffar och missar ur eventloggen. Svarar på frågan om
    de arbetslösa inte HITTAR jobb eller inte SÖKER."""
    path = os.path.join(run_dir, "eventlog.csv")
    if not os.path.isfile(path):
        return
    counts = {}
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            for key in ("match_completed", "match_failed", "job_destroyed_holder_displaced",
                        "vacancy_destroyed"):
                if key in line:
                    counts[key] = counts.get(key, 0) + 1
            if ", quit_job," in line:
                counts["quit_job"] = counts.get("quit_job", 0) + 1
            if ", start_job," in line:
                counts["start_job"] = counts.get("start_job", 0) + 1
    if not counts:
        return
    ok = counts.get("match_completed", 0)
    bad = counts.get("match_failed", 0)
    print("\nFlöden under körningen (ur eventloggen):")
    for k in ("quit_job", "job_destroyed_holder_displaced", "match_completed",
              "match_failed", "start_job", "vacancy_destroyed"):
        if k in counts:
            print(f"  {k:34s} {counts[k]:7d}")
    if ok + bad:
        print(f"  träffkvot vid sökning              {100*ok/(ok+bad):6.1f} %")


def analyse(run_dir, sigma_gamma=0.6, commute_cost_per_km=0.005, min_surplus=0.0):
    """Delar upp de arbetslösa efter VARFÖR de inte matchas.

    Använder samma överskottsformel som matchningskärnan:

        S = p * w_j - c * km - w_res

    Parametrarna ska stämma med scenariots simulation-block. Läses de fel
    mäter diagnosen en annan modell än den som kördes.
    """
    ind = pd.read_csv(os.path.join(run_dir, "final_state_individuals.csv"))
    jobs = pd.read_csv(os.path.join(run_dir, "final_state_jobs.csv"))

    unemp = ind[ind["status"] == "unemployed"].copy()
    vac = jobs[jobs["individual_id"].isna()].copy()
    n_all_vacant = len(vac)
    if "active" in jobs.columns:
        vac = vac[vac["active"].astype(bool)]
    print(f"Arbetslösa: {len(unemp)}   Vakanser: {len(vac)}"
          + (f"  (av {n_all_vacant} obesatta rader; {n_all_vacant - len(vac)} förstörda)"
             if n_all_vacant != len(vac) else ""))
    if "active" in jobs.columns:
        act = jobs["active"].astype(bool)
        print(f"Jobb: {int(act.sum())} aktiva, {int((~act).sum())} förstörda, "
              f"{int((act & jobs['individual_id'].notna()).sum())} tillsatta")
    if unemp.empty or vac.empty:
        print("Inget att analysera.")
        return

    has_wage = "wage" in vac.columns and vac["wage"].notna().any()
    has_res = "w_res" in unemp.columns and unemp["w_res"].notna().any()
    if not has_wage or not has_res:
        print("\nVARNING: jobben saknar lön eller individerna reservationslön. "
              "Diagnosen körs utan priser (S = w - c*km).")

    jx = vac["x_occ"].to_numpy(); jy = vac["y_occ"].to_numpy()
    jro = vac["r_o"].to_numpy()
    jw = vac["wage"].to_numpy() if has_wage else np.ones(len(vac))
    jgx = vac["x"].to_numpy(); jgy = vac["y"].to_numpy()

    best_s, best_d, best_geo, best_p = [], [], [], []
    ri_col = "r_i" if "r_i" in unemp.columns else None
    chunk = 2000
    for st in range(0, len(unemp), chunk):
        b = unemp.iloc[st:st + chunk]
        ix = b["x_occ"].to_numpy()[:, None]; iy = b["y_occ"].to_numpy()[:, None]
        ri = (np.nan_to_num(b[ri_col].to_numpy())[:, None] if ri_col else 0.0)
        wres = (np.nan_to_num(b["w_res"].to_numpy())[:, None] if has_res else 0.0)

        d = np.sqrt((ix - jx[None, :]) ** 2 + (iy - jy[None, :]) ** 2)
        sigma2 = np.maximum((sigma_gamma ** 2) * (jro[None, :] ** 2 + ri ** 2), 1e-9)
        p = np.exp(-0.5 * d ** 2 / sigma2)
        gkm = np.sqrt((b["x"].to_numpy()[:, None] - jgx[None, :]) ** 2 +
                      (b["y"].to_numpy()[:, None] - jgy[None, :]) ** 2) / 1000.0
        # S = w - c*km - w_res. Passformen p avgör anställningssannolikheten,
        # inte lönen.
        S = jw[None, :] - commute_cost_per_km * gkm - wres

        # Bästa möjliga: högsta överskott bland jobb med rimlig passform.
        viable = p > 0.05
        S_eff = np.where(viable, S, -np.inf)
        k = S_eff.argmax(axis=1)
        r = np.arange(len(b))
        no_viable = ~np.isfinite(S_eff[r, k])
        best_s.append(np.where(no_viable, np.nan, S[r, k]))
        best_d.append(d[r, k]); best_geo.append(gkm[r, k])
        best_p.append(p[r, k])

    best_s = np.concatenate(best_s)
    best_d = np.concatenate(best_d)
    best_geo = np.concatenate(best_geo)
    best_p = np.concatenate(best_p)

    n_none = int(np.isnan(best_s).sum())          # ingen vakans med rimlig passform
    blocked = np.nan_to_num(best_s, nan=-np.inf) <= min_surplus
    n_b, n_c = int(blocked.sum()), int((~blocked).sum())
    tightness = len(vac) / max(len(unemp), 1)
    print(f"\nMarknadstryck: {tightness:.2f} vakanser per arbetslös")
    if tightness < 0.5:
        print("  OBS: tunn vakanspool. När vakanserna är få sätts övergångarnas längd")
        print("  av knapphet snarare än av kärnbredden, och andelen 'blockerade'")
        print("  mäter kö snarare än geometri.")
    print(f"\nParametrar: sigma_gamma={sigma_gamma}, c={commute_cost_per_km}/km, "
          f"min_surplus={min_surplus}")
    print(f"Geometriskt blockerade : {n_b:5d} ({100*n_b/len(best_s):.1f} %)  "
          f"-- inget jobb ger positivt överskott")
    if n_none:
        print(f"  därav utan NÅGON vakans med rimlig passform: {n_none} "
              f"({100*n_none/len(best_s):.1f} %) -- kö, inte geometri, "
              f"om marknadstrycket är lågt")
    print(f"Konkurrens/tajming     : {n_c:5d} ({100*n_c/len(best_s):.1f} %)  "
          f"-- överskott fanns, men jobbet gick till någon annan")

    finite = best_s[np.isfinite(best_s)]
    if finite.size:
        print("\nBästa uppnåeliga överskott (bland dem som har någon möjlig vakans):")
        for q in (10, 25, 50, 75, 90):
            print(f"  p{q:<3d} {np.percentile(finite, q):+.4f}")

    print(f"\nAnställningssannolikhet vid bästa vakans: median {np.median(best_p):.3f}")
    print("\nAvstånd i planet till bästa vakans:")
    print(f"  median {np.median(best_d):.3f}   p90 {np.percentile(best_d, 90):.3f}")
    print("Geografiskt avstånd till bästa vakans (km):")
    print(f"  median {np.median(best_geo):.1f}   p90 {np.percentile(best_geo, 90):.1f}")
    if has_res:
        print(f"Reservationslön: median {np.median(unemp['w_res'].dropna()):.3f}")
    if has_wage:
        print(f"Vakansernas lön: median {np.median(jw):.3f}")

    _event_flows(run_dir)

    print("\nAndel blockerade vid andra pendlingskostnader:")
    for c in (0.001, 0.003, 0.005, 0.010):
        # approximativ: skala om den geografiska termen för bästa träffen
        adj = np.nan_to_num(best_s, nan=-np.inf) + (commute_cost_per_km - c) * best_geo
        print(f"  c={c:<6} -> {100*(adj <= min_surplus).mean():.1f} %")


def _params_from_scenario(path):
    """Läser simulation-blocket, så att diagnosen mäter samma modell som kördes."""
    try:
        import yaml
        cfg = yaml.safe_load(open(path, encoding="utf-8")).get("simulation", {})
    except Exception:
        return {}
    return {k: float(cfg[k]) for k in
            ("sigma_gamma", "commute_cost_per_km", "min_surplus") if k in cfg}


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
    scen = os.path.join(ROOT, "scenarios", "mora_baseline.yml")
    kw = _params_from_scenario(scen)
    if kw:
        print(f"(parametrar ur {os.path.basename(scen)}: "
              + ", ".join(f"{k}={v}" for k, v in kw.items()) + ")\n")
    analyse(run_dir, **kw)
