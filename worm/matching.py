import pandas as pd
import numpy as np
from worm.occupations.utils import optimal_assignment
from worm.occupations.utils import compute_utility_matrix
import time

def batched_communewise_assignment(individuals_df, jobs_df, alpha=1.0, batch_size=1000, verbose=True):
    inds = individuals_df.copy()
    jobs = jobs_df.copy()
    all_matches = []
    batch_nr = 1
    while len(inds) > 0 and len(jobs) > 0:
        t0 = time.time()
        inds_batch = inds.iloc[:batch_size]
        jobs_batch = jobs.iloc[:batch_size]
        matches = optimal_assignment(inds_batch, jobs_batch, alpha=alpha)
        batch_time = time.time() - t0
        if matches.empty:
            break
        all_matches.append(matches)
        inds = inds[~inds['individual_id'].isin(matches['individual_id'])]
        jobs = jobs[~jobs['job_id'].isin(matches['job_id'])]
        if verbose:
            print(f"    - Kommunbatch {batch_nr}: {len(matches)} matchade, kvar: {len(inds)} individer, {len(jobs)} jobb. Tid: {batch_time:.2f} s")
        batch_nr += 1

    if all_matches:
        return pd.concat(all_matches, ignore_index=True)
    else:
        return pd.DataFrame(columns=["individual_id", "job_id", "utility"])


def greedy_deso_matching(individuals, jobs, alpha=1.0, batch_size=1000, verbose=True):
    inds = individuals.copy()
    jobs_df = jobs.copy()
    inds["deso_code"] = inds["deso_code"].astype(str)
    jobs_df["deso_code"] = jobs_df["deso_code"].astype(str)
    all_matchings = []
    total_matched_inds = 0

    deso_codes = inds["deso_code"].dropna().unique()
    if verbose:
        print(f"\nMatcherar först {len(deso_codes)} DeSO...")

    # DeSO-nivå
    for ix, deso in enumerate(deso_codes, 1):
        t0 = time.time()
        i_mask = inds["deso_code"] == deso
        j_mask = jobs_df["deso_code"] == deso
        inds_batch = inds[i_mask]
        jobs_batch = jobs_df[j_mask]
        n_inds = len(inds_batch)
        n_jobs = len(jobs_batch)
        if verbose:
            print(f"[{ix}/{len(deso_codes)}] DeSO {deso}: {n_inds} individer, {n_jobs} jobb kvar.")
        if n_inds == 0 or n_jobs == 0:
            continue
        t_batch_start = time.time()
        m = optimal_assignment(inds_batch, jobs_batch, alpha)
        t_batch = time.time() - t_batch_start
        if len(m) == 0:
            continue
        all_matchings.append(m)
        total_matched_inds += len(m)
        inds = inds[~inds["individual_id"].isin(m["individual_id"])]
        jobs_df = jobs_df[~jobs_df["job_id"].isin(m["job_id"])]
        if verbose:
            print(f"  - Matchade {len(m)} i denna DeSO (totalt {total_matched_inds}). Tid: {t_batch:.2f} s")
        if verbose:
            print(f"  - Återstående: {len(inds)} individer, {len(jobs_df)} jobb")

    # Kommunnivå i batcher
    if len(inds) > 0 and len(jobs_df) > 0:
        if verbose:
            print(f"\nMatchar kvarvarande på kommunnivå (block om {batch_size}) ({len(inds)} individer, {len(jobs_df)} jobb)...")
        muni_codes = inds["municipal_code"].dropna().unique()
        for j, muni in enumerate(muni_codes, 1):
            i_mask = inds["municipal_code"] == muni
            j_mask = jobs_df["municipal_code"] == muni
            inds_batch = inds[i_mask]
            jobs_batch = jobs_df[j_mask]
            if len(inds_batch) == 0 or len(jobs_batch) == 0:
                continue
            t_batch_start = time.time()
            m = batched_communewise_assignment(inds_batch, jobs_batch, alpha=alpha, batch_size=batch_size, verbose=verbose)
            t_batch = time.time() - t_batch_start
            if len(m) > 0:
                all_matchings.append(m)
                total_matched_inds += len(m)
                inds = inds[~inds["individual_id"].isin(m["individual_id"])]
                jobs_df = jobs_df[~jobs_df["job_id"].isin(m["job_id"])]
                if verbose:
                    print(f"    - Kommun {muni}: matchade {len(m)} (totalt {total_matched_inds}), tid: {t_batch:.2f} s")
                if verbose:
                    print(f"    - Återstående: {len(inds)} individer, {len(jobs_df)} jobb")

    # Sista batch: globalt
    if len(inds) > 0 and len(jobs_df) > 0:
        if verbose:
            print(f"\nGlobal sista matchningsbatch (ingen geografi): {len(inds)} individer, {len(jobs_df)} jobb.")
        t_batch_start = time.time()
        m = batched_communewise_assignment(inds, jobs_df, alpha=alpha, batch_size=batch_size, verbose=verbose)
        t_batch = time.time() - t_batch_start
        if len(m) > 0:
            all_matchings.append(m)
            total_matched_inds += len(m)
            if verbose:
                print(f"  - Globalt matchade {len(m)}. Tid: {t_batch:.2f} s")
        else:
            if verbose:
                print("  - Ingen möjlig global matchning kvar.")

    if verbose:
        print(f"\nSlutlig summering: matchade totalt {total_matched_inds} individer.\n")

    if all_matchings:
        result = pd.concat(all_matchings, ignore_index=True)
    else:
        result = pd.DataFrame(columns=["individual_id", "job_id", "utility"])
    return result
