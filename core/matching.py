# core/matching.py

import time
import numpy as np
import pandas as pd
from core.occupations.utils import global_greedy_matching

from core.log import log



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
            matches = global_greedy_matching(
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
            matches = global_greedy_matching(
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
        matches = global_greedy_matching(
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

def multilevel_exhaustive_matching(
    individuals, jobs,
    alpha_chi=5.0, alpha_xi=5.0, alpha_geo=1.0,
    verbose=True
):
    inds = individuals.copy()
    jobs_df = jobs.copy()
    inds["deso_code"] = inds["deso_code"].astype(str)
    jobs_df["deso_code"] = jobs_df["deso_code"].astype(str)
    inds["municipal_code"] = inds["municipal_code"].astype(str)
    jobs_df["municipal_code"] = jobs_df["municipal_code"].astype(str)

    all_matchings = []
    total_matched = 0

    # 1. DeSO-nivå: Kör tills ingen mer matchning sker på denna nivå
    changed = True
    round_num = 1
    while changed and len(inds) > 0 and len(jobs_df) > 0:
        changed = False
        deso_codes = inds["deso_code"].dropna().unique()
        if verbose: print(f"\n[ROUND {round_num}] DeSO matchning, {len(deso_codes)} zoner")
        for deso in deso_codes:
            i_mask = inds["deso_code"] == deso
            j_mask = jobs_df["deso_code"] == deso
            inds_batch = inds[i_mask]
            jobs_batch = jobs_df[j_mask]
            if len(inds_batch) == 0 or len(jobs_batch) == 0:
                continue
            matches = global_greedy_matching(
                inds_batch, jobs_batch,
                alpha_chi=alpha_chi, alpha_xi=alpha_xi, alpha_geo=alpha_geo
            )
            if len(matches) > 0:
                changed = True
                all_matchings.append(matches)
                inds = inds[~inds["individual_id"].isin(matches["individual_id"])]
                jobs_df = jobs_df[~jobs_df["job_id"].isin(matches["job_id"])]
                if verbose:
                    print(f"  - DeSO {deso}: matched {len(matches)}")
        round_num += 1

    # 2. Kommunnivå: Kör tills ingen mer matchning sker på denna nivå
    changed = True
    round_num = 1
    while changed and len(inds) > 0 and len(jobs_df) > 0:
        changed = False
        muni_codes = inds["municipal_code"].dropna().unique()
        if verbose: print(f"\n[ROUND {round_num}] Kommun-matchning, {len(muni_codes)} kommuner")
        for muni in muni_codes:
            i_mask = inds["municipal_code"] == muni
            j_mask = jobs_df["municipal_code"] == muni
            inds_batch = inds[i_mask]
            jobs_batch = jobs_df[j_mask]
            if len(inds_batch) == 0 or len(jobs_batch) == 0:
                continue
            matches = global_greedy_matching(
                inds_batch, jobs_batch,
                alpha_chi=alpha_chi, alpha_xi=alpha_xi, alpha_geo=alpha_geo
            )
            if len(matches) > 0:
                changed = True
                all_matchings.append(matches)
                inds = inds[~inds["individual_id"].isin(matches["individual_id"])]
                jobs_df = jobs_df[~jobs_df["job_id"].isin(matches["job_id"])]
                if verbose:
                    print(f"  - Kommun {muni}: matched {len(matches)}")
        round_num += 1

    # 3. Global nivå: Kör tills ingen mer matchning sker
    changed = True
    round_num = 1
    while changed and len(inds) > 0 and len(jobs_df) > 0:
        changed = False
        matches = global_greedy_matching(
            inds, jobs_df,
            alpha_chi=alpha_chi, alpha_xi=alpha_xi, alpha_geo=alpha_geo
        )
        if len(matches) > 0:
            changed = True
            all_matchings.append(matches)
            inds = inds[~inds["individual_id"].isin(matches["individual_id"])]
            jobs_df = jobs_df[~jobs_df["job_id"].isin(matches["job_id"])]
            if verbose:
                print(f"  - Globalt: matched {len(matches)}")
        round_num += 1

    # Sammanställ resultat
    if all_matchings:
        result = pd.concat(all_matchings, ignore_index=True)
    else:
        result = pd.DataFrame(columns=["individual_id", "job_id", "utility"])
    return result
