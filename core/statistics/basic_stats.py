#core/statistics/basic_stats.py

import os
import yaml
import numpy as np

from core.world import World

def analyze_world(world):
    """
    Returns extended statistics about the current world.
    """
    n_unique_individuals = len(world.matchings['individual_id'].unique()) if not world.matchings.empty else 0
    n_unique_jobs = len(world.matchings['job_id'].unique()) if not world.matchings.empty else 0

    stats = {
        "total_individuals": len(world.individuals),
        "individual_status_counts": world.individuals['status'].value_counts().to_dict(),
        "total_jobs": len(world.jobs),
        "total_employers": len(world.employers),
        "matched_pairs": len(world.matchings),
        "unique_matched_individuals": n_unique_individuals,
        "unique_matched_jobs": n_unique_jobs,
        "unmatched_individuals_in_workforce": len(world.individuals[(world.individuals['status'] == 'unemployed') & (~world.individuals['individual_id'].isin(world.matchings['individual_id']) if not world.matchings.empty else True)]),
        "unmatched_jobs": world.jobs['individual_id'].isna().sum()
    }
    return stats

def save_summary_stats(result, output_path):
    df_ind = result.get_individuals()
    df_job = result.get_jobs()
    df_emp = result.get_employers()

    # Grundläggande summering
    stats = {
        "individuals": len(df_ind),
        "jobs": len(df_job),
        "employers": len(df_emp) if df_emp is not None else 0,
        # Fler nyckeltal här ...
    }

    # # Exempel: åldersstatistik (om det finns)
    # if "age" in df_ind.columns:
    #     stats["age"] = {
    #         "mean": float(np.mean(df_ind["age"])),
    #         "std": float(np.std(df_ind["age"])),
    #         "min": int(np.min(df_ind["age"])),
    #         "max": int(np.max(df_ind["age"])),
    #     }

    # # Exempel: matchning/utility (lägg till din egen logik)
    # if "matched_job_id" in df_ind.columns:
    #     match_rate = np.mean(df_ind["matched_job_id"].notna())
    #     stats["matching"] = {
    #         "matched": int(df_ind["matched_job_id"].notna().sum()),
    #         "unmatched": int(df_ind["matched_job_id"].isna().sum()),
    #         "match_rate": float(match_rate),
    #     }

    # # Exempel: utility – här placeholder, byt mot din faktiska utility
    # if "utility" in df_ind.columns:
    #     stats["utility"] = {
    #         "mean": float(np.mean(df_ind["utility"])),
    #         "std": float(np.std(df_ind["utility"])),
    #         "min": float(np.min(df_ind["utility"])),
    #         "max": float(np.max(df_ind["utility"])),
    #     }

    # Eventuella andra mått – fyll på här

    # Spara till YAML
    with open(os.path.join(output_path, "summary_stats.yaml"), "w") as f:
        yaml.dump(stats, f, sort_keys=False, allow_unicode=True, default_flow_style=False)

