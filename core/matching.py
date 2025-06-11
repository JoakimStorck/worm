import time
import numpy as np
import pandas as pd
from core.occupations.utils import optimal_assignment

from core.statistics.log import log

def batched_communewise_assignment(
    individuals_df, jobs_df,
    alpha_chi=5.0, alpha_xi=5.0, alpha_geo=1.0,
    batch_size=1000, verbose=True
):
    inds = individuals_df.copy()
    jobs = jobs_df.copy()
    all_matches = []
    batch_nr = 1
    while len(inds) > 0 and len(jobs) > 0:
        inds_batch = inds.iloc[:batch_size]
        jobs_batch = jobs.iloc[:batch_size]
        matches = optimal_assignment(
            inds_batch, jobs_batch,
            alpha_chi=alpha_chi, alpha_xi=alpha_xi, alpha_geo=alpha_geo
        )
        if matches.empty:
            break
        all_matches.append(matches)
        inds = inds[~inds['individual_id'].isin(matches['individual_id'])]
        jobs = jobs[~jobs['job_id'].isin(matches['job_id'])]
        if verbose:
            log(f"    - Kommunbatch {batch_nr}: {len(matches)} matchade, kvar: {len(inds)} individer, {len(jobs)} jobb.")
        batch_nr += 1

    if all_matches:
        return pd.concat(all_matches, ignore_index=True)
    else:
        return pd.DataFrame(columns=["individual_id", "job_id", "utility"])


def greedy_deso_matching(
    individuals, jobs,
    alpha_chi=5.0, alpha_xi=5.0, alpha_geo=1.0,
    batch_size=1000, verbose=True
):
    inds = individuals.copy()
    jobs_df = jobs.copy()
    inds["deso_code"] = inds["deso_code"].astype(str)
    jobs_df["deso_code"] = jobs_df["deso_code"].astype(str)
    all_matchings = []
    total_matched_inds = 0

    deso_codes = inds["deso_code"].dropna().unique()
    if verbose:
        log(f"\nMatcherar först {len(deso_codes)} DeSO...")

    for ix, deso in enumerate(deso_codes, 1):
        t_batch_start = time.time()
        i_mask = inds["deso_code"] == deso
        j_mask = jobs_df["deso_code"] == deso
        inds_batch = inds[i_mask]
        jobs_batch = jobs_df[j_mask]
        n_inds = len(inds_batch)
        n_jobs = len(jobs_batch)
        if verbose:
            log(f"[{ix}/{len(deso_codes)}] DeSO {deso}: {n_inds} individer, {n_jobs} jobb kvar.")
        if n_inds == 0 or n_jobs == 0:
            continue
        m = optimal_assignment(
            inds_batch, jobs_batch,
            alpha_chi=alpha_chi, alpha_xi=alpha_xi, alpha_geo=alpha_geo
        )
        t_batch = time.time() - t_batch_start
        if len(m) == 0:
            continue
        all_matchings.append(m)
        total_matched_inds += len(m)
        inds = inds[~inds["individual_id"].isin(m["individual_id"])]
        jobs_df = jobs_df[~jobs_df["job_id"].isin(m["job_id"])]
        if verbose:
            log(f"  - Matchade {len(m)} i denna DeSO (totalt {total_matched_inds}). Tid: {t_batch:.2f} s")
        if verbose:
            log(f"  - Återstående: {len(inds)} individer, {len(jobs_df)} jobb")

    # Kommunnivå i batcher
    if len(inds) > 0 and len(jobs_df) > 0:
        if verbose:
            log(f"\nMatchar kvarvarande på kommunnivå (block om {batch_size}) ({len(inds)} individer, {len(jobs_df)} jobb)...")
        muni_codes = inds["municipal_code"].dropna().unique()
        for j, muni in enumerate(muni_codes, 1):
            i_mask = inds["municipal_code"] == muni
            j_mask = jobs_df["municipal_code"] == muni
            inds_batch = inds[i_mask]
            jobs_batch = jobs_df[j_mask]
            if len(inds_batch) == 0 or len(jobs_batch) == 0:
                continue
            t_batch_start = time.time()
            m = batched_communewise_assignment(
                inds_batch, jobs_batch,
                alpha_chi=alpha_chi, alpha_xi=alpha_xi, alpha_geo=alpha_geo,
                batch_size=batch_size, verbose=verbose
            )

            t_batch = time.time() - t_batch_start
            if len(m) > 0:
                all_matchings.append(m)
                total_matched_inds += len(m)
                inds = inds[~inds["individual_id"].isin(m["individual_id"])]
                jobs_df = jobs_df[~jobs_df["job_id"].isin(m["job_id"])]
                if verbose:
                    log(f"    - Kommun {muni}: matchade {len(m)} (totalt {total_matched_inds}), tid: {t_batch:.2f} s")
                if verbose:
                    log(f"    - Återstående: {len(inds)} individer, {len(jobs_df)} jobb")

    # Sista batch: globalt
    if len(inds) > 0 and len(jobs_df) > 0:
        if verbose:
            log(f"\nGlobal sista matchningsbatch (ingen geografi): {len(inds)} individer, {len(jobs_df)} jobb.")
        t_batch_start = time.time()
        m = batched_communewise_assignment(
            inds_batch, jobs_batch,
            alpha_chi=alpha_chi, alpha_xi=alpha_xi, alpha_geo=alpha_geo,
            batch_size=batch_size, verbose=verbose
        )
        t_batch = time.time() - t_batch_start
        if len(m) > 0:
            all_matchings.append(m)
            total_matched_inds += len(m)
            if verbose:
                log(f"  - Globalt matchade {len(m)}. Tid: {t_batch:.2f} s")
        else:
            if verbose:
                log("  - Ingen möjlig global matchning kvar.")

    if verbose:
        log(f"\nSlutlig summering: matchade totalt {total_matched_inds} individer.\n")

    if all_matchings:
        result = pd.concat(all_matchings, ignore_index=True)
    else:
        result = pd.DataFrame(columns=["individual_id", "job_id", "utility"])
    return result

import numpy as np
import pandas as pd
import time

def batch_split(df, batch_size):
    """Returnerar lista av batcher med index från df."""
    N = len(df)
    if N == 0:
        return []
    n_batches = max(1, int(np.ceil(N / batch_size)))
    indices = np.array_split(df.index, n_batches)
    return [df.loc[idx] for idx in indices]


def interleaved_multilevel_batch_matching(
    individuals, jobs,
    batch_frac_deso=0.20, batch_frac_muni=0.10, batch_frac_global=0.05,
    alpha_chi=5.0, alpha_xi=5.0, alpha_geo=1.0,
    min_batch=10, verbose=True
):
    inds = individuals.copy()
    jobs_df = jobs.copy()
    inds["deso_code"] = inds["deso_code"].astype(str)
    jobs_df["deso_code"] = jobs_df["deso_code"].astype(str)
    inds["municipal_code"] = inds["municipal_code"].astype(str)
    jobs_df["municipal_code"] = jobs_df["municipal_code"].astype(str)

    all_matchings = []
    total_matched = 0
    round_num = 1

    t_start = time.time()
    while len(inds) > 0 and len(jobs_df) > 0:
        t_round = time.time()
        matched_this_round = 0

        # 1. DeSO batches (parallel across zones)
        deso_codes = inds["deso_code"].dropna().unique()
        if verbose:
            log(f"\n[ROUND {round_num}] DeSO batch matching, zones: {len(deso_codes)}")
        for deso in deso_codes:
            i_mask = inds["deso_code"] == deso
            j_mask = jobs_df["deso_code"] == deso
            inds_batch = inds[i_mask]
            jobs_batch = jobs_df[j_mask]
            if len(inds_batch) == 0 or len(jobs_batch) == 0:
                continue
            n_ind_batch = max(int(batch_frac_deso * len(inds_batch)), min_batch)
            n_job_batch = max(int(batch_frac_deso * len(jobs_batch)), min_batch)
            inds_sel = inds_batch.sample(min(n_ind_batch, len(inds_batch)), random_state=round_num)
            jobs_sel = jobs_batch.sample(min(n_job_batch, len(jobs_batch)), random_state=round_num)
            matches = optimal_assignment(
                inds_sel, jobs_sel,
                alpha_chi=alpha_chi, alpha_xi=alpha_xi, alpha_geo=alpha_geo
            )
            if len(matches) > 0:
                matched_this_round += len(matches)
                all_matchings.append(matches)
                inds = inds[~inds["individual_id"].isin(matches["individual_id"])]
                jobs_df = jobs_df[~jobs_df["job_id"].isin(matches["job_id"])]
            if verbose and len(matches) > 0:
                log(f"    - DeSO {deso}: matched {len(matches)}, left: {len(inds)} individuals, {len(jobs_df)} jobs.")

        # 2. Municipal batch (across all remaining individuals/jobs per municipality)
        muni_codes = inds["municipal_code"].dropna().unique()
        if verbose:
            log(f"\n[ROUND {round_num}] Municipal batch matching, municipalities: {len(muni_codes)}")
        for muni in muni_codes:
            i_mask = inds["municipal_code"] == muni
            j_mask = jobs_df["municipal_code"] == muni
            inds_batch = inds[i_mask]
            jobs_batch = jobs_df[j_mask]
            if len(inds_batch) == 0 or len(jobs_batch) == 0:
                continue
            n_ind_batch = max(int(batch_frac_muni * len(inds_batch)), min_batch)
            n_job_batch = max(int(batch_frac_muni * len(jobs_batch)), min_batch)
            inds_sel = inds_batch.sample(min(n_ind_batch, len(inds_batch)), random_state=round_num+1)
            jobs_sel = jobs_batch.sample(min(n_job_batch, len(jobs_batch)), random_state=round_num+1)
            matches = optimal_assignment(
                inds_sel, jobs_sel,
                alpha_chi=alpha_chi, alpha_xi=alpha_xi, alpha_geo=alpha_geo
            )
            if len(matches) > 0:
                matched_this_round += len(matches)
                all_matchings.append(matches)
                inds = inds[~inds["individual_id"].isin(matches["individual_id"])]
                jobs_df = jobs_df[~jobs_df["job_id"].isin(matches["job_id"])]
            if verbose and len(matches) > 0:
                log(f"    - Municipality {muni}: matched {len(matches)}, left: {len(inds)} individuals, {len(jobs_df)} jobs.")

        # 3. Global batch
        if verbose:
            log(f"\n[ROUND {round_num}] Global batch matching")
        if len(inds) == 0 or len(jobs_df) == 0:
            break
        n_ind_batch = max(int(batch_frac_global * len(inds)), min_batch)
        n_job_batch = max(int(batch_frac_global * len(jobs_df)), min_batch)
        inds_sel = inds.sample(min(n_ind_batch, len(inds)), random_state=round_num+2)
        jobs_sel = jobs_df.sample(min(n_job_batch, len(jobs_df)), random_state=round_num+2)
        matches = optimal_assignment(
            inds_sel, jobs_sel,
            alpha_chi=alpha_chi, alpha_xi=alpha_xi, alpha_geo=alpha_geo
        )
        if len(matches) > 0:
            matched_this_round += len(matches)
            all_matchings.append(matches)
            inds = inds[~inds["individual_id"].isin(matches["individual_id"])]
            jobs_df = jobs_df[~jobs_df["job_id"].isin(matches["job_id"])]
        if verbose and len(matches) > 0:
            log(f"    - Global: matched {len(matches)}, left: {len(inds)} individuals, {len(jobs_df)} jobs.")

        round_time = time.time() - t_round
        total_matched += matched_this_round
        if verbose:
            log(f"[END OF ROUND {round_num}] Matched this round: {matched_this_round}, total matched: {total_matched}. Time: {round_time:.2f} s")

        # Stop if nothing matched this round (converged)
        if matched_this_round == 0:
            if verbose:
                log(f"No more matches found, stopping.")
            break
        round_num += 1

    total_time = time.time() - t_start
    if verbose:
        log(f"\nFinal summary: total matched: {total_matched}, time: {total_time:.2f} s")

    if all_matchings:
        result = pd.concat(all_matchings, ignore_index=True)
    else:
        result = pd.DataFrame(columns=["individual_id", "job_id", "utility"])
    return result

