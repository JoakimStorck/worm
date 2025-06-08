# worm/statistics/matching_stats.py

import pandas as pd

def compute_matching_statistics(matchings_df, print_stats=True):
    """
    Tar emot DataFrame med kolumner ['individual_id', 'job_id', 'utility'].
    Returnerar en dict med nyckeltal för utility-fördelningen.
    """
    if matchings_df.empty:
        return {"n_matched": 0}

    util = matchings_df['utility']
    stats = {
        "n_matched": len(util),
        "utility_mean": util.mean(),
        "utility_median": util.median(),
        "utility_std": util.std(),
        "utility_min": util.min(),
        "utility_max": util.max(),
        "utility_q25": util.quantile(0.25),
        "utility_q75": util.quantile(0.75),
        "utility_99th": util.quantile(0.99),
        "n_utility_above_0.05": (util > 0.05).sum(),
        "n_utility_below_0.01": (util < 0.01).sum(),
    }
    if print_stats:
        print("--- Matchningsstatistik ---")
        for k, v in stats.items():
            print(f"{k}: {v}")
    return stats
