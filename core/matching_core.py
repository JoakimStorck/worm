"""Matchningen som EN kodväg, delad av uppstarten och körningen.

Förmatchningen använde tidigare interleaved_multilevel_batch_matching, en
tidigare version av samma modell: global_greedy_matching gör samma sak som
search_once -- överskott, dragning på passform, sortering på S -- men fyra
patchar efter. Den kände varken till kön i överskottet (0057), arbetsgivarens
urval (0055), kravgrinden (0049) eller loneformeln w = Pi_j * p**theta med
arbetsgivareffekt (0061, 0063). Nio tusen matchningar, alltså större delen av
beståndet i flera år, var därför gjorda under en modell vi inte längre tror
på, och varje mått på beståndet blandade två arbetsmarknader.

Värre: dess geografiska trappa DeSO -> kommun -> globalt är en SYSTEMATISK
partitionering. Individer i samma bostadsområde liknar varandra i
uppgiftsrummet, och den som råkade komma tidigt i deso_codes-ordningen tog de
bästa jobben i hela kommunen. Startbeståndet bar alltså en geografisk gradient
som var ett artefakt av körordningen -- i en modell där geografi är
glesbygdspapprets förklaringsvariabel.

Fem fel i den här serien var två kodvägar som gjorde samma sak och glidit
isär. En tredje väg som LIKNAR search_once skulle bli den sjätte. Därför
återimplementerar den här modulen ingenting: uppstarten anropar samma
funktioner som händelsehanterarna, och skillnaden ligger bara i inramningen --
omschemaläggning och tillträdesfördröjning hör till händelsekedjan, inte till
matchningen.
"""

import numpy as np


def search_config(world):
    """De argument search_once ska ha, på ETT ställe.

    Byggdes tidigare inline i handle_start_job_search. Det var där vitlistan i
    0061 kunde uppstå: theta och labour_share filtrerades bort på vägen till
    negotiated_wage, och en hel femfrökörning gav identiska tal som före
    patchen utan att något larmade. Med argumenten samlade här kan uppstarten
    inte få andra värden än körningen.
    """
    sim = world.cfg_reader.config.get('simulation', {})
    brg = sim.get('bargaining', {}) or {}
    return dict(
        sigma_gamma=sim.get('sigma_gamma', 1.0),
        commute_cost_per_km=sim.get('commute_cost_per_km', 0.005),
        min_surplus=sim.get('min_surplus', 0.0),
        choice_scale=sim.get('choice_scale', 0.05),
        requirement_k=float(sim.get('requirement_k', 2.0)),
        bargaining=({k: v for k, v in brg.items() if k != 'enabled'}
                    if brg.get('enabled', True) else None),
    )


def apply_once(world, idx, t_now):
    """En sökomgång för en arbetslös: möte, val, ANSÖKAN.

    Returnerar (job_id, w_neg, q, surplus, commute_km) eller (None,)*5.

    Ingen omschemaläggning och ingen händelseloggning: det hör till
    handle_start_job_search, som ramar in den här funktionen. Uppstarten
    behöver varken.
    """
    from core.occupations.utils import search_once

    ind = world.individuals
    if 'status' in ind.columns and ind.at[idx, 'status'] != 'unemployed':
        return (None,) * 5

    cfg = search_config(world)
    job_pos, surplus, w_neg, q_hire, km = search_once(
        ind.loc[idx], world.jobs,
        np.flatnonzero(world.vacant_mask()),
        queue=(world.applicant_counts()
               if hasattr(world, 'applicant_counts') else None),
        arrays=world.job_arrays(),
        competitiveness=(
            (lambda jx, jy, jro: world.circles.competitiveness(
                idx, jx, jy, jro, world.competence_params()))
            if hasattr(world, 'circles') else None),
        **cfg)
    if job_pos is None:
        return (None,) * 5

    job_id = world.jobs.iloc[job_pos]['job_id']
    ind.at[idx, 'w_neg'] = w_neg          # kolumnen garanteras av World.prepare
    world.file_application(job_id, idx, float(t_now),
                           q=q_hire, w_neg=w_neg, surplus=surplus,
                           commute_km=km)
    return job_id, w_neg, q_hire, surplus, km


def close_all_windows(world, t_now, immediate=False):
    """Stänger varje öppen annons genom handle_close_vacancy.

    immediate=True genomför tillträdena direkt i stället för att lägga dem i
    kön till efter start_delay_days. Uppstarten sker vid t = 0 och ska inte
    lägga tillträden i händelsekön: hela poängen är att beståndet finns när
    simuleringen börjar.

    Tillträdena fångas VID KÄLLAN, genom att _push_event tillfälligt avleds,
    i stället för att läsas ur kön efteråt. Kön är inte en pålitlig kanal här:
    _push_event kastar tyst allt bortom simulation_end_time, och i ett första
    försök innebar det att 172 positioner sattes till pending medan
    tillträdena försvann -- noll anställda och en läcka i bokföringen.
    """
    from core import event_handlers as eh

    starter = []
    if immediate:
        orig = world._push_event

        def fånga(ev, _o=orig):
            if ev.get("event_type") == "start_job":
                starter.append(dict(ev, time=float(t_now)))
                return
            return _o(ev)
        world._push_event = fånga
    try:
        for jid in list(getattr(world, 'applications', {}).keys()):
            eh.handle_close_vacancy({"time": float(t_now), "agent_id": None,
                                     "event_type": "close_vacancy",
                                     "params": {"job_id": jid}}, world)
    finally:
        if immediate:
            world._push_event = orig

    for ev in starter:
        eh.handle_start_job(ev, world)
    return len(starter)


def bootstrap_matching(world, t_now=0.0, log=print):
    """Uppstarten: samma matchning som körningen, i slumpmässiga omgångar.

    OMGÅNGSSTORLEKEN HÄRLEDS UR MÅLTÄTHETEN och sätts inte fritt. Under
    körning finns ungefär 1/tightness sökande per ledig vakans; varje omgång
    får därför lika många, så konkurrensen vid start liknar den under
    körningen. Antalet omgångar blir ett resultat i stället för en parameter.

    SLUMPMÄSSIG PARTITIONERING, inte geografisk. DeSO-områden är
    bostadsområden, och individerna i ett område liknar varandra i
    uppgiftsrummet: körs de i tur och ordning konkurrerar de som borde
    konkurrera i olika omgångar, och den som kommer först tar de bästa jobben
    i hela kommunen. Startbeståndet skulle då bära en gradient efter
    partitionsordning -- permanent, i fem år, i en modell där geografi är en
    förklaringsvariabel. Med slumpmässiga omgångar är varje omgång ett
    stickprov ur hela populationen och ordningen bär ingen information.

    Att tidiga omgångar har fler lediga jobb att välja bland är oundvikligt i
    vilken sekvens som helst, men slår nu slumpmässigt över individer i
    stället för systematiskt över områden. Det är prövbart: två frön med olika
    partitionsordning ska ge samma lönefördelning i beståndet, inom frönas
    vanliga spann.
    """
    sim = world.cfg_reader.config.get('simulation', {})
    per_vak = float(sim.get('bootstrap_applicants_per_vacancy', 2.4))
    max_omg = int(sim.get('bootstrap_max_rounds', 40))

    # Jobbkolumnerna och cirklarna måste finnas: uppstarten är samma kod som
    # körningen och behöver active, pending och competitiveness. Anropet är
    # idempotent och görs om i simulate().
    if hasattr(world, 'prepare'):
        world.prepare()

    ind = world.individuals
    if 'status' not in ind.columns:
        return {}
    rng = np.random.default_rng(sim.get('seed_bootstrap', 20260909))

    lediga = list(ind.index[ind['status'] == 'unemployed'])
    rng.shuffle(lediga)
    kö = list(lediga)
    n_start = len(kö)

    totalt, omgångar, per_omgång = 0, 0, []
    par = []
    while kö and omgångar < max_omg:
        n_vak = int(world.vacant_mask().sum())
        if n_vak == 0:
            break
        n = max(1, min(len(kö), int(round(per_vak * n_vak))))
        omgång, kö = kö[:n], kö[n:]
        for i in omgång:
            apply_once(world, i, t_now)
        före = dict(zip(ind.index, ind['job_id']))
        fyllda = close_all_windows(world, t_now, immediate=True)
        for i in omgång:
            j = ind.at[i, 'job_id']
            if j is not None and str(j) != 'nan' and före.get(i) != j:
                par.append({"individual_id": ind.at[i, 'individual_id']
                            if 'individual_id' in ind.columns else i,
                            "job_id": j,
                            "utility": float(ind.at[i, 'w_neg'])
                            if 'w_neg' in ind.columns
                            and ind.at[i, 'w_neg'] == ind.at[i, 'w_neg'] else 0.0})
        omgångar += 1
        totalt += fyllda
        per_omgång.append(fyllda)
        if fyllda == 0 and not kö:
            break
        if fyllda == 0 and omgångar > 2 and sum(per_omgång[-3:]) == 0:
            break                      # inget rör sig längre

    import pandas as pd
    st = {"matchings": pd.DataFrame(par, columns=["individual_id", "job_id",
                                                  "utility"]),
          "bootstrap_rounds": omgångar, "bootstrap_hired": totalt,
          "bootstrap_labour_force": n_start,
          "bootstrap_share_hired": round(totalt / max(n_start, 1), 4),
          "bootstrap_per_round": per_omgång}
    if log:
        log(f"Uppstart: {totalt} av {n_start} matchade på {omgångar} omgångar "
            f"({100 * totalt / max(n_start, 1):.1f} %), "
            f"per omgång {per_omgång}")
    return st
