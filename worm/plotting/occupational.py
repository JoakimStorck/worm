import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.animation import FuncAnimation
from collections import defaultdict

def load_initial_state(indiv_path, job_path):
    individuals = pd.read_csv(indiv_path)
    jobs = pd.read_csv(job_path)
    return individuals, jobs

def load_eventlog(eventlog_path):
    # Dynamisk tolkning av eventloggen: första två kolumner är alltid tid och eventtyp
    with open(eventlog_path, encoding='utf-8') as f:
        lines = f.readlines()
    events = []
    for line in lines:
        items = [x.strip() for x in line.strip().split(",")]
        d = {}
        d['time'] = float(items[0])
        d['event'] = items[1]
        for kv in items[2:]:
            if ' ' in kv:
                k, v = kv.split(' ', 1)
                # Försök att tolka som float om möjligt
                try:
                    v = float(v)
                except ValueError:
                    pass
                d[k] = v
        events.append(d)
    df = pd.DataFrame(events)
    return df

def replay_to_time(individuals, jobs, eventlog, T, selected_inds=None):
    indiv = individuals.copy()
    jobs_df = jobs.copy()
    indiv.set_index('individual_id', inplace=True)
    jobs_df.set_index('job_id', inplace=True)

    indiv_paths = defaultdict(list)
    indiv_job_path = defaultdict(list)  # NYTT: Samla alla jobb-punkter för pathways

    if selected_inds is not None:
        eventlog = eventlog[eventlog['individual_id'].isin(selected_inds)]

    for i, row in eventlog[eventlog['time'] <= T].sort_values('time').iterrows():
        event = row['event']
        if event == 'start_job':
            iid = row.get('individual_id')
            jid = row.get('job_id')
            if pd.notnull(iid) and iid in indiv.index:
                indiv.at[iid, 'status'] = 'employed'
                indiv.at[iid, 'job_id'] = jid
                if 'chi' in row: indiv.at[iid, 'chi'] = row['chi']
                if 'xi' in row: indiv.at[iid, 'xi'] = row['xi']
                if 'H' in row: indiv.at[iid, 'H'] = row['H']
                indiv_paths[iid].append((row['time'], row.get('chi', np.nan), row.get('xi', np.nan)))
                # NYTT: Spara jobbpositionen
                if 'chi' in row and 'xi' in row and not (pd.isnull(row['chi']) or pd.isnull(row['xi'])):
                    indiv_job_path[iid].append((row['xi'], row['chi']))
            if pd.notnull(jid) and jid in jobs_df.index:
                jobs_df.at[jid, 'individual_id'] = iid
        elif event == 'quit_job':
            iid = row.get('individual_id')
            if pd.notnull(iid) and iid in indiv.index:
                jobs_df.loc[jobs_df['individual_id'] == iid, 'individual_id'] = np.nan
                indiv.at[iid, 'status'] = 'unemployed'
                indiv.at[iid, 'job_id'] = ''
                if 'chi' in row: indiv.at[iid, 'chi'] = row['chi']
                if 'xi' in row: indiv.at[iid, 'xi'] = row['xi']
                if 'H' in row: indiv.at[iid, 'H'] = row['H']
                indiv_paths[iid].append((row['time'], row.get('chi', np.nan), row.get('xi', np.nan)))
        elif event == 'start_education':
            iid = row.get('individual_id')
            if pd.notnull(iid) and iid in indiv.index:
                indiv.at[iid, 'status'] = 'in_education'
                if 'chi' in row: indiv.at[iid, 'chi'] = row['chi']
                if 'xi' in row: indiv.at[iid, 'xi'] = row['xi']
                if 'H' in row: indiv.at[iid, 'H'] = row['H']
                indiv_paths[iid].append((row['time'], row.get('chi', np.nan), row.get('xi', np.nan)))
    indiv.reset_index(inplace=True)
    jobs_df.reset_index(inplace=True)
    # Returnera även jobb-pathways
    return indiv, jobs_df, indiv_paths, indiv_job_path

def plot_occupation_space(
        indiv, jobs, indiv_paths=None,
        plot_jobs=True,
        plot_indivs=True,
        plot_lines=False,
        plot_H_circle=False,
        selected_inds=None,
        figsize=(8,8),
        save_path=None,
        title=None,
        T=None,
        indiv_job_path=None   # NYTT!
    ):
    fig, ax = plt.subplots(figsize=figsize, subplot_kw={'projection':'polar'})

    if plot_jobs and jobs is not None:
        jobsfilt = jobs
        if selected_inds is not None:
            jobsfilt = jobs[(jobs['individual_id'].isin(selected_inds)) | (jobs['individual_id'].isnull())]
        ax.scatter(jobsfilt['xi'], jobsfilt['chi'], c='blue', s=8, alpha=0.3, label='Jobs')

    # Plotta individer som punkter (valfritt filter)
    if plot_indivs:
        indfilt = indiv
        if selected_inds is not None:
            indfilt = indiv[indiv['individual_id'].isin(selected_inds)]
        ax.scatter(indfilt['xi'], indfilt['chi'], c='red', s=16, alpha=0.8, label='Individuals')

    # Plotta H-cirkel kring varje individ
    if plot_H_circle and plot_indivs:
        for _, row in indfilt.iterrows():
            draw_H_circle(ax, row['chi'], row['xi'], row['H'])

            # Plotta linjer mellan jobb och individ vid anställning
            if plot_lines and jobs is not None:
                indiv_dict = indiv.set_index('individual_id').to_dict('index')
                # Filtrera om selected_inds används
                if selected_inds is not None:
                    selected_set = set(selected_inds)
                    for _, row in jobs.iterrows():
                        iid = row['individual_id']
                        if pd.notnull(iid) and iid in indiv_dict and iid in selected_set:
                            ind_row = indiv_dict[iid]
                            ax.plot([row['xi'], ind_row['xi']], [row['chi'], ind_row['chi']],
                                    color='gray', alpha=0.7, lw=1.0)
                else:
                    for _, row in jobs.iterrows():
                        iid = row['individual_id']
                        if pd.notnull(iid) and iid in indiv_dict:
                            ind_row = indiv_dict[iid]
                            ax.plot([row['xi'], ind_row['xi']], [row['chi'], ind_row['chi']],
                                    color='gray', alpha=0.3, lw=0.8)


    # Plotta pathways för utvalda individer
    if indiv_paths and selected_inds:
        colors = plt.get_cmap('tab10')
        for j, iid in enumerate(selected_inds):
            pts = [(row_xi, row_chi) for t, row_chi, row_xi in indiv_paths.get(iid, []) if not (np.isnan(row_chi) or np.isnan(row_xi))]
            if len(pts) > 1:
                xis, chis = zip(*pts)  # xi = vinkel, chi = radie
                ax.plot(xis, chis, '-', lw=2, alpha=0.7, color=colors(j % 10), label=f'Path {iid}')
                ax.scatter(xis[-1], chis[-1], color=colors(j % 10), s=40, marker='*')

    # NYTT: Plotta jobb-pathways för utvalda individer
    print(f"[DEBUG] indiv_job_path={indiv_job_path}, selected_inds={selected_inds}")
    if indiv_job_path and selected_inds:
        colors = plt.get_cmap('tab10')
        for j, iid in enumerate(selected_inds):
            job_pts = indiv_job_path.get(iid, [])
            if len(job_pts) > 1:
                xi_vals, chi_vals = zip(*job_pts)
                print(f"[DEBUG] Job pathway for {iid}:")
                for n, (xi, chi) in enumerate(job_pts):
                    print(f"  Step {n}: xi={xi}, chi={chi}")
                ax.plot(xi_vals, chi_vals, '--', lw=1.5, alpha=0.8, color=colors(j % 10), label=f'Job path {iid}')

    ax.set_rlabel_position(0)
    ax.grid(True, linestyle=':', alpha=0.4)
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    if title:
        ax.set_title(title)
    plt.legend(loc='upper right', fontsize=8)
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.show()
    return fig, ax

# Rita cirkel
def draw_H_circle(ax, chi, xi, H, color='orange', lw=0.7, alpha=0.5, n_points=80):
    theta = np.linspace(0, 2*np.pi, n_points)
    r = chi + H * np.cos(theta)
    t = xi + H * np.sin(theta) / max(chi, 0.1)
    ax.plot(t, r, color=color, lw=lw, alpha=alpha, zorder=8)

# --------- MAIN WORKFLOW EXEMPEL ---------
# (byt ut mot dina filnamn eller anropa från annan kod)

def replay_plot_occupation_space(
    indiv_path,
    job_path,
    eventlog_path,
    T=None,
    plot_jobs=True,
    plot_indivs=True,
    plot_lines=False,
    plot_H_circle=False,
    selected_inds=None,
    show_pathways=True,
    save_path=None
):
    individuals, jobs = load_initial_state(indiv_path, job_path)
    eventlog = load_eventlog(eventlog_path)
    if T is None:
        T = eventlog['time'].max()
    indiv_T, jobs_T, indiv_paths, indiv_job_path = replay_to_time(individuals, jobs, eventlog, T, selected_inds)
    fig, ax = plot_occupation_space(
        indiv_T,
        jobs_T,
        indiv_paths if show_pathways else None,
        plot_jobs=plot_jobs,
        plot_indivs=plot_indivs,
        plot_lines=plot_lines,
        plot_H_circle=plot_H_circle,
        selected_inds=selected_inds,
        title=f"Occupation space at t={T}",
        save_path=save_path,
        indiv_job_path=indiv_job_path     # NYTT!
    )
    return fig, ax

# Exempelanrop:
# replay_plot_occupation_space(
#     'initial_state_individuals.csv',
#     'initial_state_jobs.csv',
#     'eventlog.txt',
#     T=150,
#     plot_jobs=True,
#     plot_indivs=True,
#     plot_lines=True,
#     plot_H_circle=True,
#     selected_inds=['2080_i003478', '2080_i056177'],
#     show_pathways=True,
# )

# -------- ANIMATION/VIDEO ------------
def animate_replay_occupation_space(
    indiv_path,
    job_path,
    eventlog_path,
    selected_inds=None,
    t_start=0,
    t_end=None,
    n_frames=30,
    **kwargs
):
    individuals, jobs = load_initial_state(indiv_path, job_path)
    eventlog = load_eventlog(eventlog_path)
    if t_end is None:
        t_end = eventlog['time'].max()
    times = np.linspace(t_start, t_end, n_frames)

    fig, ax = plt.subplots(figsize=(8,8), subplot_kw={'projection':'polar'})
    paths = {}

    def update(frame):
        ax.cla()
        indiv_T, jobs_T, indiv_paths = replay_to_time(individuals, jobs, eventlog, times[frame])
        plot_occupation_space(
            indiv_T, jobs_T, indiv_paths if selected_inds else None,
            plot_jobs=kwargs.get('plot_jobs', True),
            plot_indivs=kwargs.get('plot_indivs', True),
            plot_lines=kwargs.get('plot_lines', False),
            plot_H_circle=kwargs.get('plot_H_circle', False),
            selected_inds=selected_inds,
            title=f"t={times[frame]:.1f}",
            save_path=None
        )
        return ax,

    ani = FuncAnimation(fig, update, frames=n_frames, blit=False)
    plt.show()
    return ani
