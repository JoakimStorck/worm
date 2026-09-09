"""
figures.py  (scripts/)
----------------------
Resultatfigurer i papper 1:s visuella språk, så att de kan ställas bredvid
papprens utan att skava. Stilen ligger i core/visualization/paperstyle.py och
är avläst ur geometry-of-work.

    python scripts/figures.py                       # alla, senaste körningen
    python scripts/figures.py --only mobility
    python scripts/figures.py output/run_... --out figures/

Figurer:
  mobility    Fördelning av övergångslängder mot papper 2:s referensvärden.
              Yrkesbyten, återgångar och chefsövergångar var för sig.
  competence  Kompetenscirklarna för tre arbetare: nybörjare, mogen, och
              mogen efter tjugo års uppehåll. Individmodellens huvudfigur.
  coverage    Kommunens jobb som täthet över skivan -- tunnhet gjord synlig.
  tenure      Konkurrenskraften q som funktion av tid: inlärning, mättnad,
              glömska. Motiverar lambda, D och tau_s visuellt.
  wages       Lönespridning: fältlön mot förhandlad lön, totalt och inom yrke.
"""
import argparse
import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import PowerNorm
from matplotlib.lines import Line2D

from core.analysis import figio
from core.visualization import paperstyle as ps

REF_WITHIN, REF_GLOBAL, REF_CROSS = 0.70, 1.03, 1.93


def read_transitions(run_dir):
    """Övergångar ur den exporterade tabellen."""
    from core.analysis.eventlog import load_tables

    tr = load_tables(run_dir)["transitions"]
    if tr.empty or "u_R_occ" not in tr.columns:
        return pd.DataFrame(columns=["u_R", "changed", "mgmt"])
    return pd.DataFrame({
        "u_R": tr["u_R_occ"],
        "changed": tr["occ_change"].fillna(True).astype(bool),
        "mgmt": tr["is_mgmt"].fillna(False).astype(bool),
    }).dropna(subset=["u_R"])


# ---------------------------------------------------------------------------
def fig_mobility(run_dirs, out):
    """Fördelning av övergångslängder, med band över frön.

    En enskild körning är inte ett resultat när flera frön finns: figuren
    visar då ett godtyckligt utfall och läsaren får ingen uppfattning om
    osäkerheten."""
    from core.analysis.eventlog import ecdf_band, load_tables

    per_run, same_sh, mgmt_sh, mgmt_vals = {}, [], [], []
    for rd in run_dirs:
        try:
            tr = load_tables(rd)["transitions"]
        except Exception:
            continue
        if tr.empty or "u_R_occ" not in tr.columns:
            continue
        n = len(tr)
        ch = tr["occ_change"].fillna(True).astype(bool)
        mg = tr["is_mgmt"].fillna(False).astype(bool)
        same_sh.append(float((~ch).mean()))
        mgmt_sh.append(float((ch & mg).mean()))
        mgmt_vals.append(tr.loc[ch & mg, "u_R_occ"].dropna().to_numpy())
        cps = tr[tr["in_cps_sample"].fillna(False).astype(bool)]
        per_run[os.path.basename(str(rd).rstrip("/"))] = cps["u_R_occ"].dropna().to_numpy()

    if not per_run:
        print("mobility: inga övergångar med u_R_occ"); return
    band = ecdf_band(per_run)
    allv = np.concatenate(list(per_run.values()))
    n_runs = len(per_run)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), dpi=ps.DPI)
    ax = ps.cartesian_axes(axes[0])
    if n_runs > 1:
        ax.fill_between(band["x"], band["min"], band["max"], color="#1f77b4",
                        alpha=0.15, lw=0, label=f"spann över {n_runs} frön")
        ax.fill_between(band["x"], band["q25"], band["q75"], color="#1f77b4",
                        alpha=0.30, lw=0, label="kvartilavstånd")
    ax.plot(band["x"], band["median"], lw=1.8, color="#1f77b4",
            label="yrkesbyten (median)" if n_runs > 1 else "yrkesbyten")
    mv = np.concatenate([m for m in mgmt_vals if m.size]) if any(m.size for m in mgmt_vals) else np.array([])
    if mv.size:
        x = np.sort(mv)
        ax.plot(x, np.arange(1, x.size + 1) / x.size, lw=1.4, color="#ff7f0e",
                label="till/från chefsyrke")
    for v, lab, col in ((REF_WITHIN, "inom delsystem 0,70", "#2ca02c"),
                        (REF_GLOBAL, "globalt 1,03", "#7f7f7f"),
                        (REF_CROSS, "tvär 1,93", "#d62728")):
        ax.axvline(v, ls=":", lw=1.2, color=col)
        ax.text(v, 0.03, f" {lab}", fontsize=7, color=col, rotation=90, va="bottom")
    ax.set_xlim(0, 3.5); ax.set_ylim(0, 1)
    ax.set_xlabel("Övergångslängd $u_R$ (task-radier)", fontsize=9)
    ax.set_ylabel("Kumulativ andel", fontsize=9)
    ax.legend(fontsize=7.5, loc="lower right", framealpha=0.9)
    ps.title(ax, "Fördelning av övergångslängder", pad=10)

    ax2 = ps.cartesian_axes(axes[1])
    bins = np.linspace(0, 3.5, 40)
    ax2.hist(allv, bins=bins, color="#1f77b4", alpha=0.75, label="yrkesbyten")
    if mv.size:
        ax2.hist(mv, bins=bins, color="#ff7f0e", alpha=0.6, label="chefsyrken")
    med = float(np.median(allv))
    ax2.axvline(med, ls="--", lw=1.4, color="#1f77b4")
    ax2.axvline(REF_WITHIN, ls=":", lw=1.2, color="#2ca02c")
    ax2.set_xlabel("Övergångslängd $u_R$ (task-radier)", fontsize=9)
    ax2.set_ylabel("Antal", fontsize=9)
    ax2.legend(fontsize=7.5, framealpha=0.9)
    ps.title(ax2, f"Täthet ({n_runs} körning{'ar' if n_runs > 1 else ''})", pad=10)

    meds = [float(np.median(v)) for v in per_run.values() if v.size]
    spread = (f" (spann {min(meds):.2f}–{max(meds):.2f} över {n_runs} frön)"
              if n_runs > 1 else "")
    ps.footnote(fig, f"Median {med:.2f} task-radier mot 0,70 inom delsystem "
                     f"(papper 2){spread}. Återgång till eget yrke "
                     f"{100*np.mean(same_sh):.0f} % och chefsövergångar "
                     f"{100*np.mean(mgmt_sh):.0f} % utesluts; CPS räknar bara "
                     f"yrkesbyten, och tvärflödet är befordran.", y=-0.03)

    per = pd.DataFrame({"run": list(per_run), "n": [v.size for v in per_run.values()],
                        "median_u_R": meds})
    figio.write(fig, "mobility_distribution", out,
                data={"band": band, "per_run": per},
                run_dirs=run_dirs, save=ps.save,
                note="CDF av u_R för yrkesbyten utan chefsövergångar; band över frön.",
                extra={"ref_within": REF_WITHIN, "ref_global": REF_GLOBAL,
                       "ref_cross": REF_CROSS})


# ---------------------------------------------------------------------------
def fig_competence(out):
    """Individmodellens huvudfigur: samma arbetare i tre skeden."""
    from core.occupations.competence import Circles, CompetenceParams, seed_circles, EMPTY

    p = CompetenceParams()
    ro, cx, cy = 0.27, 0.42, 0.14

    def build(tenure, years_away, edu):
        c = Circles(1, 12)
        seed_circles(c, 0, "A", cx, cy, ro, tenure, edu, p)
        for _ in range(int(years_away * 12)):
            c.evolve(1 / 12, np.array([EMPTY]), p)
        return c

    panels = [(build(0.0, 0, 1), "Nybörjare\nbara grundskola"),
              (build(20.0, 0, 3), "Mogen arbetare\ntjugo år i yrket"),
              (build(20.0, 20, 3), "Samma arbetare\nefter tjugo års uppehåll")]

    # Polärt rutnät: pcolormesh kräver monotona koordinater, så fältet
    # samplas direkt i (theta, r) i stället för på ett kartesiskt rutnät.
    tg, rg = np.meshgrid(np.linspace(0, 2 * math.pi, 241),
                         np.linspace(0, 1.0, 121))
    gx, gy = rg * np.cos(tg), rg * np.sin(tg)
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.8), dpi=ps.DPI,
                             subplot_kw={"projection": "polar"})
    fields = []
    for c, _ in panels:
        f = np.zeros_like(gx)
        for j in range(c.K):
            if c.key[0, j] == EMPTY:
                continue
            d2 = (gx - c.x[0, j]) ** 2 + (gy - c.y[0, j]) ** 2
            f += (c.mass[0, j] * np.exp(-0.5 * d2 / max(c.rho2[0, j], 1e-9))
                  / (2 * math.pi * c.rho2[0, j]))
        fields.append(f)
    # Gemensam skala, men komprimerad: den mogna arbetarens spets är tvåhundra
    # gånger högre än nybörjarens golv, och med linjär skala syns bara den.
    vmax = max(np.nanmax(f) for f in fields)
    norm = PowerNorm(gamma=0.30, vmin=0.0, vmax=vmax)

    for ax, (c, lab), f in zip(axes, panels, fields):
        ps.polar_axes(ax, rmax=1.0)
        ax.set_rlabel_position(112)          # bort från yrkets position
        ax.pcolormesh(tg, rg, f, shading="auto", cmap="YlOrRd",
                      norm=norm, alpha=0.9, zorder=0)
        ax.contour(tg, rg, f, levels=[0.15 * vmax, 0.45 * vmax], colors="#8b0000",
                   linewidths=0.6, alpha=0.7, zorder=2)
        for j in range(c.K):
            if c.key[0, j] == EMPTY:
                continue
            t, r = ps.to_polar(c.x[0, j], c.y[0, j])
            ax.plot([t], [r], marker="D", ms=4, color="#333333", zorder=3)
        tj, rj = ps.to_polar(cx, cy)
        ax.plot([tj], [rj], marker="*", ms=13, color="#1f77b4", zorder=4)
        q = float(c.competitiveness(0, [cx], [cy], [ro], p)[0])
        ps.title(ax, lab, pad=14)
        ax.text(0.5, -0.13, f"konkurrenskraft i yrket:  q = {q:.2f}",
                transform=ax.transAxes, ha="center", fontsize=9)

    fig.legend(handles=[Line2D([], [], marker="*", ls="", ms=11, color="#1f77b4",
                               label="yrkets position"),
                        Line2D([], [], marker="D", ls="", ms=5, color="#333333",
                               label="kompetenscirkelns centrum")],
               loc="lower center", ncol=2, fontsize=8, framealpha=0.9,
               bbox_to_anchor=(0.5, -0.04))
    ps.footnote(fig, "Kompetensen är en summa av cirklar, en per erfarenhet. Massan bevaras "
                     "men diffunderar när den inte används: spetsen går förlorad, resten "
                     "finns kvar. Gemensam färgskala, komprimerad ($\\gamma$ = 0,3), "
                     "eftersom spetsen är tvåhundra gånger högre än golvet.", y=-0.10)
    rows = []
    for (c, lab), f in zip(panels, fields):
        for j in range(c.K):
            if c.key[0, j] == EMPTY:
                continue
            rows.append({"panel": lab.replace("\n", " "),
                         "circle": c.key_names[c.key[0, j]],
                         "x": c.x[0, j], "y": c.y[0, j],
                         "rho": float(np.sqrt(c.rho2[0, j])), "mass": c.mass[0, j]})
    qs = pd.DataFrame({"panel": [l.replace("\n", " ") for _, l in panels],
                       "q": [float(c.competitiveness(0, [cx], [cy], [ro], p)[0])
                             for c, _ in panels]})
    figio.write(fig, "competence_circles", out,
                data={"circles": pd.DataFrame(rows), "q": qs},
                save=ps.save,
                note="Kompetenscirklar för samma arbetare i tre skeden.",
                extra={"lambda_half_life_years": float(np.log(2) / p.lam),
                       "D": p.D, "tau_months": p.tau_months, "m_ref": p.m_ref,
                       "gamma": p.gamma, "job": {"x": cx, "y": cy, "r_o": ro}})


# ---------------------------------------------------------------------------
def fig_coverage(run_dirs, out, s=0.25):
    """Kommunens jobb som täthet över skivan. Tunnhet gjord synlig."""
    tg, rg = np.meshgrid(np.linspace(0, 2 * math.pi, 241),
                         np.linspace(0, 1.0, 121))
    gx, gy = rg * np.cos(tg), rg * np.sin(tg)
    n = len(run_dirs)
    cov_rows = []
    fig, axes = plt.subplots(1, n, figsize=(4.6 * n, 4.8), dpi=ps.DPI,
                             subplot_kw={"projection": "polar"}, squeeze=False)
    for ax, rd in zip(axes[0], run_dirs):
        jobs = pd.read_csv(os.path.join(rd, "final_state_jobs.csv"))
        if "active" in jobs.columns:
            jobs = jobs[jobs["active"].astype(bool)]
        x = jobs["x_occ"].dropna().to_numpy(); y = jobs["y_occ"].dropna().to_numpy()
        f = np.zeros_like(gx)
        covered = np.zeros(gx.shape, dtype=bool)
        for st in range(0, x.size, 400):
            bx, by = x[st:st + 400], y[st:st + 400]
            d2 = (gx[..., None] - bx) ** 2 + (gy[..., None] - by) ** 2
            f += np.exp(-0.5 * d2 / 0.05 ** 2).sum(axis=-1)
            covered |= (d2.min(axis=-1) <= s * s)
        # C(s): ytandel av skivan inom s från någon position. Cellerna i ett
        # polärt rutnät har arean r*dr*dtheta, så vikta med r.
        C = float((covered * rg).sum() / rg.sum())

        ps.polar_axes(ax, rmax=1.0)
        ax.set_rlabel_position(112)
        ax.pcolormesh(tg, rg, f / np.nanmax(f), shading="auto", cmap="YlOrRd",
                      vmin=0, vmax=1, alpha=0.9, zorder=0)
        ps.title(ax, os.path.basename(rd.rstrip("/")), pad=14)
        ax.text(0.5, -0.13, f"{len(jobs)} positioner    C({s}) = {C:.2f}",
                transform=ax.transAxes, ha="center", fontsize=9)
        cov_rows.append({"run": os.path.basename(str(rd).rstrip("/")),
                         "n_positions": len(jobs), f"C_{s}": C})
    ps.footnote(fig, f"Täthet av lediga och tillsatta positioner i uppgiftsrummet. "
                     f"C({s}) är andelen av skivan inom {s} task-enheter från någon position: "
                     f"ett direkt mått på uppgiftsrummets tjocklek.", y=-0.06)
    figio.write(fig, "coverage", out, data=pd.DataFrame(cov_rows),
                run_dirs=run_dirs, save=ps.save,
                note="Positionernas täthet i uppgiftsrummet per körning.",
                extra={"s": s})


# ---------------------------------------------------------------------------
def fig_tenure(out):
    """Konkurrenskraften över tid: inlärning, mättnad, glömska.

    De tre parametrarna lambda, D och tau_s är svåra att försvara i text utan
    bild. Här syns deras tidsskalor direkt."""
    from core.occupations.competence import Circles, CompetenceParams, seed_circles, EMPTY

    p = CompetenceParams()
    ro, cx, cy = 0.27, 0.42, 0.14
    months = 40 * 12

    def trace(years_work, then_away):
        c = Circles(1, 12)
        seed_circles(c, 0, "A", cx, cy, ro, 0.01, 3, p)
        k = c.code("A")
        qs, ms, rs = [], [], []
        for m in range(months):
            active = np.array([k if m < years_work * 12 else EMPTY])
            c.evolve(1 / 12, active, p)
            qs.append(float(c.competitiveness(0, [cx], [cy], [ro], p)[0]))
            j = np.flatnonzero(c.key[0] == k)
            ms.append(float(c.mass[0, j[0]]) if j.size else 0.0)
            rs.append(float(np.sqrt(c.rho2[0, j[0]])) if j.size else np.nan)
        return np.array(qs), np.array(ms), np.array(rs)

    t = np.arange(months) / 12.0
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.0), dpi=ps.DPI)

    ax = ps.cartesian_axes(axes[0])
    for yrs, col in ((40, "#1f77b4"), (10, "#ff7f0e"), (3, "#2ca02c")):
        q, _, _ = trace(yrs, True)
        ax.plot(t, q, lw=1.8, color=col, label=f"{yrs} år i yrket")
        if yrs < 40:
            ax.axvline(yrs, ls=":", lw=0.9, color=col, alpha=0.7)
    ax.set_xlabel("År", fontsize=9); ax.set_ylabel("Konkurrenskraft $q$", fontsize=9)
    ax.set_ylim(0, 1.05); ax.set_xlim(0, 40)
    ax.legend(fontsize=7.5, loc="lower left", framealpha=0.9)
    ps.title(ax, "Inlärning och glömska", pad=10)

    ax = ps.cartesian_axes(axes[1])
    q40, m40, r40 = trace(40, False)
    m_sat = p.a / p.lam
    ax.plot(t, m40, lw=1.8, color="#1f77b4")
    ax.axhline(m_sat, ls="--", lw=1.0, color="#7f7f7f")
    ax.text(1.0, m_sat * 1.02, f"mättnad $a/\\lambda$ = {m_sat:.1f}", fontsize=8, color="#555555")
    ax.set_xlabel("År i yrket", fontsize=9); ax.set_ylabel("Massa", fontsize=9)
    ax.set_xlim(0, 40)
    ps.title(ax, "Massan mättas: läckaget sätter taket", pad=10)

    ax = ps.cartesian_axes(axes[2])
    q10, _, r10 = trace(10, True)
    ax.plot(t, r10, lw=1.8, color="#ff7f0e", label="cirkelns radie $\\rho$")
    ax.axhline(ro, ls="--", lw=1.0, color="#7f7f7f")
    ax.text(25, ro * 1.06, "yrkets radie $r_o$", fontsize=8, color="#555555")
    ax.axvline(10, ls=":", lw=0.9, color="#ff7f0e", alpha=0.7)
    ax.text(10.6, 0.80, "slutar arbeta", fontsize=8, color="#555555")
    ax.set_xlabel("År", fontsize=9); ax.set_ylabel("Radie", fontsize=9)
    ax.set_xlim(0, 40)
    ps.title(ax, "Diffusionen breddar cirkeln", pad=10)

    ps.footnote(fig, f"Läckage med halveringstid {np.log(2)/p.lam:.0f} år, diffusion "
                     f"D = {p.D}, skärpning {p.tau_months:.0f} månader. Massan bevaras inte "
                     f"helt men avtar långsamt; radien växer som $\\rho^2 = \\rho_0^2 + 2Dt$, "
                     f"så spetsen faller brant först och flackt sedan, aldrig till noll.",
                y=-0.06)
    series = {"q_by_years_worked": pd.DataFrame({"year": t, **{
                  f"q_{yrs}y": trace(yrs, True)[0] for yrs in (40, 10, 3)}}),
              "mass_and_radius": pd.DataFrame({"year": t, "mass_40y": m40,
                                               "radius_10y": r10})}
    figio.write(fig, "competence_over_tenure", out, data=series, save=ps.save,
                note="Inlärning, mättnad och diffusion över fyrtio år.",
                extra={"lambda_half_life_years": float(np.log(2) / p.lam),
                       "D": p.D, "tau_months": p.tau_months,
                       "m_sat": float(p.a / p.lam)})


# ---------------------------------------------------------------------------
def fig_wages(run_dirs, out):
    """Lönen som avvikelse från yrkets norm, och arbetsgivarens andel av den.

    MOT YRKET, INTE MOT JOBBET. Figuren räknade tidigare sin egen kvot,
    w_neg / w_field, medan w_field är JOBBETS lön Pi_j = Pi_o * exp(eta_j).
    Med w = Pi_j * p**theta står eta i både täljare och nämnare och försvinner
    IDENTISKT: figuren visade p**theta och inte lönekvoten, med en spik vid
    exakt 1.00 i alla jobb där r_j ~ 0 och p per definition är ett. 0064
    rättade måttet i eventlog men figuren räknade vidare på egen hand.

    Nu läses wage_ratio ur transitions, som alla andra skript gör. Egna
    parsers och egna härledningar av samma storhet är hur de två kunde glida
    isär utan att något larmade.
    """
    from core.analysis.eventlog import pooled_transitions

    tr = pooled_transitions(run_dirs, cps_only=False)
    if tr.empty or "w_neg" not in tr.columns:
        print("wages: inga löner i tabellerna"); return
    kol = [c for c in ("w_neg", "w_occ", "w_field", "wage_ratio",
                       "employer_premium", "r_req", "to_onet") if c in tr.columns]
    df = tr[kol].dropna(subset=["w_neg"]).rename(columns={"to_onet": "onet"}).copy()
    if "wage_ratio" not in df.columns:
        print("wages: transitions saknar wage_ratio (kräver patch 0064)"); return
    df = df[df["wage_ratio"] > 0]
    if df.empty:
        print("wages: inga giltiga lönekvoter"); return

    har_eta = "employer_premium" in df.columns and df["employer_premium"].notna().any()
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.0), dpi=ps.DPI)

    # 1. Fördelningen mot en lognormal med samma my och sigma. Formen är en
    #    FÖRUTSÄGELSE: q är en summa av produkter, alltså approximativt
    #    lognormal, och p = q**(k*r) bevarar det. Den ska kunna slås ut.
    ax = ps.cartesian_axes(axes[0])
    r = df["wage_ratio"].to_numpy()
    lo, hi = np.quantile(r, [0.002, 0.998])
    bins = np.linspace(lo, hi, 46)
    ax.hist(r, bins=bins, color="#1f77b4", alpha=0.75, lw=0)
    lg = np.log(r); mu, sd = float(lg.mean()), float(lg.std())
    xs = 0.5 * (bins[:-1] + bins[1:])
    dens = np.exp(-(np.log(xs) - mu) ** 2 / (2 * sd * sd)) / (xs * sd * np.sqrt(2 * np.pi))
    ax.plot(xs, dens * r.size * (bins[1] - bins[0]), ls="--", lw=1.6, color="#d62728",
            label=f"lognormal, $\\sigma$={sd:.3f}")
    ax.axvline(1.0, ls=":", lw=1.0, color="#7f7f7f")
    ax.set_xlabel("Förhandlad lön / yrkets fältlön $\\Pi_o$", fontsize=9)
    ax.set_ylabel("Antal", fontsize=9)
    ax.legend(fontsize=7.5, framealpha=0.9)
    ps.title(ax, f"Avvikelse från yrkets norm (median {np.median(r):.2f})", pad=10)

    # 2. Spridningen mot kravnivån, och VARFÖR den kröker.
    #
    #    Den enkla formen sigma**2 = sigma_eta**2 + (theta*k*sigma_q)**2 * r**2
    #    antar att sigma_q är konstant över r. Det är den inte: urvalet (0055)
    #    rangordnar på q och grinden q >= phi**(1/(2r)) sållar hårdare ju
    #    högre kravet är, så de anställda är homogena i q där kraven är höga
    #    och heterogena där de är låga. Uppmätt faller sd(log q) med en faktor
    #    3.6 över kvartilerna, 0.93 till 0.26, och motverkar därmed exponenten.
    #    Lönespridningen växer alltså långsammare med kravnivån än formeln
    #    säger, och residualerna behåller sitt mönster oavsett x-värde.
    #
    #    x-värdet är kvartilens MEDELVÄRDE av r**2, inte kvadraten på dess
    #    mittpunkt: sigma**2 är linjär i r**2, så det som ska plottas är
    #    E[r**2]; E[r]**2 skiljer sig med variansen inom kvartilen (Jensen)
    #    och avviker med upp till 57 procent i den understa. Korrigeringen är
    #    riktig men liten, sigma_eta 0.126 -> 0.124, vilket är själva beskedet:
    #    krökningen är ingen mätartefakt.
    #
    #    Den raka linjen står kvar som REFERENS, inte som skattning. Mot SCB
    #    ska den reducerade förutsägelsen prövas -- att spridningen växer
    #    monotont med r_j -- eftersom sigma_q(r) är mätbar i modellen men inte
    #    i lönestrukturstatistiken.
    ax = ps.cartesian_axes(axes[1])
    rows = []
    if "r_req" in df.columns and df["r_req"].notna().any():
        qq = pd.qcut(df["r_req"], 4, duplicates="drop")
        g = df.groupby(qq, observed=True)
        mids = [float((iv.left + iv.right) / 2) for iv in g.groups]
        sds = [float(np.std(np.log(v))) for v in g["wage_ratio"].apply(lambda s: s.to_numpy())]
        x2 = np.array([float((v ** 2).mean()) for v in
                       g["r_req"].apply(lambda s: s.to_numpy())])
        y2 = np.array(sds) ** 2
        ax.plot(x2, y2, "o-", lw=1.8, color="#1f77b4", label="var(log $w/\\Pi_o$)")
        if len(mids) >= 2:
            b, a = np.polyfit(x2, y2, 1)
            xr = np.array([0.0, float(x2.max()) * 1.05])
            ax.plot(xr, a + b * xr, ls="--", lw=1.2, color="#d62728",
                    label=(f"rät referens: $\\sigma_\\eta$={np.sqrt(max(a, 0)):.3f}"))
            ax.plot([0.0], [max(a, 0)], marker="D", ms=5, color="#d62728")
        ax.set_xlim(left=0.0)
        ax.set_ylabel("var(log $w/\\Pi_o$)", fontsize=9, color="#1f77b4")
        ax.tick_params(axis="y", labelcolor="#1f77b4")

        sq = []
        if "q_hire" in tr.columns:
            qh = tr.loc[tr["q_hire"] > 0, ["q_hire", "r_req"]].dropna()
            if not qh.empty:
                gq = qh.groupby(pd.qcut(qh["r_req"], 4, duplicates="drop"),
                                observed=True)["q_hire"]
                sq = [float(np.std(np.log(v))) for v in gq.apply(lambda s: s.to_numpy())]
        if len(sq) == len(x2):
            axq = ax.twinx()
            axq.plot(x2, sq, "s:", lw=1.6, color="#2ca02c", label="sd(log $q$)")
            axq.set_ylabel("sd(log $q$) vid anställning", fontsize=9, color="#2ca02c")
            axq.tick_params(axis="y", labelcolor="#2ca02c")
            axq.set_ylim(bottom=0.0)
            h1, l1 = ax.get_legend_handles_labels()
            h2, l2 = axq.get_legend_handles_labels()
            ax.legend(h1 + h2, l1 + l2, fontsize=7, loc="upper left", framealpha=0.9)
        else:
            ax.legend(fontsize=7.5, framealpha=0.9)
        rows = [{"r_req_mid": m, "mean_r_sq": float(x), "sd_log_wage_ratio": sv,
                 "var_log_wage_ratio": sv ** 2,
                 "sd_log_q": (sq[i] if i < len(sq) else np.nan)}
                for i, (m, x, sv) in enumerate(zip(mids, x2, sds))]
    ax.set_xlabel("$E[r_j^2]$ inom kvartilen", fontsize=9)
    ps.title(ax, "Spridning mot kravnivå", pad=10)

    # 3. Arbetsgivarkomponenten, exp(eta), som föll bort ur den gamla kvoten.
    ax = ps.cartesian_axes(axes[2])
    if har_eta:
        ep = df["employer_premium"].dropna().to_numpy()
        ep = ep[ep > 0]
        ax.hist(ep, bins=40, color="#2ca02c", alpha=0.75, lw=0)
        ax.axvline(1.0, ls=":", lw=1.0, color="#7f7f7f")
        andel = float(np.var(np.log(ep)) / max(np.var(np.log(df["w_neg"].to_numpy())), 1e-12))
        ax.set_xlabel("$\\Pi_j / \\Pi_o = e^{\\eta_j}$", fontsize=9)
        ax.set_ylabel("Antal", fontsize=9)
        ps.title(ax, f"Arbetsgivareffekt ({100*andel:.0f} % av variansen)", pad=10)
    else:
        ax.text(0.5, 0.5, "employer_premium saknas\n(kräver patch 0064)",
                ha="center", va="center", fontsize=9, color="#777777")
        ps.title(ax, "Arbetsgivareffekt", pad=10)

    ps.footnote(fig, "Lönen är en avvikelse från yrkets norm, "
                     "$w = \\Pi_j\\,p^{\\theta}$ med $\\Pi_j = \\Pi_o e^{\\eta_j}$ och golvet "
                     "$\\varphi\\Pi$ som undre gräns. $\\theta$ är graden av individuell "
                     "lönesättning. Kvoten mäts mot YRKETS fältlön: mot jobbets "
                     "försvinner arbetsgivareffekten identiskt, eftersom den står i "
                     "både täljare och nämnare.", y=-0.10)

    agg = {"n": ("w_neg", "size"), "w_neg_median": ("w_neg", "median"),
           "w_neg_q10": ("w_neg", lambda x: x.quantile(0.10)),
           "w_neg_q25": ("w_neg", lambda x: x.quantile(0.25)),
           "w_neg_q75": ("w_neg", lambda x: x.quantile(0.75)),
           "w_neg_q90": ("w_neg", lambda x: x.quantile(0.90)),
           "ratio_median": ("wage_ratio", "median"),
           "sd_log_ratio": ("wage_ratio", lambda x: float(np.std(np.log(x[x > 0]))))}
    if "w_occ" in df.columns:
        agg["w_occ"] = ("w_occ", "median")
    if "w_field" in df.columns:
        agg["w_field"] = ("w_field", "median")
    per_occ = (df.groupby("onet").agg(**agg).reset_index()
                 .sort_values("n", ascending=False))
    data = {"per_occupation": per_occ,
            "ratio": df[[c for c in ("w_occ", "w_field", "w_neg", "wage_ratio",
                                     "employer_premium", "r_req") if c in df.columns]]}
    if rows:
        data["sd_by_r_req"] = pd.DataFrame(rows)
    figio.write(fig, "wage_dispersion", out, data=data, run_dirs=run_dirs,
                save=ps.save,
                note="Lön mot yrkets fältlön; spridning mot kravnivå; "
                     "arbetsgivareffekt.")


# ---------------------------------------------------------------------------
def fig_commute(run_dirs, out):
    """Pendlingsavstånd, och inversionen mot uppgiftsavstånd.

    Pendlingskostnaden c*km är ABSOLUT och inte proportionell mot lönen, så
    samma avstånd är en mindre andel av en hög lön. Modellen bör därför ge
    långa pendlingar koncentrerade till kravtunga, välbetalda yrken med tunn
    lokal marknad. Höger panel prövar det, och visar samtidigt inversionen:
    de minst kravtunga jobben pendlar KORTAST geografiskt och färdas LÄNGST i
    uppgiftsrummet, eftersom p = q**(k*r) är platt vid r ~ 0 och överskottet
    då inte bär någon information om uppgiftsavstånd alls.
    """
    from core.analysis.eventlog import load_tables

    per_run, frames = {}, []
    for rd in run_dirs:
        try:
            tr = load_tables(rd)["transitions"]
        except Exception:
            continue
        if tr.empty or "commute_km" not in tr.columns:
            continue
        km = tr["commute_km"].dropna()
        if not len(km):
            continue
        per_run[os.path.basename(str(rd).rstrip("/"))] = km.to_numpy()
        frames.append(tr)

    if not per_run:
        print("commute: ingen commute_km i tabellerna (kräver patch 0052)"); return
    allv = np.concatenate(list(per_run.values()))
    tr = pd.concat(frames, ignore_index=True)
    n_runs = len(per_run)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), dpi=ps.DPI)

    ax = ps.cartesian_axes(axes[0])
    hi = float(np.quantile(allv, 0.995))
    bins = np.linspace(0, max(hi, 1.0), 45)
    for v in per_run.values():
        ax.hist(v, bins=bins, histtype="step", lw=0.8, color="#1f77b4", alpha=0.45)
    ax.hist(allv, bins=bins, color="#1f77b4", alpha=0.35, lw=0,
            label=f"alla frön (n={allv.size})")
    med = float(np.median(allv))
    ax.axvline(med, ls="--", lw=1.4, color="#1f77b4")
    ax.text(med, ax.get_ylim()[1]*0.92, f" median {med:.1f} km", fontsize=7.5,
            color="#1f77b4")
    ax.set_xlabel("Pendlingsavstånd vid anställning (km)", fontsize=9)
    ax.set_ylabel("Antal", fontsize=9)
    ax.legend(fontsize=7.5, framealpha=0.9)
    ps.title(ax, f"Pendlingsavstånd ({n_runs} körning{'ar' if n_runs > 1 else ''})",
             pad=10)

    ax2 = ps.cartesian_axes(axes[1])
    rows = []
    if tr["r_req"].notna().any():
        q = pd.qcut(tr["r_req"], 4, duplicates="drop")
        g = tr.groupby(q, observed=True)
        mids = [float((iv.left + iv.right) / 2) for iv in g.groups]
        kmm = g["commute_km"].median().to_numpy()
        # u_R_occ, inte u_R, och på CPS-urvalet. u_R mäts från INDIVIDENS
        # position till jobbet; u_R_occ från KÄLLYRKETS centroid till jobbets,
        # normerat med källans radie. CPS observerar yrkesbyten, alltså
        # avstånd mellan två yrken, och det är u_R_occ som ska jämföras med
        # 0.70. Skillnaden är inte kosmetisk: med u_R låg bottenkvartilen på
        # 1.64 medan den med u_R_occ ligger på 0.79, alltså med de andra --
        # individen kan ligga långt från jobbet även när yrkena ligger nära.
        cps = tr[tr["in_cps_sample"].fillna(False).astype(bool)]
        uq = pd.qcut(cps["r_req"], 4, duplicates="drop")
        urm = cps.groupby(uq, observed=True)["u_R_occ"].median().to_numpy()
        ax2.plot(mids, kmm, "o-", lw=1.8, color="#1f77b4", label="pendling (km)")
        ax2.set_ylabel("Median pendling (km)", fontsize=9, color="#1f77b4")
        ax2.tick_params(axis="y", labelcolor="#1f77b4")
        ax3 = ax2.twinx()
        n = min(len(mids), len(urm))
        ax3.plot(mids[:n], urm[:n], "s--", lw=1.8, color="#d62728",
                 label="$u_R$ mellan yrken (task-radier)")
        ax3.axhline(REF_WITHIN, ls=":", lw=1.2, color="#2ca02c")
        ax3.text(mids[0], REF_WITHIN, " 0,70", fontsize=7, color="#2ca02c",
                 va="bottom")
        ax3.set_ylabel("Median $u_R$ mellan yrken", fontsize=9, color="#d62728")
        ax3.tick_params(axis="y", labelcolor="#d62728")
        napp = (tr.groupby(q, observed=True)["n_applicants"].mean().to_numpy()
                if "n_applicants" in tr.columns and tr["n_applicants"].notna().any()
                else np.full(len(mids), np.nan))
        rows = [{"r_req_mid": m, "median_commute_km": float(k),
                 "mean_applicants": float(napp[i]) if i < len(napp) else np.nan,
                 "median_u_R_occ": float(u) if i < len(urm) else np.nan}
                for i, (m, k, u) in enumerate(zip(mids, kmm,
                                                  list(urm) + [np.nan]*len(mids)))]
        h1, l1 = ax2.get_legend_handles_labels()
        h2, l2 = ax3.get_legend_handles_labels()
        ax2.legend(h1 + h2, l1 + l2, fontsize=7.5, loc="center right",
                   framealpha=0.9)
    ax2.set_xlabel("Kravintensitet $r_j$ (kvartilmitt)", fontsize=9)
    ps.title(ax2, "Geografiskt mot uppgiftsavstånd", pad=10)

    ps.footnote(fig, "Pendlingskostnaden är absolut, inte proportionell mot "
                     "lönen, så långa pendlingar ska vara koncentrerade till "
                     "välbetalda yrken. Vid $r_j \\approx 0$ är $p = q^{k r}$ platt: "
                     "överskottet bär då ingen information om uppgiftsavstånd, "
                     "och de jobben pendlar kortast geografiskt men längst i "
                     "uppgiftsrummet.", y=-0.05)

    per = pd.DataFrame({"run": list(per_run), "n": [v.size for v in per_run.values()],
                        "median_km": [float(np.median(v)) for v in per_run.values()],
                        "p90_km": [float(np.quantile(v, 0.9)) for v in per_run.values()]})
    figio.write(fig, "commute_distribution", out,
                data={"per_run": per, "by_r_req": pd.DataFrame(rows)},
                run_dirs=run_dirs, save=ps.save,
                note="Pendlingsavstånd vid anställning; per kvartil i r_req "
                     "mot uppgiftsavstånd.")


# ---------------------------------------------------------------------------
def latest_run():
    outdir = os.path.join(ROOT, "output")
    c = [os.path.join(outdir, d) for d in os.listdir(outdir)
         if os.path.isfile(os.path.join(outdir, d, "eventlog.csv"))]
    if not c:
        raise SystemExit("Ingen körning med eventlog.csv under output/.")
    return max(c, key=os.path.getmtime)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="*", help="körningskataloger (default: senaste)")
    ap.add_argument("--out", default=os.path.join(ROOT, "figures"))
    ap.add_argument("--only", choices=["mobility", "competence", "coverage",
                                       "tenure", "wages", "commute"])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    runs = a.runs or [latest_run()]
    if not a.runs:
        print(f"(använder senaste: {os.path.basename(runs[0])})\n")

    if a.only in (None, "mobility"):
        fig_mobility(runs, a.out)
    if a.only in (None, "competence"):
        fig_competence(a.out)
    if a.only in (None, "coverage"):
        fig_coverage(runs, a.out)
    if a.only in (None, "tenure"):
        fig_tenure(a.out)
    if a.only in (None, "wages"):
        fig_wages(runs, a.out)
    if a.only in (None, "commute"):
        fig_commute(runs, a.out)


if __name__ == "__main__":
    main()
