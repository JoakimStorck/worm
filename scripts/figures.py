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
def fig_mobility(run_dir, out):
    df = read_transitions(run_dir)
    if df.empty:
        print("mobility: inga övergångar med u_R_occ i loggen"); return
    task = df[df["changed"] & ~df["mgmt"]]["u_R"].to_numpy()
    same = df[~df["changed"]]["u_R"].to_numpy()
    mgmt = df[df["changed"] & df["mgmt"]]["u_R"].to_numpy()

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), dpi=ps.DPI)
    ax = ps.cartesian_axes(axes[0])
    for arr, lab, col in ((task, "Yrkesbyten (exkl. chefsyrken)", "#1f77b4"),
                          (mgmt, "Till/från chefsyrke", "#ff7f0e")):
        if arr.size:
            x = np.sort(arr)
            ax.plot(x, np.arange(1, x.size + 1) / x.size, lw=1.8, color=col, label=lab)
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
    ax2.hist(task, bins=bins, color="#1f77b4", alpha=0.75, label="Yrkesbyten")
    if mgmt.size:
        ax2.hist(mgmt, bins=bins, color="#ff7f0e", alpha=0.6, label="Chefsyrken")
    ax2.axvline(np.median(task), ls="--", lw=1.4, color="#1f77b4")
    ax2.axvline(REF_WITHIN, ls=":", lw=1.2, color="#2ca02c")
    ax2.set_xlabel("Övergångslängd $u_R$ (task-radier)", fontsize=9)
    ax2.set_ylabel("Antal", fontsize=9)
    ax2.legend(fontsize=7.5, framealpha=0.9)
    ps.title(ax2, "Täthet", pad=10)

    n_same = same.size; n_tot = len(df)
    ps.footnote(fig, f"Median {np.median(task):.2f} task-radier mot 0,70 inom delsystem "
                     f"(papper 2). Återgång till eget yrke {100*n_same/max(n_tot,1):.0f} % "
                     f"och chefsövergångar {100*mgmt.size/max(n_tot,1):.0f} % utesluts; "
                     f"CPS räknar bara yrkesbyten, och tvärflödet är befordran.", y=-0.03)
    ps.save(fig, os.path.join(out, "mobility_distribution.pdf"))


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
    ps.save(fig, os.path.join(out, "competence_circles.pdf"))


# ---------------------------------------------------------------------------
def fig_coverage(run_dirs, out, s=0.25):
    """Kommunens jobb som täthet över skivan. Tunnhet gjord synlig."""
    tg, rg = np.meshgrid(np.linspace(0, 2 * math.pi, 241),
                         np.linspace(0, 1.0, 121))
    gx, gy = rg * np.cos(tg), rg * np.sin(tg)
    n = len(run_dirs)
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
    ps.footnote(fig, f"Täthet av lediga och tillsatta positioner i uppgiftsrummet. "
                     f"C({s}) är andelen av skivan inom {s} task-enheter från någon position: "
                     f"ett direkt mått på uppgiftsrummets tjocklek.", y=-0.06)
    ps.save(fig, os.path.join(out, "coverage.pdf"))


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
    ps.save(fig, os.path.join(out, "competence_over_tenure.pdf"))


# ---------------------------------------------------------------------------
def fig_wages(run_dir, out):
    """Lönespridning: fältet ger yrkets nivå, individen förhandlar sin avvikelse."""
    from core.analysis.eventlog import load_tables

    tr = load_tables(run_dir)["transitions"]
    df = pd.DataFrame()
    if not tr.empty and {"w_field", "w_neg"} <= set(tr.columns):
        df = tr[["w_field", "w_neg", "to_onet"]].dropna(
            subset=["w_field", "w_neg"]).rename(columns={"to_onet": "onet"})
    if df.empty:
        print("wages: inga w_field/w_neg i loggen (kräver körning efter förhandlingen)")
        return
    df = df.copy()
    df["ratio"] = df["w_neg"] / df["w_field"].replace(0, np.nan)

    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.0), dpi=ps.DPI)

    ax = ps.cartesian_axes(axes[0])
    ax.scatter(df["w_field"], df["w_neg"], s=5, alpha=0.25, color="#1f77b4",
               edgecolors="none")
    lim = [0, max(df["w_field"].max(), df["w_neg"].max()) * 1.05]
    ax.plot(lim, lim, ls="--", lw=1.0, color="#7f7f7f")
    ax.text(lim[1] * 0.62, lim[1] * 0.97, "full fältlön", fontsize=8, color="#555555")
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("Fältlön $\\Pi$ (löneandelar)", fontsize=9)
    ax.set_ylabel("Förhandlad lön $w$", fontsize=9)
    ps.title(ax, "Fältet ger nivån, individen förhandlar", pad=10)

    ax = ps.cartesian_axes(axes[1])
    ax.hist(df["ratio"].dropna(), bins=40, color="#1f77b4", alpha=0.8)
    ax.axvline(1.0, ls="--", lw=1.0, color="#7f7f7f")
    ax.axvline(float(df["ratio"].median()), ls="-", lw=1.4, color="#d62728")
    ax.set_xlabel("Förhandlad lön / fältlön", fontsize=9); ax.set_ylabel("Antal", fontsize=9)
    ps.title(ax, f"Andel av fältlönen (median {df['ratio'].median():.2f})", pad=10)

    # Spridning inom yrke: de tio vanligaste
    ax = ps.cartesian_axes(axes[2])
    top = df["onet"].value_counts().head(10).index.tolist()
    data = [df.loc[df["onet"] == o, "w_neg"].to_numpy() for o in top]
    if data and max(len(d) for d in data) > 3:
        bp = ax.boxplot(data, widths=0.6, patch_artist=True,
                        flierprops=dict(marker=".", markersize=2, alpha=0.4))
        for b in bp["boxes"]:
            b.set(facecolor="#1f77b4", alpha=0.55, linewidth=0.8)
        for o, i in zip(top, range(1, len(top) + 1)):
            pi = df.loc[df["onet"] == o, "w_field"].median()
            ax.plot([i], [pi], marker="D", ms=4, color="#d62728", zorder=4)
        ax.set_xticks(range(1, len(top) + 1))
        ax.set_xticklabels([o[:7] for o in top], rotation=60, fontsize=6.5)
        ax.set_ylabel("Förhandlad lön", fontsize=9)
        ax.legend(handles=[Line2D([], [], marker="D", ls="", ms=5, color="#d62728",
                                  label="fältlön $\\Pi$")], fontsize=7.5, framealpha=0.9)
    ps.title(ax, "Spridning inom yrke", pad=10)

    ps.footnote(fig, "Nash-förhandling: $w = w_{res} + \\beta(q\\Pi - w_{res} - \\kappa\\Pi)$. "
                     "Samma position betalar olika beroende på arbetarens konkurrenskraft och "
                     "hennes alternativ, vilket ger lönespridning inom yrke som fältet ensamt "
                     "inte kan ge.", y=-0.10)
    ps.save(fig, os.path.join(out, "wage_dispersion.pdf"))


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
                                       "tenure", "wages"])
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    runs = a.runs or [latest_run()]
    if not a.runs:
        print(f"(använder senaste: {os.path.basename(runs[0])})\n")

    if a.only in (None, "mobility"):
        fig_mobility(runs[0], a.out)
    if a.only in (None, "competence"):
        fig_competence(a.out)
    if a.only in (None, "coverage"):
        fig_coverage(runs, a.out)
    if a.only in (None, "tenure"):
        fig_tenure(a.out)
    if a.only in (None, "wages"):
        fig_wages(runs[0], a.out)


if __name__ == "__main__":
    main()
