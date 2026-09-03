"""
beveridge.py  (placera i scripts/)
----------------------------------
Extraherar Beveridgekurvan ur WORM:s eventloggar och plottar den.

Två lägen:

  BANA (en körning)      Varje new_month-rad ger en punkt (u, v). Under
      konvergensen rör sig systemet från hög arbetslöshet + höga vakanser mot
      sin jämvikt, vilket ritar en bana genom (u, v)-rummet.

  LOKUS (flera körningar) Kör samma scenario med olika friktionsparametrar
      (sigma_gamma, alpha_geo) eller olika efterfrågan. Varje körnings JÄMVIKT
      blir en punkt; tillsammans bildar de kurvan. Det är den egentliga
      Beveridgekurvan -- ett samband, inte en tidsserie.

    python scripts/beveridge.py                       # senaste körningen
    python scripts/beveridge.py output/run_A output/run_B ...

u = arbetslösa / (sysselsatta + arbetslösa)
v = lediga jobb / totalt antal jobb
"""
import os
import sys

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


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


def _parse_line(line):
    """
    Eventloggen är trots filändelsen INTE en CSV. EventLogger._write_log skriver
    rader på formen:

        0.00, new_month, agent_type system, agent_id None, ..., employed 6530, ...

    dvs. kommaseparerade fält där det första är tid, det andra eventtypen och
    resten är "nyckel värde"-par (värdet kan innehålla mellanslag).
    """
    parts = [p.strip() for p in line.rstrip("\n").split(",")]
    if len(parts) < 2:
        return None
    rec = {}
    try:
        rec["time"] = float(parts[0])
    except ValueError:
        return None
    rec["event"] = parts[1]
    for f in parts[2:]:
        if not f:
            continue
        k, _, v = f.partition(" ")
        rec[k] = v.strip()
    return rec


def series_from_run(run_dir):
    """Månadsserie (u, v) ur en körnings eventlog."""
    path = os.path.join(run_dir, "eventlog.csv")
    if not os.path.isfile(path):
        print(f"  saknar eventlog.csv: {run_dir}")
        return None

    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if "new_month" not in line and "new_year" not in line:
                continue                      # snabbfilter före parsning
            rec = _parse_line(line)
            if rec is None or rec.get("event") != "new_month":
                continue
            try:
                emp = float(rec["employed"])
                unemp = float(rec["unemployed"])
                vac = float(rec["unmatched_jobs"])
            except (KeyError, ValueError):
                continue
            total_jobs = emp + vac
            if (emp + unemp) <= 0 or total_jobs <= 0:
                continue
            rows.append({"time": rec["time"],
                         "u": unemp / (emp + unemp),
                         "v": vac / total_jobs})

    if not rows:
        print(f"  inga användbara new_month-rader i {os.path.basename(run_dir)}")
        return None
    return pd.DataFrame(rows).reset_index(drop=True)


def plot(runs, outfile):
    fig, ax = plt.subplots(figsize=(7, 6))
    cmap = plt.get_cmap("viridis")

    for k, run_dir in enumerate(runs):
        s = series_from_run(run_dir)
        if s is None or s.empty:
            print(f"  hoppar över (ingen användbar eventlog): {run_dir}")
            continue
        label = os.path.basename(run_dir.rstrip("/"))
        col = cmap(k / max(len(runs) - 1, 1))
        # Bana
        ax.plot(100 * s["u"], 100 * s["v"], "-", color=col, alpha=0.55, lw=1.2)
        ax.scatter(100 * s["u"], 100 * s["v"], s=14, color=col, alpha=0.5)
        # Start och jämvikt
        ax.scatter([100 * s["u"].iloc[0]], [100 * s["v"].iloc[0]],
                   marker="o", s=70, facecolor="white", edgecolor=col, zorder=5)
        ax.scatter([100 * s["u"].iloc[-1]], [100 * s["v"].iloc[-1]],
                   marker="*", s=190, color=col, zorder=6, label=label)
        print(f"  {label}: start u={100*s['u'].iloc[0]:.1f}% v={100*s['v'].iloc[0]:.1f}%"
              f"  ->  slut u={100*s['u'].iloc[-1]:.1f}% v={100*s['v'].iloc[-1]:.1f}%")

    ax.set_xlabel("Arbetslöshet u (%)")
    ax.set_ylabel("Vakansgrad v (%)")
    ax.set_title("Beveridgekurva – WORM\n(cirkel = start, stjärna = jämvikt)", fontsize=11)
    ax.grid(alpha=0.25, linestyle=":")
    ax.legend(fontsize=8, loc="upper right")
    fig.tight_layout()
    fig.savefig(outfile, dpi=140)
    print(f"\nSparad: {outfile}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        runs = sys.argv[1:]
    else:
        outdir = os.path.join(ROOT, "output")
        cands = [os.path.join(outdir, d) for d in os.listdir(outdir)
                 if os.path.isfile(os.path.join(outdir, d, "eventlog.csv"))]
        if not cands:
            raise SystemExit("Ingen körning med eventlog.csv under output/.")
        runs = [max(cands, key=os.path.getmtime)]
        print(f"(ingen katalog angiven – använder senaste: {os.path.basename(runs[0])})\n")
    plot(runs, os.path.join(ROOT, "output", "beveridge.png"))
