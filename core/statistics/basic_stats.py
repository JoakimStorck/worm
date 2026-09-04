#core/statistics/basic_stats.py

import os
import yaml
import numpy as np

from core.scenario_result import ScenarioResult 


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
    ind = result.individuals
    jobs = result.jobs
    employers = result.employers

    print(f'tag={tag}')

    stats = {
        "tag": tag,
        "n_individuals": len(ind),
        "n_jobs": len(jobs),
        "n_employers": len(employers),
        "individual_status_counts": ind['status'].value_counts().to_dict(),
        "job_vacancy_counts": {
            "vacant": int(jobs['individual_id'].isna().sum()),
            "filled": int(jobs['individual_id'].notna().sum())
        },
        "OCS_individuals": {
            "chi": {
                "mean": float(ind['chi'].mean()),
                "std": float(ind['chi'].std()),
                "min": float(ind['chi'].min()),
                "max": float(ind['chi'].max()),
                "hist": hist_as_dict(ind['chi'], bins=20)
            },
            "xi": {
                "mean": float(ind['xi'].mean()),
                "std": float(ind['xi'].std()),
                "min": float(ind['xi'].min()),
                "max": float(ind['xi'].max()),
                "hist": hist_as_dict(ind['xi'], bins=20)
            },
            "r_i": {
                "mean": float(ind['r_i'].mean()),
                "std": float(ind['r_i'].std()),
                "min": float(ind['r_i'].min()),
                "max": float(ind['r_i'].max()),
                "hist": hist_as_dict(ind['r_i'], bins=20)
            }
        },
        # Skriv motsvarande för jobs och ev. annat.
    }

    # Spara till JSON och/eller CSV
    import json
    with open(f"{outdir}/basic_stats_{tag}.json", "w") as f:
        json.dump(stats, f, indent=2)
