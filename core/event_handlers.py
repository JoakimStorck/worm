# core/event_handlers.py

import numpy as np
import pandas as pd
from core.occupations.utils import xi_add, chi_add, r_add, apply_capability_update

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
        individuals.at[idx, 'job_id'] = np.nan

    prop_edu = individuals.at[idx, 'propensity_start_education']
    if np.random.rand() < prop_edu:
        eff = world.cfg_reader.config['simulation']['event_effects']['start_education']['broad']
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
    individuals.at[idx, 'status'] = 'employed'
    individuals.at[idx, 'job_id'] = job_id
    job_idx = jobs['job_id'] == job_id
    jobs.loc[job_idx, 'individual_id'] = idx
    world.event_logger.log_event(world, event, extra={'job_id': job_id})

    job_row = jobs[jobs['job_id'] == job_id].iloc[0]
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
        effects = world.cfg_reader.config['simulation']['event_effects']['internal_job_change']
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
    idx = event['agent_id']
    df = world.individuals.loc[[idx]]
    matches = world.match_individuals_to_jobs(
        individuals=df,
        mode="exhaustive_multilevel",
        alpha_chi=world.cfg_reader.config['simulation']['alpha_chi'],
        alpha_xi=world.cfg_reader.config['simulation']['alpha_xi'],
        alpha_geo=world.cfg_reader.config['simulation']['alpha_geo'],
        sigma_gamma=world.cfg_reader.config['simulation'].get('sigma_gamma', 1.0),
        utility_min=world.cfg_reader.config['simulation'].get('utility_min', 0.05),
    )
    if not matches.empty:
        job_id = matches.iloc[0]['job_id']
        utility = matches.iloc[0]['utility']
        t_start = event['time']
        start_event = {
            "time": t_start,
            "agent_id": idx,
            "event_type": "start_job",
            "params": {'job_id': job_id}
        }
        world._push_event(start_event)
        world.n_matched_in_month += 1
        world.event_logger.log_event(world, event, extra={"event_detail": "match_completed", "job_id": job_id, "utility": utility})
    else:
        current_prop = world.individuals.at[idx, 'propensity_start_education']
        new_prop = min(current_prop + 0.1, 1.0)
        world.individuals.at[idx, 'propensity_start_education'] = new_prop

        timing = world.cfg_reader.get_event_timing('start_job_search')
        if timing['dist'] == 'exponential':
            interval = np.random.exponential(timing['mean'])
        else:
            interval = 30.0
        t_retry = event['time'] + interval

        retry_event = {
            "time": t_retry,
            "agent_id": idx,
            "event_type": "start_job_search",
            "params": {}
        }
        world._push_event(retry_event)
        world.event_logger.log_event(
            world, event,
            extra={"event_detail": "match_failed", "new_propensity_start_education": new_prop}
        )

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

def handle_new_month(event, world):
    from core.statistics.basic_stats import analyze_world
    year = event['params'].get('year')
    month = event['params'].get('month')
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
        "not_in_labour_force": not_in_labour_force
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
        "not_in_labour_force": not_in_labour_force
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
    "new_month": handle_new_month,
    "new_year": handle_new_year,
}
