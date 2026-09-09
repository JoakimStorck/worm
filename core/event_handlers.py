# core/event_handlers.py

import numpy as np
import pandas as pd
from core.occupations.utils import (search_once, vacant_job_indices,
                                    retraining_target)

def _become_unemployed(world, idx, free_job=True):
    """Sätter en individ till arbetslös och frigör hennes eventuella position.

    Att skriva status utan att frigöra jobbet har varit samma återkommande fel
    på flera ställen: positionen blir kvar tillsatt med individens id men utan
    sysselsatt innehavare, låst för andra sökande, och bokföringen
    U = L - J + V går inte ihop. Använd denna i stället för att sätta status
    direkt.
    """
    ind = world.individuals
    if free_job and 'job_id' in ind.columns:
        held = ind.at[idx, 'job_id']
        if pd.notna(held):
            pos = world.job_index().get(held)
            jobs = world.jobs
            if pos is not None:
                jobs.iat[pos, jobs.columns.get_loc('individual_id')] = np.nan
                world.set_job_filled(held, False)
            ind.at[idx, 'job_id'] = np.nan
    world.clear_active_occupation(idx)
    ind.at[idx, 'status'] = 'unemployed'


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

    # Källyrket läses INNAN det skrivs över: u_R_occ mäts från det yrke hon
    # kom från. Att uppdatera först gav u_R_occ = 0 för varje övergång.
    prev_onet = (individuals.at[idx, 'last_onet_code']
                 if 'last_onet_code' in individuals.columns else None)

    individuals.at[idx, 'status'] = 'employed'
    individuals.at[idx, 'job_id'] = job_id
    # Kompetens: jobbets yrke blir den aktiva cirkeln.
    _jr = jobs.iloc[pos] if pos is not None else None
    if _jr is not None and 'onet_code' in jobs.columns:
        world.set_active_occupation(idx, _jr['onet_code'], _jr['x_occ'], _jr['y_occ'],
                                    _jr.get('r_o', 0.27))
        if 'last_onet_code' in individuals.columns:
            individuals.at[idx, 'last_onet_code'] = _jr['onet_code']
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
        # u_R som CPS mäter det: från senaste yrkes centroid, normerat med
        # KÄLLANS radie. Det är detta som ska jämföras med 1.03.
        prev = prev_onet
        if prev is not None and not (isinstance(prev, float) and np.isnan(prev)):
            g = world._geom_lookup(prev)
            if g is not None and g.get('r_o', 0) > 0:
                d_occ = float(np.hypot(g['x_occ'] - job_row['x_occ'], g['y_occ'] - job_row['y_occ']))
                extra['u_R_occ'] = round(d_occ / float(g['r_o']), 4)
                extra['from_onet'] = prev
                extra['to_onet'] = job_row.get('onet_code')
                # CPS räknar bara yrkesBYTEN. Återgång till eget yrke är ett
                # eget mått: hur ofta den arbetslösa hittar tillbaka.
                extra['occ_change'] = int(str(prev) != str(job_row.get('onet_code')))
    except (KeyError, TypeError, ValueError):
        pass

    # Reservationslön = FÖRHANDLAD lön i det nya jobbet: ett byte måste
    # förbättra. Den förhandlade lönen följer med i händelsens parametrar från
    # matchningen; saknas den (äldre händelser) används fältlönen.
    # Båda loggas så att gapet mellan fält och förhandling är synligt.
    if 'w_res' in individuals.columns and 'wage' in jobs.columns:
        w_field = float(job_row.get('wage', 1.0))
        w_par = event['params'].get('w_neg')
        try:
            w_eff = float(w_par)
            if not np.isfinite(w_eff):
                w_eff = w_field
        except (TypeError, ValueError):
            w_eff = w_field
        individuals.at[idx, 'w_res'] = w_eff
        if 'w_neg' in individuals.columns:
            individuals.at[idx, 'w_neg'] = w_eff
        # Utgångspunkt för nästa revision: revisionen belönar TILLVÄXT i
        # konkurrenskraft sedan förra gången, inte nivån.
        q_par0 = event['params'].get('q_hire')
        try:
            if q_par0 is not None and float(q_par0) > 0:
                individuals.at[idx, 'q_last'] = float(q_par0)
        except (TypeError, ValueError):
            pass
        extra['w_field'] = round(w_field, 4)
        extra['w_neg'] = round(w_eff, 4)
        # YRKETS fältlön, utan arbetsgivareffekten. w_field är JOBBETS lön,
        # Pi_j = Pi_o * exp(eta_j), och med w = Pi_j * p**theta står eta i
        # både täljare och nämnare i w_neg/w_field och försvinner IDENTISKT
        # ur kvoten. Måttet kunde därför varken visa spridning inom yrke
        # eller arbetsgivarkomponenten: bottenkvartilen låg på exakt 1.000
        # med 43 procent på punkten trots att sd(log w_field) inom yrke var
        # 0.103. Med w_occ separat blir w_neg/w_occ jämförbart med SCB:s
        # lönestrukturstatistik per SSYK, och w_field/w_occ isolerar eta.
        try:
            eta = float(job_row.get('wage_eta', 0.0) or 0.0)
        except (TypeError, ValueError):
            eta = 0.0
        extra['w_occ'] = round(w_field * float(np.exp(-eta)), 4)

    # Beståndet mäts årsvis i handle_new_year; lönen bärs av individen.
        km_par = event['params'].get('commute_km')
        if km_par is not None:
            try:
                extra['commute_km'] = round(float(km_par), 3)
            except (TypeError, ValueError):
                pass
        na = event['params'].get('n_applicants')
        if na is not None:
            extra['n_applicants'] = int(na)
        q_par = event['params'].get('q_hire')
        if q_par is not None:
            try:
                extra['q_hire'] = round(float(q_par), 4)
            except (TypeError, ValueError):
                pass
        # Kravet loggas så att låg konkurrenskraft i KRÄVANDE jobb går att
        # skilja från låg konkurrenskraft i jobb där den inte spelar roll.
        rq = job_row.get('r_req') if hasattr(job_row, 'get') else None
        if rq is not None and not (isinstance(rq, float) and np.isnan(rq)):
            extra['r_req'] = round(float(rq), 3)
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
    from core.matching_core import apply_once

    # Statusvakt, möte, val och ansökan ligger i matching_core.apply_once och
    # delas med uppstarten. Kvar här är det HÄNDELSESPECIFIKA: loggningen och
    # omschemaläggningen. Två kodvägar som gör samma sak har glidit isär fem
    # gånger i den här serien; uppstarten återimplementerar därför ingenting.
    job_id, w_neg, q_hire, surplus, commute_km = apply_once(
        world, idx, float(event['time']))

    if job_id is not None:
        world.event_logger.log_event(world, event, extra={
            'event_detail': 'application_filed', 'job_id': job_id,
            'surplus': round(surplus, 4), 'w_neg': round(w_neg, 4),
            'q_hire': round(q_hire, 4), 'commute_km': round(commute_km, 3)})

        # Hon fortsätter söka medan ansökan ligger ute. En ansökan i taget
        # kostade henne hela fönstret per försök. Reservationen faller INTE
        # här: hon har inte fått avslag.
        _reschedule_search(world, idx, float(event['time']),
                           decay_reservation=False)
    elif ('status' not in world.individuals.columns
          or world.individuals.at[idx, 'status'] == 'unemployed'):
        current_prop = world.individuals.at[idx, 'propensity_start_education']
        new_prop = min(current_prop + 0.1, 1.0)
        world.individuals.at[idx, 'propensity_start_education'] = new_prop
        _decay_reservation(world, idx)

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


def _decay_reservation(world, idx):
    """Ett avslag ÄR en misslyckad sökning ur hennes synvinkel."""
    sim = world.cfg_reader.config.get('simulation', {})
    decay = float(sim.get('reservation_decay_per_search', 1.0))
    floor = float(sim.get('reservation_floor', 0.0))
    if 'w_res' in world.individuals.columns and decay < 1.0:
        w_res = float(world.individuals.at[idx, 'w_res'])
        world.individuals.at[idx, 'w_res'] = max(w_res * decay, floor)


def _reschedule_search(world, idx, t_now, decay_reservation=True):
    """Tillbaka i sökandet.

    ANVÄNDS BARA när hon inte redan har en levande sökkedja. Sedan
    parallella ansökningar infördes får hon en ny sökning direkt vid ANSÖKAN,
    så ett avslag ska inte ge en till: annars får varje ansökan två kedjor i
    stället för en, och med fem ansökningar före en anställning blir det
    2**5 sökhändelser per person. Kön växer exponentiellt och körningen
    stannar av.
    """
    sim = world.cfg_reader.config.get('simulation', {})
    if decay_reservation:
        decay = float(sim.get('reservation_decay_per_search', 1.0))
        floor = float(sim.get('reservation_floor', 0.0))
        if 'w_res' in world.individuals.columns and decay < 1.0:
            w_res = float(world.individuals.at[idx, 'w_res'])
            world.individuals.at[idx, 'w_res'] = max(w_res * decay, floor)
    timing = world.cfg_reader.get_event_timing('start_job_search')
    interval = (np.random.exponential(timing.get('mean', 28.0))
                if timing.get('dist', 'exponential') == 'exponential' else 30.0)
    world._push_event({"time": float(t_now + interval), "agent_id": idx,
                       "event_type": "start_job_search", "params": {}})


def start_delay_days(world, idx):
    """Tiden från urval till tillträde: beslut plus uppsägningstid.

    Beslutet -- referenser, kontrakt -- gäller alla. Uppsägningstiden är NOLL
    för den arbetslösa och en institutionell månad för den som ska lämna en
    anställning. Annonstiden är redan avverkad när detta anropas.

    Bara annons och beslut hör till vakansen som SCB:s KV mäter: en obemannad
    befattning som rekryteringsförfarandet pågår för, inte tiden fram till
    tillträde. Utlovade positioner ingår i unmatched_jobs och därmed i V, så
    den fasta rekryteringstiden på trettio dagar låg tidigare inne i
    vakansvaraktigheten för ALLA, också för dem som inte hade något att säga
    upp.

    Uppsägningsgrenen är oåtkomlig i dag, eftersom urvalet bara släpper fram
    arbetslösa. Den finns här för att steg 2 -- sökning från anställning --
    ska ärva den färdig, och för att bokföringen ska kunna prövas medan
    populationen fortfarande är enkel.
    """
    sim = world.cfg_reader.config.get('simulation', {})
    dagar = float(sim.get('hiring_decision_days', 10.0))
    if ('status' in world.individuals.columns
            and idx in world.individuals.index
            and world.individuals.at[idx, 'status'] == 'employed'):
        dagar += float(sim.get('notice_period_days', 30.0))
    return dagar


def handle_close_vacancy(event, world):
    """Annonsen stänger: arbetsgivaren väljer bland de sökande.

    URVALET SKER PÅ q, INTE PÅ p, och det är ett eget antagande som inte
    följer av produktiviteten. Vid r_j ~ 0 är p = q**(k*r) identiskt ett för
    alla, så en rangordning på produktivitet vore platt just i den kvartil
    mekanismen finns till för -- den där u_R ligger på 1.64 mot 0.88-0.97 i
    de övriga och målet 0.70. Motivet är upplärningskostnad, risken att
    någon inte klarar sig, och förväntad kvarvarotid: arbetsgivaren föredrar
    den erfarna diskaren fast vem som helst kan diska. Prisfrågan finns inte:
    lönen är en funktion av p, så överskottet p*Pi/lambda - w är monotont i p
    över hela det tillåtna intervallet, och bäst kvalificerad sammanfaller
    med bäst per krona.

    Aritmetiken: med acceptans proportionell mot q**a blir det accepterade
    avståndet Rayleigh med skala sigma/sqrt(a). En dos ger 1.03 task-radier.
    Mötesdraget är kvar som informationsfriktion, så exponenten blir
    1 + (n-1) = n med n sökande, och n = 1/tightness = 2.1 ger 1.03/sqrt(2.1)
    = 0.71 mot papper 2:s 0.70. Andra skalan skulle därmed FÖLJA ur
    marknadstrycket i stället för att vara en andra kalibreringskonstant, och
    variationen i u_R mellan kommuner blir ett resultat och inte en parameter.

    Mekanismen självkorrigerar: vid höga krav utesluter grinden nästan alla
    sökande, poolen blir liten och urvalet tillför lite; vid r ~ 0 kvalificerar
    sig alla och urvalet biter hårt. Lokaliteten läggs alltså där den saknas.
    """
    job_id = event['params'].get('job_id')
    apps = world.close_application_window(job_id)
    t_now = float(event['time'])

    pos = world.job_index().get(job_id)
    gone = (pos is None
            or ('active' in world.jobs.columns
                and not bool(world.jobs.iat[pos, world.jobs.columns.get_loc('active')]))
            or pd.notna(world.jobs.iat[pos, world.jobs.columns.get_loc('individual_id')]))

    ind = world.individuals
    lediga = [a for a in apps
              if a['idx'] in ind.index
              and ind.at[a['idx'], 'status'] == 'unemployed'
              and pd.isna(ind.at[a['idx'], 'job_id'])]

    if gone or not lediga:
        world.event_logger.log_event(world, event, extra={
            'event_detail': 'vacancy_closed_unfilled', 'job_id': job_id,
            'n_applicants': len(apps), 'n_eligible': len(lediga)})
        for a in lediga:
            _decay_reservation(world, a['idx'])   # kedjan lever redan
        return

    win = max(lediga, key=lambda a: a['q'])
    idx = win['idx']

    # TRE TIDER, var och en med sitt skäl. Annonstiden (40 dagar) är redan
    # avverkad här. Kvar är arbetsgivarens beslut och kontrakt, som gäller
    # alla, och uppsägningstiden, som är noll för den arbetslösa och en
    # institutionell månad för den som ska lämna en anställning. Bara de två
    # första hör till vakansen som SCB mäter: KV räknar en obemannad
    # befattning som rekryteringsförfarandet pågår för, inte tiden fram till
    # tillträde. Utlovade positioner ingår i unmatched_jobs och därmed i V,
    # så rekryteringstiden låg tidigare inne i vakansvaraktigheten för alla.
    world.set_job_pending(job_id)
    lag = start_delay_days(world, idx)
    world._push_event({
        "time": t_now + lag, "agent_id": idx, "event_type": "start_job",
        "params": {"job_id": job_id, "w_neg": win['w_neg'], "q_hire": win['q'],
                   "commute_km": win['commute_km'],
                   "n_applicants": len(lediga)},
    })
    world.event_logger.log_event(world, event, extra={
        'event_detail': 'match_completed', 'job_id': job_id,
        'agent_id': idx, 'n_applicants': len(lediga),
        'surplus': round(win['surplus'], 4), 'w_neg': round(win['w_neg'], 4),
        'q_hire': round(win['q'], 4), 'commute_km': round(win['commute_km'], 3)})
    world.n_matched_in_month = getattr(world, 'n_matched_in_month', 0) + 1

    for a in lediga:
        if a['idx'] != idx:
            _decay_reservation(world, a['idx'])   # kedjan lever redan


def handle_start_education(event, world):
    """Omskolning riktad mot där arbete faktiskt finns.

    Tre ändringar mot den tidigare mekanismen. Riktningen var ett fast
    delta_xi som roterade alla åt samma håll oavsett var jobben fanns, alltså
    en slumpvandring. Kompetensen uppdaterades vid INSKRIVNINGEN, så effekten
    kom av att anmäla sig. Och en studerande kunde tillträda ett jobb mitt
    under studietiden, eftersom ett tidigare löfte låg kvar i kön.

    Nu bestäms målet av en överskottsviktad tyngdpunkt av de nåbara
    vakanserna, kompetensen uppdateras först vid slutet, och studier utesluter
    anställning. Finns inget rimligt mål sker ingen omskolning -- vilket är
    det väntade utfallet i en tunn marknad.
    """
    idx = event['agent_id']
    sim = world.cfg_reader.config.get('simulation', {})
    ind = world.individuals

    target = retraining_target(
        ind.loc[idx], world.jobs, np.flatnonzero(world.vacant_mask()),
        arrays=world.job_arrays(),
        commute_cost_per_km=sim.get('commute_cost_per_km', 0.005),
        min_surplus=sim.get('min_surplus', 0.0),
        top_k=int(sim.get('retraining_target_k', 50)))

    if target is None:
        world.event_logger.log_event(world, event, extra={
            'event_detail': 'education_no_target'})
        return

    x0, y0 = float(ind.at[idx, 'x_occ']), float(ind.at[idx, 'y_occ'])
    share = float(sim.get('retraining_share', 0.5))     # andel av vägen dit
    x1 = x0 + share * (target[0] - x0)
    y1 = y0 + share * (target[1] - y0)
    move = float(np.hypot(x1 - x0, y1 - y0))

    # Studier utesluter anställning: ett utlovat jobb släpps tillbaka.
    held = ind.at[idx, 'job_id'] if 'job_id' in ind.columns else None
    if pd.notna(held):
        pos = world.job_index().get(held)
        if pos is not None:
            world.jobs.iat[pos, world.jobs.columns.get_loc('individual_id')] = np.nan
            world.set_job_filled(held, False)
        ind.at[idx, 'job_id'] = np.nan

    ind.at[idx, 'status'] = 'in_education'

    # Varaktighet efter förflyttning: en kort sträcka är en kurs, en lång är en
    # utbildning. Omställningstiden blir därmed ett utfall, inte en konstant,
    # och längre i tunna marknader där målet ligger långt bort.
    days_per_unit = float(sim.get('retraining_days_per_unit', 900.0))
    min_days = float(sim.get('retraining_min_days', 30.0))
    duration = max(min_days, days_per_unit * move)

    world.event_logger.log_event(world, event, extra={
        'event_detail': 'education_started',
        'x_from': round(x0, 4), 'y_from': round(y0, 4),
        'x_to': round(x1, 4), 'y_to': round(y1, 4),
        'move': round(move, 4), 'duration_days': round(duration, 1),
        'municipal_code': ind.at[idx, 'municipal_code']
        if 'municipal_code' in ind.columns else None})

    world._push_event({
        "time": float(event['time'] + duration),
        "agent_id": idx,
        "event_type": "end_education",
        "params": {"x_to": x1, "y_to": y1, "move": move, "duration_days": duration},
    })


def handle_end_education(event, world):
    """Kompetensen uppdateras här, inte vid inskrivningen."""
    idx = event['agent_id']
    ind = world.individuals

    if ind.at[idx, 'status'] == 'employed':
        # Skydd mot äldre löften i kön; med den nya mekanismen ska det inte ske.
        world.event_logger.log_event(world, event, extra={
            'event_detail': 'education_finished_already_employed'})
        return

    x1 = event['params'].get('x_to')
    y1 = event['params'].get('y_to')
    move = float(event['params'].get('move', 0.0))
    if x1 is not None and y1 is not None and hasattr(world, 'circles'):
        # Omskolningen är en cirkel: kursens position, en bred radie, och massa
        # lika med studietiden. Se docs/utbildningsmodell.md.
        sim = world.cfg_reader.config.get('simulation', {})
        dur_days = float(event['params'].get('duration_days', 365.0))
        p = world.competence_params()
        rho2 = float(sim.get('competence', {}).get('retraining_radius2', 0.25))
        world.circles.add(idx, f"RETRAIN:{event['time']:.0f}", float(x1), float(y1),
                          rho2, p.a * dur_days / 365.25)
        world._write_competence_summary()
        if 'w_res' in ind.columns:
            rho = float(sim.get('rho_reservation', 0.7))
            ind.at[idx, 'w_res'] = rho * float(ind.at[idx, 'w_res'])
    _become_unemployed(world, idx)
    world.event_logger.log_event(world, event, extra={
        'event_detail': 'education_finished',
        'move': round(float(event['params'].get('move', 0.0)), 4)})

def handle_start_internal_training(event, world):
    """Intern träning = extra exponering på den aktiva cirkeln. Ett halvårs
    massa läggs till direkt; skärpningen sköter månadssteget."""
    idx = event['agent_id']
    if hasattr(world, 'circles') and world._active_key[idx] >= 0:
        k = int(world._active_key[idx])
        j = np.flatnonzero(world.circles.key[idx] == k)
        if j.size:
            extra_years = float(event['params'].get('training_years', 0.5))
            world.circles.mass[idx, j[0]] += world.competence_params().a * extra_years
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
    # Positionsdelta utgått: kompetenscirklarna sköter detta (steg 2 ersätter
    # händelsen med sökning inom egen arbetsgivare).
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
    pass
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


def _wage_flow_quantiles(world):
    """Tre tal per månad: median och kvartiler i log lön bland anställda.

    Fem årspunkter räcker inte för att se om fördelningen är stationär. Tre
    float per månad kostar ingenting och gör drift synlig i tidsserien.
    """
    st = _wage_stock_stats(world)
    return {k: st[k] for k in ("stock_w_p10", "stock_w_p50", "stock_w_p90")
            if k in st}


def handle_new_month(event, world):
    from core.statistics.basic_stats import analyze_world
    year = event['params'].get('year')
    month = event['params'].get('month')
    n_posted = world.post_vacancies_batch(event['time'])
    world.evolve_competence(1.0 / 12.0)
    stats = analyze_world(world)

    n_individuals = stats['total_individuals']
    n_jobs = stats['total_jobs']
    n_employers = stats['total_employers']
    employed = stats['employed_individuals']
    unemployed = stats['unemployed_individuals']
    unmatched_jobs = stats['unmatched_jobs']
    not_in_labour_force = stats['individuals_not_in_labour_force']
    m_extra = {
        "month": month,
        "employed": employed,
        "unemployed": unemployed,
        "unmatched_jobs": unmatched_jobs,
        "not_in_labour_force": not_in_labour_force,
        "active_jobs": n_jobs,
        "posted": n_posted,
    }
    m_extra.update(_wage_flow_quantiles(world))
    world.event_logger.log_event(world, event, extra=m_extra, print_line=True)
    # Reset match-counter
    world.n_matched_in_month = 0

def _wage_stock_stats(world):
    """Årligt tvärsnitt av löneBESTÅNDET, inte av flödet.

    Övergångstabellen mäter lönen VID ANSTÄLLNING. SCB:s lönestruktur-
    statistik mäter beståndet, med september som referensperiod, så ett
    årligt tvärsnitt är direkt jämförbart med källan medan tolv per år inte
    ger mer information om just den jämförelsen -- bara tolv gånger kostnaden
    på tiotusen löner per snapshot.

    Mätningen ligger i new_year-hanteraren och inte som egen händelsetyp. Med
    en wage_snapshot i kön skulle den konkurrera med den kommande årliga
    lönerevisionen om ordningen inom samma tidpunkt, och det skulle bli oklart
    om beståndet mäts före eller efter revisionen. Här är ordningen explicit i
    koden, och snapshot ska tas FÖRE revisionen: då blir revisionen en
    observerbar hoppfunktion mellan två tvärsnitt, och fördelningen av
    lönetillväxt per år kan jämföras med märket.

    ETT GRATIS TEST SÅ LÄNGE. Lönen ändras aldrig efter anställning, så
    beståndet är en blandning över anställningsårgångar under en
    tidsinvariant regel: stock och flöde ska vara nästan IDENTISKA. Skiljer de
    sig materiellt finns ett fel någonstans. När revisionen kommer ska de
    tvärtom divergera, med beståndet förskjutet uppåt och bredare, och
    skillnaden blir måttet på hur mycket av lönespridningen som är karriär och
    hur mycket som är matchning.
    """
    ind = world.individuals
    if 'status' not in ind.columns:
        return {}
    if 'w_neg' not in ind.columns:
        # Tom eller minimal ram (tester) är ett legitimt fall. Men finns det
        # ANSTÄLLDA utan lönekolumn är det ett programmeringsfel som annars
        # göms: det var precis så beståndsmåttet och lönerevisionen kunde vara
        # avstängda under fem hela körningar utan att något larmade.
        if (ind['status'] == 'employed').any():
            raise KeyError(
                "individuals har anställda men saknar kolumnen w_neg: "
                "beståndets tvärsnitt kan inte mätas. Kolumnen skapas i "
                "World._seed_wages_for_matched och fylls av handle_start_job.")
        return {}
    w = pd.to_numeric(ind.loc[ind['status'] == 'employed', 'w_neg'],
                      errors='coerce').dropna()
    w = w[w > 0]
    if len(w) < 10:
        return {}
    lg = np.log(w.to_numpy())
    q = np.quantile(w.to_numpy(), [0.10, 0.25, 0.50, 0.75, 0.90])
    return {
        "stock_n": int(len(w)),
        "stock_w_p10": round(float(q[0]), 4),
        "stock_w_p25": round(float(q[1]), 4),
        "stock_w_p50": round(float(q[2]), 4),
        "stock_w_p75": round(float(q[3]), 4),
        "stock_w_p90": round(float(q[4]), 4),
        "stock_w_p90p10": round(float(q[4] / q[0]), 4),
        "stock_sd_log_w": round(float(np.std(lg)), 4),
    }


def _apply_wage_revision(world, t_now):
    """Årlig lönerevision: procentuell ökning på befintlig lön.

    VÄGBEROENDE, INTE NIVÅBESTÄMD. Alternativet vore att räkna om lönen ur
    w = Pi_j * p**theta med aktuellt q, alltså dra den mot en nivå oavsett var
    den varit. Svensk lönebildning fungerar inte så: ökningar ges i procent av
    befintlig lön, och prestation belönas som SPRIDNING KRING MÄRKET. Två
    personer med samma q kan därför tjäna olika för att de haft olika
    revisionsutfall, och det vägberoendet är vad som skapar spridning över en
    karriär:

        log w(t+1) = log w(t) + log(1 + g)

    Summan av många små multiplikativa påslag är approximativt normal, så
    beståndet blir lognormalt av en ANDRA oberoende orsak utöver den som redan
    finns i q:s produktstruktur.

    DEN INDIVIDUELLA DELEN hämtas ur något modellen redan vet -- hur mycket
    konkurrenskraften vuxit sedan förra revisionen -- och inte ur en fri
    slumpterm. Den som utvecklas i sitt jobb får mer.

    MÄRKET FALLER UT UR ALLA KVOTER. Räknas både löner och Pi upp med märket
    mäts allt realt relativt normen, och märket behöver ingen indexering av
    Pi: w * (1+g)/(1+märke). Men det spelar ändå roll, genom avkortningen.
    Nominella löner sänks inte i Sverige, alltså g >= 0 -- och eftersom märket
    ligger över noll blir nollutfall ovanliga utan att vara omöjliga, precis
    som i verkligheten. Realt kan lönen däremot falla, för den som får mindre
    än märket. Nominell stelhet, real flexibilitet.

    Anropas FRÅN handle_new_year, efter beståndets tvärsnitt. Ordningen är
    därmed explicit i koden: en egen händelsetyp i kön skulle konkurrera med
    snapshot om ordningen inom samma tidpunkt, och då vore det oklart om
    beståndet mäts före eller efter revisionen. Före är det som gör revisionen
    till en observerbar hoppfunktion mellan två tvärsnitt.
    """
    cfg = (world.cfg_reader.config.get('simulation', {})
           .get('wage_revision', {}) or {})
    if not cfg.get('enabled', True):
        return {}
    ind = world.individuals
    if not hasattr(world, 'circles'):
        return {}                       # syntetisk värld utan cirklar
    if 'w_neg' not in ind.columns:
        if (ind['status'] == 'employed').any():
            raise KeyError(
                "individuals har anställda men saknar kolumnen w_neg: "
                "lönerevisionen kan inte köras. En tyst retur här dolde att "
                "revisionen aldrig kördes under fem hela körningar.")
        return {}
    mask = (ind['status'] == 'employed') & ind['w_neg'].notna() & ind['job_id'].notna()
    idxs = ind.index[mask]
    if not len(idxs):
        return {}

    markup = float(cfg.get('markup', 0.025))
    beta_q = float(cfg.get('beta_q', 0.10))
    pos_of = world.job_index()
    jobs = world.jobs
    cp = world.competence_params()
    jx = jobs['x_occ'].to_numpy(dtype=float)
    jy = jobs['y_occ'].to_numpy(dtype=float)
    jr = jobs['r_o'].to_numpy(dtype=float)

    gs = []
    for i in idxs:
        pos = pos_of.get(ind.at[i, 'job_id'])
        if pos is None:
            continue
        q_now = float(world.circles.competitiveness(
            i, jx[pos:pos + 1], jy[pos:pos + 1], jr[pos:pos + 1], cp)[0])
        q_prev = ind.at[i, 'q_last'] if 'q_last' in ind.columns else np.nan
        try:
            q_prev = float(q_prev)
        except (TypeError, ValueError):
            q_prev = np.nan
        d = 0.0
        if np.isfinite(q_prev) and q_prev > 0 and q_now > 0:
            d = float(np.log(q_now / q_prev))
        g = max(0.0, markup + beta_q * d)          # ingen nominell sänkning
        ind.at[i, 'w_neg'] = float(ind.at[i, 'w_neg']) * (1.0 + g) / (1.0 + markup)
        if q_now > 0:
            ind.at[i, 'q_last'] = q_now
        gs.append(g)

    if not gs:
        return {}
    g = np.asarray(gs, dtype=float)
    return {
        "revision_n": int(g.size),
        "revision_g_mean": round(float(g.mean()), 5),
        "revision_g_p10": round(float(np.quantile(g, 0.10)), 5),
        "revision_g_p90": round(float(np.quantile(g, 0.90)), 5),
        "revision_share_zero": round(float((g <= 1e-12).mean()), 4),
    }


def handle_new_year(event, world):
    from core.statistics.basic_stats import analyze_world
    year = event['params'].get('year')
    stats = analyze_world(world)
    employed = stats['employed_individuals']
    unemployed = stats['unemployed_individuals']
    unmatched_jobs = stats['unmatched_jobs']
    not_in_labour_force = stats['individuals_not_in_labour_force']
    extra = {
        "year": year,
        "employed": employed,
        "unemployed": unemployed,
        "unmatched_jobs": unmatched_jobs,
        "not_in_labour_force": not_in_labour_force,
        "active_jobs": stats['total_jobs'],
    }
    extra.update(_wage_stock_stats(world))          # FÖRE revisionen
    extra.update(_apply_wage_revision(world, float(event['time'])))
    world.event_logger.log_event(world, event, extra=extra, print_line=True)

RULE_SWITCH = {
    "quit_job": handle_quit_job,
    "start_job": handle_start_job,
    "start_job_search": handle_start_job_search,
    "close_vacancy": handle_close_vacancy,
    "start_education": handle_start_education,
    "end_education": handle_end_education,
    "start_internal_training": handle_start_internal_training,
    "internal_job_change": handle_internal_job_change,
    "career_break": handle_career_break,
    "destroy_job": handle_destroy_job,
    "new_month": handle_new_month,
    "new_year": handle_new_year,
}
