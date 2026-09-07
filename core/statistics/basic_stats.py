#core/statistics/basic_stats.py

import os
import yaml
import numpy as np
import pandas as pd


def analyze_world(world):
    """
    Returns extended statistics about the current world.
    """

    stats = {
        "total_individuals": len(world.individuals),
        "total_jobs": int(world.jobs['active'].sum()) if 'active' in world.jobs.columns else len(world.jobs),
        "total_employers": len(world.employers),
        "employed_individuals": len(world.individuals[(world.individuals['status'] == 'employed')]),
        "unemployed_individuals": len(world.individuals[(world.individuals['status'] == 'unemployed')]),
        "unmatched_jobs": int((world.jobs['individual_id'].isna() & world.jobs['active']).sum())
                          if 'active' in world.jobs.columns
                          else int(world.jobs['individual_id'].isna().sum()),
        "individuals_not_in_labour_force": len(world.individuals[(world.individuals['status'] == 'not_in_labor_force')]),   
    }
    return stats

def hist_as_dict(data, bins=20, range=None):
    hist, bin_edges = np.histogram(data, bins=bins, range=range)
    return {
        "counts": hist.tolist(),
        "bin_edges": bin_edges.tolist()
    }

def save_basic_stats(result, outdir, tag="basic_stats"):
    """Ögonblicksbild av tillståndet till JSON.

    Histogrammen över chi, xi och r_i beskrev den gamla individmodellen, där
    de var tillståndsvariabler. Med kompetenscirklarna är de HÄRLEDDA mått
    (core/occupations/competence.Circles.summarize), och att spara deras
    fördelningar utan cirklarna bakom är missvisande. De ersätts av
    fördelningar som faktiskt bär information om tillståndet: konkurrenskraft,
    kompetensmassa och löner.

    Analysklara tabeller skrivs i stället av scripts/export_tables.py.
    """
    import json

    ind = result.individuals
    jobs = result.jobs
    employers = result.employers
    print(f'tag={tag}')

    def dist(series, bins=20):
        x = pd.to_numeric(series, errors="coerce").dropna() if series is not None else None
        if x is None or x.empty:
            return None
        return {"mean": float(x.mean()), "std": float(x.std()),
                "min": float(x.min()), "max": float(x.max()),
                "median": float(x.median()),
                "hist": hist_as_dict(x, bins=bins)}

    act = jobs["active"].astype(bool) if "active" in jobs.columns else None
    stats = {
        "tag": tag,
        "n_individuals": len(ind),
        "n_jobs": int(act.sum()) if act is not None else len(jobs),
        "n_employers": len(employers),
        "individual_status_counts": ind['status'].value_counts().to_dict()
        if 'status' in ind.columns else {},
        "job_vacancy_counts": {
            "vacant": int((jobs['individual_id'].isna() & (act if act is not None else True)).sum()),
            "filled": int((jobs['individual_id'].notna() & (act if act is not None else True)).sum()),
        },
        "individuals": {k: dist(ind[k]) for k in
                        ("chi", "xi", "r_i", "R", "w_res", "w_neg", "tenure_years")
                        if k in ind.columns},
        "jobs": {k: dist(jobs[k]) for k in ("wage", "r_o") if k in jobs.columns},
    }
    with open(f"{outdir}/basic_stats_{tag}.json", "w") as f:
        json.dump(stats, f, indent=2)

