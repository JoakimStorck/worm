# worm/statistics/matching_stats.py

import os
import json
import pandas as pd
from datetime import datetime

from worm.statistics.log import log


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
        log("--- Matchningsstatistik ---")
        for k, v in stats.items():
            log(f"{k}: {v}")
    return stats


def compute_commuting_statistics(matchings_df, individuals_df, jobs_df, deso_col="deso_code", muni_col="municipal_code", print_stats=True):
    """
    Beräknar pendlingsflöden på DeSO- och kommunnivå:
    - Hur många individer får jobb i annan DeSO än sin hem-DeSO?
    - Hur många jobb fylls av utpendlare? (per DeSO/kommun)
    Kräver:
        matchings_df: ['individual_id', 'job_id']
        individuals_df: ['individual_id', deso_col, muni_col]
        jobs_df: ['job_id', deso_col, muni_col]
    Returnerar dict med pendlingsandelar etc.
    """
    if matchings_df.empty:
        return {"n_matched": 0}

    # Slå upp DeSO och kommun för individer och jobb
    ind = individuals_df.set_index("individual_id")[[deso_col, muni_col]].rename(
        columns={deso_col: "ind_deso", muni_col: "ind_muni"}
    )
    job = jobs_df.set_index("job_id")[[deso_col, muni_col]].rename(
        columns={deso_col: "job_deso", muni_col: "job_muni"}
    )
    df = matchings_df.join(ind, on="individual_id").join(job, on="job_id")

    # Utpendling på DeSO-nivå
    df["is_cross_deso"] = df["ind_deso"] != df["job_deso"]
    df["is_cross_muni"] = df["ind_muni"] != df["job_muni"]

    n_matched = len(df)
    n_cross_deso = df["is_cross_deso"].sum()
    n_cross_muni = df["is_cross_muni"].sum()
    share_cross_deso = n_cross_deso / n_matched if n_matched > 0 else 0
    share_cross_muni = n_cross_muni / n_matched if n_matched > 0 else 0

    # Andel jobb i varje DeSO/kommun som fylls av utpendlare
    job_group = df.groupby("job_deso")["is_cross_deso"].mean()
    muni_group = df.groupby("job_muni")["is_cross_muni"].mean()

    stats = {
        "n_matched": n_matched,
        "n_cross_deso": n_cross_deso,
        "share_cross_deso": share_cross_deso,
        "n_cross_muni": n_cross_muni,
        "share_cross_muni": share_cross_muni,
        "mean_job_share_cross_deso": job_group.mean(),
        "mean_job_share_cross_muni": muni_group.mean(),
    }
    if print_stats:
        log("--- Pendlingsstatistik ---")
        log(f"Totalt matchade: {n_matched}")
        log(f"Antal/andel som fått jobb i annan DeSO: {n_cross_deso} ({share_cross_deso:.2%})")
        log(f"Antal/andel som fått jobb i annan kommun: {n_cross_muni} ({share_cross_muni:.2%})")
        log(f"Genomsnittlig andel jobb (per DeSO) som fylls av utpendlare: {job_group.mean():.2%}")
        log(f"Genomsnittlig andel jobb (per kommun) som fylls av utpendlare: {muni_group.mean():.2%}")
    return stats

