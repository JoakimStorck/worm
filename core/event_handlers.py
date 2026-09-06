# core/event_handlers.py

import numpy as np
import pandas as pd
from core.occupations.utils import (xi_add, chi_add, r_add, apply_capability_update,
                                    effective_wage, search_once, vacant_job_indices)

def _resolve_individual_index(world, holder):
    """jobs['individual_id'] innehåller historiskt två olika saker: strängen ur
    kolumnen individual_id (batch-matchningen) eller DataFrame-indexet
    (handle_start_job). Denna funktion accepterar båda och returnerar ett
    giltigt index, eller None. Aldrig .at[] direkt på ett okänt värde -- det
    SKAPAR en ny rad i pandas i stället för att höja fel."""
    if holder is None or (isinstance(holder, float) and pd.isna(holder)):
        return None
    ind = world.individuals
    if holder in ind.index:
        return holder
    hit = ind.index[ind['individual_id'] == holder]
    return hit[0] if len(hit) else None


def _update_individual(world, idx, delta_chi=0.0, delta_xi=0.0, delta_r=0.0):
    """Uppdaterar chi/xi/r_i, haller x_occ/y_occ synkade och tar ut bytarkostnad."""
    ind = world.individuals
    sim = world.cfg_reader.config.get('simulation', {})
    kappa = sim.get('switch_cost_kappa', 0.05)
    bfm = sim.get('breadth_from_move', 0.25)
    r_now = ind.at[idx, 'r_i'] if 'r_i' in ind.columns else 0.0
    chi, xi, r_i, x, y = apply_capability_update(
        ind.at[idx, 'chi'], ind.at[idx, 'xi'], r_now,
        delta_chi=delta_chi, delta_xi=delta_xi, delta_r=delta_r,
        switch_cost_kappa=kappa, breadth_from_move=bfm)
    ind.at[idx, 'chi'] = chi
    ind.at[idx, 'xi'] = xi
    ind.at[idx, 'r_i'] = r_i
    ind.at[idx, 'x_occ'] = x
    ind.at[idx, 'y_occ'] = y


def handle_quit_job(event, world):
    idx = event['agent_id']
    individuals = world.individuals
    jobs = world.jobs
    individuals.at[idx, 'status'] = 'unemployed'
    job_id = individuals.at[idx, 'job_id']
    if pd.notna(job_id):
        jobs.loc[jobs['job_id'] == job_id, 'individual_id'] = np.nan
        world.set_job_filled(job_id, False)
        individuals.at[idx, 'job_id'] = np.nan
    # Arbetslös: reservationslönen faller till rho * senaste lön
    if 'w_res' in individuals.columns:
        rho = world.cfg_reader.config.get('simulation', {}).get('rho_reservation', 0.7)
        individuals.at[idx, 'w_res'] = rho * float(individuals.at[idx, 'w_res'])

    prop_edu = individuals.at[idx, 'propensity_start_education']
    if np.random.rand() < prop_edu:
        eff = (world.cfg_reader.config.get('simulation', {})
               .get('event_effects', {}).get('start_education', {}).get('broad', {}))
        timing = world.cfg_reader.get_event_timing('start_education')
        if timing['dist'] == 'uniform':
            days_until_start = np.random.uniform(timing['min'], timing['max'])
        else:
            raise ValueError("Unknown dist for start_education")
        edu_event = {
            "time": event['time'] + days_until_start,
            "agent_id": idx,
            "event_type": "start_education",
            "params": {
                'education_type': 'broad',
                'delta_chi': eff['delta_chi'],
                'delta_r': eff.get('delta_r', eff.get('delta_H', 0.0)),
                'duration': eff['duration'],
                'delta_xi': eff.get('delta_xi', 10),
            }
        }
        world._push_event(edu_event)
    else:
        timing = world.cfg_reader.get_event_timing('start_job_search')
        if timing['dist'] == 'exponential':
            interval = np.random.exponential(timing['mean'])
        else:
            raise ValueError("Unknown dist for start_job_search")
        search_event = {
            "time": event['time'] + interval,
            "agent_id": idx,
            "event_type": "start_job_search",
            "params": {}
        }
        world._push_event(search_event)

    world.event_logger.log_event(world, event, "individual")

def handle_start_job(event, world):
    idx = event['agent_id']
    job_id = event['params']['job_id']
    individuals = world.individuals
    jobs = world.jobs

    # Positionsuppslag via job_index: boolesk jämförelse över hela tabellen
    # kostade 825 mikrosekunder per anrop, en dict 33.
    pos = world.job_index().get(job_id)

    # Positionen kan ha upphört under rekryteringstiden. En UTLOVAD position
    # har individual_id NaN, så handle_destroy_job hittar ingen innehavare att
    # meddela: arbetaren tillträdde ett jobb som inte längre fanns och blev
    # bokförd som sysselsatt utan aktiv position. Det gav en residual i
    # identiteten U = L - J + V på ett par hundra individer per femårskörning.
    still_available = (
        pos is not None
        and bool(jobs.iat[pos, jobs.columns.get_loc('active')])
        and pd.isna(jobs.iat[pos, jobs.columns.get_loc('individual_id')])
    )
    if not still_available:
        if pos is not None and 'pending' in jobs.columns:
            jobs.iat[pos, jobs.columns.get_loc('pending')] = False

        # Höll arbetaren redan en giltig position behåller hon den. Att
        # ovillkorligen sätta status unemployed och nolla job_id lämnade den
        # gamla positionen tillsatt med hennes id men utan sysselsatt
        # innehavare -- 28 sådana fall i en femårskörning (kategori E i
        # scripts/check_invariants.py).
        held = individuals.at[idx, 'job_id'] if 'job_id' in individuals.columns else None
        held_pos = world.job_index().get(held) if pd.notna(held) else None
        still_holds = (
            held_pos is not None
            and bool(jobs.iat[held_pos, jobs.columns.get_loc('active')])
            and jobs.iat[held_pos, jobs.columns.get_loc('individual_id')]
                == individuals.at[idx, 'individual_id']
        )
        if still_holds:
            world.event_logger.log_event(world, event, extra={
                'event_detail': 'job_gone_before_start_kept_previous', 'job_id': job_id})
            return

        individuals.at[idx, 'status'] = 'unemployed'
        individuals.at[idx, 'job_id'] = np.nan
        timing = world.cfg_reader.get_event_timing('start_job_search')
        interval = (np.random.exponential(timing.get('mean', 28.0))
                    if timing.get('dist', 'exponential') == 'exponential' else 30.0)
        world._push_event({"time": float(event['time'] + interval), "agent_id": idx,
                           "event_type": "start_job_search", "params": {}})
        world.event_logger.log_event(world, event, extra={
            'event_detail': 'job_gone_before_start', 'job_id': job_id})
        return

    # Ett jobbyte måste frigöra den gamla positionen. Utan det blir den kvar
    # med arbetarens id utan innehavare, och antalet tillsatta positioner
    # överstiger antalet sysselsatta.
    prev = individuals.at[idx, 'job_id'] if 'job_id' in individuals.columns else None
    if pd.notna(prev) and prev != job_id:
        prev_pos = world.job_index().get(prev)
        if prev_pos is not None:
            jobs.iat[prev_pos, jobs.columns.get_loc('individual_id')] = np.nan
            world.set_job_filled(prev, False)

    individuals.at[idx, 'status'] = 'employed'
    individuals.at[idx, 'job_id'] = job_id
    job_idx = (jobs.index[pos:pos + 1] if pos is not None
               else jobs.index[jobs['job_id'] == job_id])
    # Skriv kolumnvärdet, inte radindexet: batch-matchningen gör likadant.
    jobs.loc[job_idx, 'individual_id'] = (
        individuals.at[idx, 'individual_id'] if 'individual_id' in individuals.columns else idx)

    world.set_job_filled(job_id, True)
    job_row = jobs.iloc[pos] if pos is not None else jobs[jobs['job_id'] == job_id].iloc[0]

    # Övergångens geometri: avstånd i planet, och samma storhet normaliserad mot
    # jobbets task-radie. u_R är direkt jämförbar med den empiriska
    # mobilitetsfördelningen (median 1.03 task-radier, CPS 2020-2024).
    extra = {'job_id': job_id}
    try:
        d_task = float(np.hypot(individuals.at[idx, 'x_occ'] - job_row['x_occ'],
                                individuals.at[idx, 'y_occ'] - job_row['y_occ']))
        r_o = float(job_row.get('r_o', np.nan))
        extra['d_task'] = round(d_task, 4)
        if r_o and not np.isnan(r_o) and r_o > 0:
            extra['u_R'] = round(d_task / r_o, 4)
    except (KeyError, TypeError, ValueError):
        pass

    # Reservationslön = faktisk lön i det nya jobbet: ett byte måste förbättra.
    if 'w_res' in individuals.columns and 'wage' in jobs.columns:
        sg = world.cfg_reader.config.get('simulation', {}).get('sigma_gamma', 1.0)
        w_eff = effective_wage(individuals.loc[idx], job_row, sigma_gamma=sg)
        individuals.at[idx, 'w_res'] = w_eff
        extra['wage_eff'] = round(w_eff, 4)
    world.event_logger.log_event(world, event, extra=extra)
    n_employees = job_row['employer_size']
    prop_training = individuals.at[idx, 'propensity_internal_training']
    P_training = prop_training * world.employer_training_prob(n_employees)

    training_timing = world.cfg_reader.get_event_timing('start_internal_training')
    if np.random.rand() < P_training:
        if training_timing['dist'] == 'uniform':
            interval = np.random.uniform(training_timing['min'], training_timing['max'])
        else:
            interval = 28
        t_training = event['time'] + interval
        delta_r = np.random.uniform(0.0, 0.02)
        delta_chi = np.random.uniform(0.01, 0.04)
        training_event = {
            "time": t_training,
            "agent_id": idx,
            "event_type": "start_internal_training",
            "params": {'delta_r': delta_r, 'delta_chi': delta_chi}
        }
        world._push_event(training_event)

    job_change_timing = world.cfg_reader.get_event_timing('internal_job_change')
    prop_job_change = individuals.at[idx, 'propensity_internal_job_change']
    if np.random.rand() < prop_job_change:
        if job_change_timing['dist'] == 'exponential':
            interval = np.random.exponential(job_change_timing['mean'])
        elif job_change_timing['dist'] == 'uniform':
            interval = np.random.uniform(job_change_timing['min'], job_change_timing['max'])
        else:
            interval = 182
        t_change = event['time'] + interval
        effects = (world.cfg_reader.config.get('simulation', {})
               .get('event_effects', {}).get('internal_job_change', {}))
        delta_xi = effects.get('delta_xi', 0.0)
        delta_chi = effects.get('delta_chi', 0.0)
        delta_r = effects.get('delta_r', effects.get('delta_H', 0.0))
        change_event = {
            "time": t_change,
            "agent_id": idx,
            "event_type": "internal_job_change",
            "params": {'delta_xi': delta_xi, 'delta_chi': delta_chi, 'delta_r': delta_r}
        }
        world._push_event(change_event)

    quit_timing = world.cfg_reader.get_event_timing('quit_job')
    if quit_timing['dist'] == 'normal':
        duration = np.random.normal(quit_timing['mean'], quit_timing['std'])
        duration = max(duration, 1)
    elif quit_timing['dist'] == 'lognormal':
        sigma = quit_timing.get('sigma', 0.4)
        mu = np.log(quit_timing['mean']) - 0.5 * sigma ** 2
        duration = np.random.lognormal(mean=mu, sigma=sigma)
    else:
        duration = 365
    t_quit = event['time'] + duration
    quit_event = {
        "time": t_quit,
        "agent_id": idx,
        "event_type": "quit_job",
        "params": {}
    }
    world._push_event(quit_event)

def handle_start_job_search(event, world):
    """En sökomgång: relevansmängd i uppgiftsrummet, därefter logit-val över
    överskottet.

    Profilering av en Mora-körning visade 175 av 192 sekunder här, men bara 31
    i matchningskärnan. Resten var kopior av hela jobbtabellen,
    kategorikonverteringar och rundlogik -- en gång per sökande, 24 284 gånger
    per simulerat år. Beräkningen sker nu på numpy-arrayer: mätt 169
    mikrosekunder mot 7.2 millisekunder, utan att begränsa vilka positioner
    den sökande får överväga.
    """
    idx = event['agent_id']
    sim = world.cfg_reader.config.get('simulation', {})

    job_pos, surplus = search_once(
        world.individuals.loc[idx], world.jobs,
        np.flatnonzero(world.vacant_mask()),
        sigma_gamma=sim.get('sigma_gamma', 1.0),
        commute_cost_per_km=sim.get('commute_cost_per_km', 0.005),
        min_surplus=sim.get('min_surplus', 0.0),
        choice_scale=sim.get('choice_scale', 0.05),
        arrays=world.job_arrays(),
    )

    if job_pos is not None:
        job_id = world.jobs.iloc[job_pos]['job_id']
        # Rekryteringstid: positionen är utlovad men tillträds först senare.
        # Utan fördröjning fylls en vakans i samma ögonblick den matchas, och
        # vakansvaraktigheten blir omkring 13 dagar mot faktiska 30-60. Det är
        # därför vakansgraden hamnade under 1.3 procent mot svenska cirka 2.
        world.set_job_pending(job_id)
        lag_cfg = world.cfg_reader.get_event_timing('recruitment_lag')
        lag = (np.random.exponential(lag_cfg.get('mean', 30.0))
               if lag_cfg.get('dist', 'exponential') == 'exponential'
               else float(lag_cfg.get('mean', 30.0)))
        world._push_event({
            "time": float(event['time'] + lag),
            "agent_id": idx,
            "event_type": "start_job",
            "params": {"job_id": job_id},
        })
        world.event_logger.log_event(world, event, extra={
            'event_detail': 'match_completed', 'job_id': job_id,
            'surplus': round(surplus, 4)})
        world.n_matched_in_month += 1
    else:
        current_prop = world.individuals.at[idx, 'propensity_start_education']
        new_prop = min(current_prop + 0.1, 1.0)
        world.individuals.at[idx, 'propensity_start_education'] = new_prop

        decay = float(sim.get('reservation_decay_per_search', 1.0))
        floor = float(sim.get('reservation_floor', 0.0))
        if 'w_res' in world.individuals.columns and decay < 1.0:
            w_res = float(world.individuals.at[idx, 'w_res'])
            world.individuals.at[idx, 'w_res'] = max(w_res * decay, floor)

        world.event_logger.log_event(world, event, extra={
            'event_detail': 'match_failed', 'new_propensity': round(new_prop, 3)})

        timing = world.cfg_reader.get_event_timing('start_job_search')
        interval = (np.random.exponential(timing.get('mean', 28.0))
                    if timing.get('dist', 'exponential') == 'exponential' else 30.0)
        world._push_event({
            "time": float(event['time'] + interval),
            "agent_id": idx,
            "event_type": "start_job_search",
            "params": {},
        })


def handle_start_education(event, world):
    idx = event['agent_id']
    education_type = event['params'].get('education_type', 'specialist')
    delta_chi = event['params'].get('delta_chi', 0.2)
    delta_r = event['params'].get('delta_r', event['params'].get('delta_H', 0.0))
    delta_xi = event['params'].get('delta_xi', 0.5)

    if education_type == 'specialist':
        _update_individual(world, idx, delta_chi=delta_chi, delta_r=delta_r)
    elif education_type == 'broad':
        _update_individual(world, idx, delta_xi=delta_xi, delta_r=delta_r)

    # Den som börjar studera lämnar sin position. Utan detta stod jobbet kvar
    # som tillsatt med hennes id: låst för andra sökande och räknat som
    # tillsatt utan sysselsatt innehavare, vilket bröt identiteten
    # U = L - J + V. career_break frigör redan på detta sätt.
    jobs = world.jobs
    prev_job = world.individuals.at[idx, 'job_id']
    if pd.notna(prev_job):
        prev_pos = world.job_index().get(prev_job)
        if prev_pos is not None:
            jobs.iat[prev_pos, jobs.columns.get_loc('individual_id')] = np.nan
            world.set_job_filled(prev_job, False)
        world.individuals.at[idx, 'job_id'] = np.nan

    world.individuals.at[idx, 'status'] = 'in_education'
    world.event_logger.log_event(world, event, extra={'education_type': education_type})

    education_duration = world.cfg_reader.parse_time_with_unit(event['params'].get('duration', 365.25))
    end_event = {
        "time": event['time'] + education_duration,
        "agent_id": idx,
        "event_type": "end_education",
        "params": {'education_type': education_type}
    }
    world._push_event(end_event)

def handle_end_education(event, world):
    idx = event['agent_id']
    world.individuals.at[idx, 'status'] = 'unemployed'
    world.event_logger.log_event(world, event, extra={'event_detail': 'education_finished'})

    timing = world.cfg_reader.get_event_timing('start_job_search')
    if timing['dist'] == 'exponential':
        interval = np.random.exponential(timing['mean'])
    elif timing['dist'] == 'uniform':
        interval = np.random.uniform(timing['min'], timing['max'])
    else:
        raise ValueError("Unknown dist for start_job_search")

    search_event = {
        "time": event['time'] + interval,
        "agent_id": idx,
        "event_type": "start_job_search",
        "params": {}
    }
    world._push_event(search_event)

def handle_start_internal_training(event, world):
    idx = event['agent_id']
    delta_r = event['params'].get('delta_r', event['params'].get('delta_H', 0.0))
    delta_chi = event['params'].get('delta_chi', 0.05)
    _update_individual(world, idx, delta_chi=delta_chi, delta_r=delta_r)
    world.event_logger.log_event(world, event, extra={'event_detail': 'start_internal_training'})

    if world.individuals.at[idx, 'status'] == 'employed' and np.random.rand() < 0.15:
        training_timing = world.cfg_reader.get_event_timing('start_internal_training')
        if training_timing['dist'] == 'uniform':
            interval = np.random.uniform(training_timing['min'], training_timing['max'])
        else:
            interval = 28
        t_training = event['time'] + interval
        rec_delta_r = np.random.uniform(0.0, 0.01)
        rec_delta_chi = np.random.uniform(0.01, 0.02)
        more_training = {
            "time": t_training,
            "agent_id": idx,
            "event_type": "start_internal_training",
            "params": {'delta_r': rec_delta_r, 'delta_chi': rec_delta_chi}
        }
        world._push_event(more_training)

def handle_internal_job_change(event, world):
    idx = event['agent_id']
    delta_xi = event['params'].get('delta_xi', 3)
    delta_r = event['params'].get('delta_r', event['params'].get('delta_H', 0.0))
    delta_chi = event['params'].get('delta_chi', 0.03)
    _update_individual(world, idx, delta_xi=delta_xi, delta_chi=delta_chi, delta_r=delta_r)
    world.event_logger.log_event(world, event, extra={'event_detail': 'internal_job_change'})

def handle_career_break(event, world):
    idx = event['agent_id']
    individuals = world.individuals
    jobs = world.jobs
    # Nolla jobb-koppling om den finns
    job_id = individuals.at[idx, 'job_id']
    if pd.notna(job_id):
        jobs.loc[jobs['job_id'] == job_id, 'individual_id'] = np.nan
        world.set_job_filled(job_id, False)
        individuals.at[idx, 'job_id'] = np.nan

    individuals.at[idx, 'status'] = 'career_break'
    delta_chi = -1 * event['params'].get('delta_chi', 0.05)
    delta_r = -1 * event['params'].get('delta_r', event['params'].get('delta_H', 0.0))
    _update_individual(world, idx, delta_chi=delta_chi, delta_r=delta_r)
    world.event_logger.log_event(world, event, extra={'event_detail': 'career_break'})
    break_duration = event['params'].get('duration', 0.5 * 365.25)
    end_event = {
        "time": event['time'] + break_duration,
        "agent_id": idx,
        "event_type": "start_job_search",
        "params": {}
    }
    world._push_event(end_event)

def handle_destroy_job(event, world):
    """Positionen upphör att existera (till skillnad från quit_job, där
    arbetaren lämnar men jobbet blir vakant). Sitter någon på jobbet blir hen
    arbetslös och börjar söka."""
    job_id = event['params']['job_id']
    jobs = world.jobs
    m = jobs['job_id'] == job_id
    if not m.any() or not bool(jobs.loc[m, 'active'].iloc[0]):
        return
    holder = jobs.loc[m, 'individual_id'].iloc[0]
    jobs.loc[m, 'active'] = False
    world.set_job_inactive(job_id)
    jobs.loc[m, 'destroyed_time'] = float(event['time'])
    jobs.loc[m, 'individual_id'] = np.nan

    idx = _resolve_individual_index(world, holder)
    if idx is not None:
        ind = world.individuals
        ind.at[idx, 'status'] = 'unemployed'
        ind.at[idx, 'job_id'] = np.nan
        if 'w_res' in ind.columns:
            rho = world.cfg_reader.config.get('simulation', {}).get('rho_reservation', 0.7)
            ind.at[idx, 'w_res'] = rho * float(ind.at[idx, 'w_res'])
        timing = world.cfg_reader.get_event_timing('start_job_search') or {}
        interval = (np.random.exponential(timing.get('mean', 28.0))
                    if timing.get('dist', 'exponential') == 'exponential' else 0.0)
        world._push_event({"time": float(event['time'] + interval), "agent_id": idx,
                           "event_type": "start_job_search", "params": {}})
        world.event_logger.log_event(world, event,
                                     extra={"event_detail": "job_destroyed_holder_displaced",
                                            "job_id": job_id})
    else:
        world.event_logger.log_event(world, event,
                                     extra={"event_detail": "vacancy_destroyed", "job_id": job_id})


def handle_new_month(event, world):
    from core.statistics.basic_stats import analyze_world
    year = event['params'].get('year')
    month = event['params'].get('month')
    n_posted = world.post_vacancies_batch(event['time'])
    stats = analyze_world(world)

    n_individuals = stats['total_individuals']
    n_jobs = stats['total_jobs']
    n_employers = stats['total_employers']
    employed = stats['employed_individuals']
    unemployed = stats['unemployed_individuals']
    unmatched_jobs = stats['unmatched_jobs']
    not_in_labour_force = stats['individuals_not_in_labour_force']
    world.event_logger.log_event(world, event, extra={
        "month": month,
        "employed": employed,
        "unemployed": unemployed,
        "unmatched_jobs": unmatched_jobs,
        "not_in_labour_force": not_in_labour_force,
        "active_jobs": n_jobs,
        "posted": n_posted
    }, print_line=True)
    # Reset match-counter
    world.n_matched_in_month = 0

def handle_new_year(event, world):
    from core.statistics.basic_stats import analyze_world
    year = event['params'].get('year')
    stats = analyze_world(world)
    employed = stats['employed_individuals']
    unemployed = stats['unemployed_individuals']
    unmatched_jobs = stats['unmatched_jobs']
    not_in_labour_force = stats['individuals_not_in_labour_force']
    world.event_logger.log_event(world, event, extra={
        "year": year,
        "employed": employed,
        "unemployed": unemployed,
        "unmatched_jobs": unmatched_jobs,
        "not_in_labour_force": not_in_labour_force,
        "active_jobs": stats['total_jobs']
    }, print_line=True)

RULE_SWITCH = {
    "quit_job": handle_quit_job,
    "start_job": handle_start_job,
    "start_job_search": handle_start_job_search,
    "start_education": handle_start_education,
    "end_education": handle_end_education,
    "start_internal_training": handle_start_internal_training,
    "internal_job_change": handle_internal_job_change,
    "career_break": handle_career_break,
    "destroy_job": handle_destroy_job,
    "new_month": handle_new_month,
    "new_year": handle_new_year,
}
