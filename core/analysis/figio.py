"""
core/analysis/figio.py
----------------------
Varje figur skriver den serie den ritar, och varifrån den kommer.

En PDF säger inte vilka körningar den bygger på, vilken kodversion eller
vilka frön. Utan det går en figur i ett manuskript inte att spåra, och en
medförfattare kan inte rita om den utan att köra hela simuleringen. Därför
skriver varje figur tre filer:

    <namn>.pdf            figuren
    <namn>.csv            den data som ritats, en rad per punkt
    <namn>.json           manifest: körningar, commits, frön, parametrar

Manifestet bär samma härkomst som körningarna själva (run_meta.json), ett
steg upp: en figur över fem frön ska kunna visa vilka fem.
"""
from __future__ import annotations

import datetime
import json
import os

import pandas as pd


def provenance(run_dirs):
    """Härkomst för de körningar en figur bygger på."""
    runs = []
    for rd in run_dirs or []:
        mp = os.path.join(rd, "run_meta.json")
        meta = {}
        if os.path.isfile(mp):
            try:
                with open(mp, encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                meta = {}
        runs.append({
            "run": os.path.basename(str(rd).rstrip("/")),
            "scenario": meta.get("scenario"),
            "seed": meta.get("seed"),
            "commit": meta.get("git_commit"),
            "dirty": meta.get("git_dirty"),
            "municipalities": meta.get("municipalities"),
        })
    commits = sorted({r["commit"] for r in runs if r.get("commit")})
    return {
        "runs": runs,
        "n_runs": len(runs),
        "commits": commits,
        "mixed_commits": len(commits) > 1,
        "seeds": sorted({r["seed"] for r in runs if r.get("seed") is not None}),
    }


def write(fig, name, out_dir, data=None, run_dirs=None, note=None, extra=None,
          save=None):
    """Sparar figur, data och manifest under samma namn.

    data : DataFrame eller dict av DataFrames. Flera ramar skrivs som
           <namn>__<nyckel>.csv, så att en figur med flera paneler kan bära
           varje panels serie.
    """
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, name)

    written = []
    if data is not None:
        frames = data if isinstance(data, dict) else {"": data}
        for key, df in frames.items():
            if df is None or (hasattr(df, "empty") and df.empty):
                continue
            path = f"{base}__{key}.csv" if key else f"{base}.csv"
            pd.DataFrame(df).to_csv(path, index=False)
            written.append(os.path.basename(path))

    manifest = {
        "figure": name,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "data_files": written,
        "note": note,
    }
    manifest.update(provenance(run_dirs))
    if extra:
        manifest["parameters"] = extra
    with open(f"{base}.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    if save is not None:
        save(fig, f"{base}.pdf")
    if manifest.get("mixed_commits"):
        print(f"   VARNING: {name} bygger på {len(manifest['commits'])} kodversioner.")
    return manifest
