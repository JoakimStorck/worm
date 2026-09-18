#core/statistics/basic_stats.py

import os
import yaml
import numpy as np
import pandas as pd


def _extern(df):
    if "extern" not in df.columns:
        return pd.Series(False, index=df.index)
    return df["extern"].fillna(False).astype(bool)


def analyze_world(world):
    """Stockar för regionen, med den öppna randen isärhållen (docs/omgivning.md).

    ARBETSKRAFTEN ÄR INVÅNARNA. Sysselsatta, arbetslösa och de utanför
    arbetskraften räknas bland regionens invånare; en inpendlare (extern
    individ) ingår inte. Utpendlarna -- invånare vars jobb är externt -- är
    sysselsatta invånare.

    JOBBEN ÄR REGIONENS. total_jobs och unmatched_jobs räknar de aktiva jobb
    som ligger i regionen; ett externt jobb har ingen vakans här.

    Därmed gäller U = L - J + V + In - Ut, där In är inpendlare i regionens
    jobb och Ut invånare i externa jobb. Med en sluten rand är båda noll och
    identiteten den gamla.
    """
    ind, jobs = world.individuals, world.jobs
    boende = ~_extern(ind)
    status = ind['status']
    regional = ~_extern(jobs)
    aktiv = (jobs['active'].astype(bool) if 'active' in jobs.columns
             else pd.Series(True, index=jobs.index))
    stats = {
        "total_individuals": int(boende.sum()),
        "total_jobs": int((aktiv & regional).sum()),
        "total_employers": len(world.employers),
        "employed_individuals": int((boende & (status == 'employed')).sum()),
        "unemployed_individuals": int((boende & (status == 'unemployed')).sum()),
        "unmatched_jobs": int((jobs['individual_id'].isna() & aktiv & regional).sum()),
        "individuals_not_in_labour_force": int((boende & (status == 'not_in_labor_force')).sum()),
        "in_commuters": int((~boende & (status == 'employed')).sum()),
        "out_commuters": int((jobs['individual_id'].notna() & aktiv & ~regional).sum()),
    }
    # V MOT SCB:s VAKANSBEGREPP. unmatched_jobs räknar alla obesatta aktiva
    # positioner, också de som är UTLOVADE: någon har tackat ja men inte
    # tillträtt, och under uppsägningstiden (~30 dagar av de 80 en vakans
    # lever) står positionen kvar som obesatt. SCB:s vakans är en ledig
    # befattning som rekryteringen ännu inte löst; en tillsatt befattning med
    # tillträde om en månad är inte ledig. Identiteten U = L - J + V använder
    # unmatched_jobs och rörs inte -- open_vacancies är jämförelsetalet.
    if 'active' in jobs.columns and 'pending' in jobs.columns:
        stats["open_vacancies"] = int((jobs['individual_id'].isna() & aktiv & regional
                                       & ~jobs['pending'].fillna(False).astype(bool)).sum())
    else:
        stats["open_vacancies"] = stats["unmatched_jobs"]
    return stats

def hist_as_dict(data, bins=20, range=None):
    hist, bin_edges = np.histogram(data, bins=bins, range=range)
    return {
        "counts": hist.tolist(),
        "bin_edges": bin_edges.tolist()
    }

def save_basic_stats(result, outdir, tag="basic_stats"):
    """Ögonblicksbild av tillståndet till JSON.

    Histogrammen över chi, xi och r_i beskrev den gamla individmodellen, där
    de var tillståndsvariabler. Med kompetenscirklarna är de HÄRLEDDA mått
    (core/occupations/competence.Circles.summarize), och att spara deras
    fördelningar utan cirklarna bakom är missvisande. De ersätts av
    fördelningar som faktiskt bär information om tillståndet: konkurrenskraft,
    kompetensmassa och löner.

    Analysklara tabeller skrivs i stället av scripts/export_tables.py.
    """
    import json

    ind = result.individuals
    jobs = result.jobs
    employers = result.employers
    print(f'tag={tag}')

    def dist(series, bins=20):
        x = pd.to_numeric(series, errors="coerce").dropna() if series is not None else None
        if x is None or x.empty:
            return None
        return {"mean": float(x.mean()), "std": float(x.std()),
                "min": float(x.min()), "max": float(x.max()),
                "median": float(x.median()),
                "hist": hist_as_dict(x, bins=bins)}

    act = jobs["active"].astype(bool) if "active" in jobs.columns else None
    stats = {
        "tag": tag,
        "n_individuals": len(ind),
        "n_jobs": int(act.sum()) if act is not None else len(jobs),
        "n_employers": len(employers),
        "individual_status_counts": ind['status'].value_counts().to_dict()
        if 'status' in ind.columns else {},
        "job_vacancy_counts": {
            "vacant": int((jobs['individual_id'].isna() & (act if act is not None else True)).sum()),
            "filled": int((jobs['individual_id'].notna() & (act if act is not None else True)).sum()),
        },
        "individuals": {k: dist(ind[k]) for k in
                        ("chi", "xi", "r_i", "R", "w_res", "w_neg", "tenure_years")
                        if k in ind.columns},
        "jobs": {k: dist(jobs[k]) for k in ("wage", "r_o") if k in jobs.columns},
    }
    with open(f"{outdir}/basic_stats_{tag}.json", "w") as f:
        json.dump(stats, f, indent=2)

