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
import pandas as pd


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
        commute_decay_km=sim.get('commute_decay_km', None),
        min_surplus=sim.get('min_surplus', 0.0),
        choice_scale=sim.get('choice_scale', 0.05),
        requirement_k=float(sim.get('requirement_k', 2.0)),
        bargaining=({k: v for k, v in brg.items() if k != 'enabled'}
                    if brg.get('enabled', True) else None),
    )


def _with_current_reservation(world, idx, rad, st, cfg):
    """Individens jämförelsepunkt just nu, som en rad med w_res satt.

    RESERVATIONEN ÄR NUVARANDE SITUATION, inte kolumnen w_res. Den anställdes
    alternativ är att stanna: lönen hon har minus dess pendling, plus en
    bytesfriktion. Utan friktionen byter hon för en krona; med en för hög
    byter ingen. Uttryckt som andel av nuvarande lön biter den lika på alla
    nivåer. För den arbetslösa är kolumnen w_res rätt, och likaså för en
    person i inpendlingsreservoaren (status extern, docs/omgivning.md): hennes
    alternativ i omgivningen modelleras inte, så hon har anspråket ρ·Π som en
    invånare som söker vid start. Att låta henne jämföra som en anställd med
    yrkets fulla pris gjorde att ingen i reservoaren någonsin sökte: med 5
    procents friktion och 40 km pendling från Rättvik fanns inget positivt
    överskott.

    EGEN FUNKTION sedan 0095, eftersom samma jämförelse nu görs på två
    ställen: när hon söker och när ett erbjudande kommer. Två kopior av den
    här formeln vore den sjunde gången i serien som två kodvägar för samma
    sak glidit isär.
    """
    if st != 'employed':
        return rad
    sim = world.cfg_reader.config.get('simulation', {})
    frik = float(sim.get('switching_cost_share', 0.05))
    w_nu = rad.get('w_neg')
    if w_nu is None or pd.isna(w_nu):
        return rad
    pos = world.job_index().get(rad.get('job_id'))
    km_nu = 0.0
    if pos is not None and {'x', 'y'} <= set(world.jobs.columns):
        km_nu = float(np.hypot(world.jobs['x'].iat[pos] - float(rad['x']),
                               world.jobs['y'].iat[pos] - float(rad['y']))) / 1000.0
    rad = rad.copy()
    rad['w_res'] = float(w_nu) * (1.0 + frik) - cfg['commute_cost_per_km'] * km_nu
    return rad


def current_surplus(world, idx, w_off, commute_km):
    """Överskottet av ett erbjudande MOT HENNES LÄGE NU: S = w - c*km - w_res,
    samma uttryck som search_once använder, med reservationen ur
    _with_current_reservation."""
    ind = world.individuals
    st = world.get_ind(idx, 'status') if 'status' in ind.columns else 'unemployed'
    cfg = search_config(world)
    from core.event_handlers import ar_extern
    if ar_extern(world, idx):
        # Samma regel som i sökningen (O3c): inpendlaren betalar ingen
        # pendlingskostnad. Utan raden prövades erbjudandet vid stängningen med
        # kostnaden för 40-60 km och avböjdes -- 3 vunna av 3 320 ansökningar
        # till Älvdalen.
        cfg = dict(cfg, commute_cost_per_km=0.0)
    rad = _with_current_reservation(world, idx, world.ind_row(idx), st, cfg)
    w_res = float(rad.get('w_res') or 0.0)
    return float(w_off) - float(cfg['commute_cost_per_km']) * float(commute_km) - w_res


def relevansfordelning(world, idx, min_antal=5):
    """Lönefördelningen över individens relevansmängd, som median och log-sd.

    ANSPRÅKET MÄTS I PERCENTIL, INTE I KRONOR, och percentilen ska läsas i
    HENNES fördelning: de positioner q släpper igenom, viktade med
    mötessannolikheten. Det är individens perspektiv -- hon tar de bästa X
    procenten av vad hon ser, och X faller med tiden.

    MÄNGDEN FÅR INTE VARA DAGENS SÖKOMGÅNG. Vore w_res kvantilen av det hon
    möter just nu accepterar hon alltid något så snart hon möter tillräckligt
    många: tröskeln följer med draget, och en reservationslön som aldrig kan
    leda till avslag är ingen reservationslön. Fördelningen beräknas därför
    över hela vakansstocken en gång per arbetslöshetsperiod, inte per sökning.

    TVÅ TAL RÄCKER. Lognormal är en rimlig approximation för löner -- rapporten
    kontrollerar den redan via P90/P50 mot P50/P10 -- så medianen och
    log-spridningen bär fördelningen, och kvantilen blir
    med * exp(sd * z(p)). Att lagra hela fördelningen per individ vore två
    kolumner mot hundratals utan att svaret blev bättre.

    Returnerar (median, log_sd, n) eller None om mängden är för tunn. En
    fördelning skattad på färre än min_antal positioner är brus, och då är
    den personrelativa sigmoiden från 0151 det ärligare fallbacket.
    """
    from core.occupations.utils import negotiated_wage
    from core.occupations.requirement import productivity

    cand = np.flatnonzero(world.vacant_mask())
    if cand.size < min_antal:
        return None
    A = world.job_arrays()
    cfg = search_config(world)
    rad = world.ind_row(idx)

    jx, jy = A["x_occ"][cand], A["y_occ"][cand]
    if hasattr(world, "circles"):
        q = world.circles.competitiveness(idx, jx, jy, A["r_o"][cand],
                                          world.competence_params())
    else:
        ix, iy = float(rad["x_occ"]), float(rad["y_occ"])
        ri = float(rad.get("r_i", 0.0) or 0.0)
        d2 = (jx - ix) ** 2 + (jy - iy) ** 2
        sig2 = np.maximum((float(cfg.get("sigma_gamma", 1.0)) ** 2)
                          * (A["r_o"][cand] ** 2 + ri ** 2), 1e-9)
        q = np.exp(-0.5 * d2 / sig2)

    km = np.hypot(A["x"][cand] - float(rad["x"]),
                  A["y"][cand] - float(rad["y"])) / 1000.0
    vikt = np.minimum(1.0, q)
    d0 = cfg.get("commute_decay_km")
    if d0:
        vikt = vikt * np.exp(-km / float(d0))

    pkt = productivity(q, A["r_req"][cand], k=float(cfg.get("requirement_k", 2.0)))
    brg = cfg.get("bargaining")
    if brg:
        # w_res = 0 här: vi vill ha positionens lönebud oberoende av hennes
        # nuvarande anspråk, annars definieras anspråket av sig självt.
        w_off = negotiated_wage(pkt, A["wage"][cand], 0.0, **brg)
    else:
        w_off = A["wage"][cand]

    ok = np.isfinite(w_off) & (w_off > 0) & (vikt > 0)
    if ok.sum() < min_antal:
        return None
    lw = np.log(w_off[ok])
    v = vikt[ok] / vikt[ok].sum()
    mu = float(np.dot(v, lw))
    var = float(np.dot(v, (lw - mu) ** 2))
    if not np.isfinite(var) or var <= 0:
        return None
    return float(np.exp(mu)), float(np.sqrt(var)), int(ok.sum())


def apply_once(world, idx, t_now):
    """En sökomgång för en arbetslös: möte, val, ANSÖKAN.

    Returnerar (job_id, w_neg, q, surplus, commute_km) eller (None,)*5.

    Ingen omschemaläggning och ingen händelseloggning: det hör till
    handle_start_job_search, som ramar in den här funktionen. Uppstarten
    behöver varken.
    """
    from core.occupations.utils import search_once

    ind = world.individuals
    st = world.get_ind(idx, 'status') if 'status' in ind.columns else 'unemployed'
    # extern: inpendlingsreservoaren söker regionens vakanser (docs/omgivning.md)
    if st not in ('employed', 'unemployed', 'extern'):
        return (None,) * 5
    # Den som redan sagt upp sig för ett annat jobb söker inte vidare
    if st == 'employed' and 'notice_job_id' in ind.columns \
            and pd.notna(world.get_ind(idx, 'notice_job_id')):
        return (None,) * 5

    cfg = search_config(world)
    kandidater = world.vacant_mask()
    from core.event_handlers import ar_extern
    if ar_extern(world, idx):
        # INPENDLARE OCH RESERVOAR (docs/omgivning.md, O3c): bara vakanser i
        # arbetskommunen, och utan avståndsdämpning och pendlingskostnad --
        # arbetskommunen är dragen ur pendlingsmatrisen, som redan bär hur
        # långt folk pendlar (samma princip som för utpendlingen, O4b).
        ak = world.get_ind(idx, 'arbetskommun') if 'arbetskommun' in ind.columns else None
        if ak is not None and pd.notna(ak):
            kandidater = kandidater & (world.jobb_kommun() == str(ak).zfill(4))
        cfg = dict(cfg, commute_cost_per_km=0.0, commute_decay_km=None)
    rad = _with_current_reservation(world, idx, world.ind_row(idx), st, cfg)
    job_pos, surplus, w_neg, q_hire, km = search_once(
        rad, world.jobs,
        np.flatnonzero(kandidater),
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

    # Kolumnaccess, inte radkopia: jobs.iloc[pos][col] bygger en Series av
    # hela raden och kostar 54 mikrosekunder mot 11 för .iat på kolumnen.
    job_id = world.jobs['job_id'].iat[job_pos]
    # LÖNEN SKRIVS INTE HÄR. w_neg är individens FAKTISKA lön, och den sätts av
    # handle_start_job när anställningen sker. Att skriva den vid ansökan var
    # en rest från när bara arbetslösa sökte -- skadlig men osynlig, eftersom
    # en arbetslös inte har någon lön att förstöra.
    #
    # Med sökning från anställning (0079) blev den förödande: reservationen
    # ovan läser w_neg som "nuvarande lön", så snart hon sökt ETT jobb var
    # hennes jämförelsepunkt det jobbets erbjudna lön i stället för hennes
    # egen. Spärrhaken i stegen försvann. Utfallet: 46.6 procent jobbyten per
    # år mot svenska tio, med en medianlönevinst per byte på exakt noll -- hon
    # bytte till det hon nyss jämfört sig med.
    #
    # Den erbjudna lönen bärs i ansökan (file_application nedan) och når
    # anställningen den vägen.
    world.file_application(job_id, idx, float(t_now),
                           q=q_hire, w_neg=w_neg, surplus=surplus,
                           commute_km=km)
    return job_id, w_neg, q_hire, surplus, km


def externt_erbjudande(world, idx, t_now, rng):
    """Ett erbjudande om jobb utanför regionen (docs/omgivning.md, O4), eller
    None.

    Vid en andel utpendling_erbjudande_andel av invånarnas sökningar kommer
    också ett erbjudande utifrån. Destinationen dras ur invånarens kommuns
    utpendling i pendlingsmatrisen, bransch och yrke ur destinationens
    jobbfördelning i TAB4436, platsen är en DeSO i destinationen dragen med
    befolkningen. Erbjudandet värderas som ett lokalt i search_once, men utan
    avstånd: mötet med sannolikheten min(1, q), produktiviteten
    ur q och kravet, den förhandlade lönen ur fältets pris, och överskottet
    mot hennes läge nu, utan pendlingskostnad (se nedan). Arbetsgivarens urval modelleras inte: omgivningen är
    exogen, och den som får ett lönsamt erbjudande får jobbet. Mötet dämpas
    inte med avståndet: destinationen bär det redan.

    Bara invånare, anställda eller arbetslösa, utan löfte och utan pågående
    uppsägning. Kommuner utan utpendling i matrisen får inga erbjudanden."""
    ind = world.individuals
    if getattr(world, 'conn', None) is None:          # syntetisk värld utan databas
        return None
    from core.event_handlers import ar_extern
    if ar_extern(world, idx):
        return None
    st = world.get_ind(idx, 'status')
    if st not in ('employed', 'unemployed'):
        return None
    for kol in ('accepted_job_id', 'notice_job_id'):
        if kol in ind.columns and pd.notna(world.get_ind(idx, kol)):
            return None
    sim = world.cfg_reader.config.get('simulation', {})
    if rng.random() >= float(sim.get('utpendling_erbjudande_andel', 0.1)):
        return None
    om = world.omgivning()
    hem = str(ind.at[idx, 'municipal_code']).zfill(4)
    if om.andel_utpendling(hem) <= 0:
        return None
    dest = om.dra_destination(hem, rng)
    profil = world.kommunprofil()
    bransch, ssyk = profil.dra_jobb(dest, rng)
    onet = profil.onet(ssyk, rng)
    geom = world._geom_lookup(onet)
    if geom is None:
        return None
    x, y = om.dra_plats(dest, rng)
    km = float(np.hypot(x - float(ind.at[idx, 'x']), y - float(ind.at[idx, 'y']))) / 1000.0
    if hasattr(world, 'circles'):
        q = float(world.circles.competitiveness(idx, [geom['x_occ']], [geom['y_occ']],
                                                [geom['r_o']], world.competence_params())[0])
    else:
        q = 1.0
    cfg = search_config(world)
    # INGEN AVSTÅNDSDÄMPNING I MÖTET. Destinationen är redan dragen ur
    # pendlingsmatrisen, som bär hur långt folk faktiskt pendlar; att dämpa
    # med exp(-km / commute_decay_km) därtill räknade avståndet två gånger.
    # Utpendlingen från Mora har medianen 76 km, och dämpningen gav mötet
    # sannolikheten 0,08 i medel -- ingen utpendlare på två år.
    p_mote = min(1.0, q)
    if rng.random() >= p_mote:
        return None
    from core.occupations.requirement import productivity
    from core.occupations.utils import negotiated_wage
    rad = _with_current_reservation(world, idx, world.ind_row(idx), st, cfg)
    w_res = float(rad.get('w_res') or 0.0)
    r_req = geom.get('r_req')
    pkt = productivity(np.array([q]), np.array([0.0 if r_req is None or np.isnan(r_req) else r_req]),
                       k=cfg['requirement_k'])
    w_field = np.array([float(geom['wage'])])
    w_off = (float(negotiated_wage(pkt, w_field, w_res, **cfg['bargaining'])[0])
             if cfg['bargaining'] is not None else float(w_field[0]))
    if not np.isfinite(w_off):
        return None
    # INGEN PENDLINGSKOSTNAD för ett externt erbjudande (avgjort 2026-09-18).
    # Destinationen är dragen ur pendlingsmatrisen, som är observerat
    # beteende: hur folk faktiskt pendlar, med bil, buss eller tåg, dagligen
    # eller ett par dagar i veckan med arbete hemifrån resten. Modellens
    # kostnad, 0,005 per km och kalibrerad för lokal pendling, gjorde de
    # längre arbetsresorna olönsamma: utpendlingen från Mora ligger i median
    # 76 km bort, en fjärdedel över 215 km, och de antagna jobben hamnade på
    # 43 km med 176 utpendlare mot 1 767. Att prissätta färdsätt och
    # distansarbete vore en egen modell av något som datan redan bär.
    S = w_off - w_res
    if S <= cfg['min_surplus']:
        return None
    return {"kommun": dest, "bransch": bransch, "ssyk": ssyk, "onet": onet,
            "x": x, "y": y, "q": q, "w_neg": w_off, "surplus": S, "km": km}


def anta_externt(world, idx, t_now, erbj, omedelbart=False):
    """Hon tackar ja till ett externt erbjudande: jobbet skapas, löftet
    skrivs, och tillträdet sker efter samma fördröjning som för ett lokalt
    jobb -- med uppsägningstid om hon har ett jobb att säga upp. Vid
    uppstarten sker tillträdet direkt, som för uppstartens lokala
    anställningar. Returnerar jobbets id."""
    from core import event_handlers as eh
    jid = world.skapa_externt_jobb(t_now, erbj["kommun"], erbj["bransch"], erbj["ssyk"],
                                   erbj["onet"], erbj["x"], erbj["y"])
    ind = world.individuals
    params = {"job_id": jid, "w_neg": erbj["w_neg"], "q_hire": erbj["q"],
              "commute_km": erbj["km"], "n_applicants": 0, "extern": True}
    if omedelbart:
        params["bootstrap"] = True
        eh.handle_start_job({"time": float(t_now), "agent_id": idx,
                             "event_type": "start_job", "params": params}, world)
        return jid
    ind.at[idx, 'accepted_job_id'] = jid
    if world.get_ind(idx, 'status') == 'employed' and pd.notna(world.get_ind(idx, 'job_id')):
        ind.at[idx, 'notice_job_id'] = jid
    lag = eh.start_delay_days(world, idx)
    world._push_event({"time": float(t_now) + lag, "agent_id": idx,
                       "event_type": "start_job", "params": params})
    return jid


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
                # MÄRKT. Uppstartens anställningar går genom handle_start_job
                # och hamnar därför i transitions -- 10 165 av 21 594 i en
                # femårskörning. De räknades som yrkesövergångar, eftersom
                # individens seedade onet_code skiljer sig från jobbets, och
                # blåste upp n_cps_sample från 8 285 till 17 900: hälften av
                # valideringsunderlaget var att folk fick sitt FÖRSTA jobb.
                # De ska synas i loggen -- de är verkliga anställningar med
                # löner som hör till beståndet -- men de är inte mobilitet.
                p = dict(ev.get("params", {}))
                p["bootstrap"] = True
                starter.append(dict(ev, time=float(t_now), params=p))
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

    n_start = int((ind['status'] == 'unemployed').sum())
    totalt, omgångar, per_omgång = 0, 0, []
    par = []
    tomma = 0

    while omgångar < max_omg:
        # KÖN BYGGS OM VARJE OMGÅNG ur dem som fortfarande är arbetslösa. Ett
        # första försök delade upp en fast kö en gång och lade aldrig tillbaka
        # den som inte fick jobb: med 11 502 arbetslösa och 10 754 lediga jobb
        # rymdes hela kön i första omgången (2.4 x 10 754 = 25 800), loopen
        # avslutades efter EN omgång, och 4 500 stod kvar arbetslösa bredvid
        # 3 800 lediga positioner -- 60.6 procent matchade mot en jämvikt
        # kring 86. Hela femårskörningen blev då en transient: anställningarna
        # fördubblades till 21 200 och n_cps_sample till 17 700, alltså var
        # halva valideringsunderlaget uppstartsdynamik.
        #
        # I körningen får den som misslyckas en ny sökning var 28:e dag. Här
        # får hon en ny omgång. Det är samma sak.
        # INPENDLARNA PÅ PLATS (docs/omgivning.md, O3b). En delmängd av
        # inpendlingsreservoaren, lika stor som matrisens inpendlingsstock,
        # söker med de arbetslösa invånarna; resten av reservoaren söker
        # först under körningen. Utan dem fyllde invånarna inpendlarnas jobb.
        i_ko = ind['status'] == 'unemployed'
        if 'extern_start' in ind.columns:
            i_ko = i_ko | ((ind['status'] == 'extern')
                           & ind['extern_start'].fillna(False).astype(bool))
        kö = list(ind.index[i_ko])
        if not kö:
            break
        n_vak = int(world.vacant_mask().sum())
        if n_vak == 0:
            break
        rng.shuffle(kö)
        n = max(1, min(len(kö), int(round(per_vak * n_vak))))
        omgång = kö[:n]

        externa = 0
        for i in omgång:
            # Utpendlarna på plats (docs/omgivning.md, O4): en invånare kan få
            # ett erbjudande utifrån också i uppstarten, och tillträder då
            # direkt.
            erbj = externt_erbjudande(world, i, t_now, np.random)
            if erbj is not None:
                anta_externt(world, i, t_now, erbj, omedelbart=True)
                externa += 1
                continue
            apply_once(world, i, t_now)
        före = dict(zip(ind.index, ind['job_id']))
        fyllda = close_all_windows(world, t_now, immediate=True)
        for i in omgång:
            j = world.get_ind(i, 'job_id')
            if j is not None and str(j) != 'nan' and före.get(i) != j:
                par.append({"individual_id": world.get_ind(i, 'individual_id')
                            if 'individual_id' in ind.columns else i,
                            "job_id": j,
                            "utility": float(world.get_ind(i, 'w_neg'))
                            if 'w_neg' in ind.columns
                            and world.get_ind(i, 'w_neg') == world.get_ind(i, 'w_neg') else 0.0})
        omgångar += 1
        # De externa räknas med: en omgång där någon tog ett jobb utanför
        # regionen är inte tom.
        fyllda += externa
        totalt += fyllda
        per_omgång.append(fyllda)

        # Avslutas när marknaden är uttömd, inte när kön är slut: två tomma
        # omgångar i rad betyder att de kvarvarande arbetslösa och de
        # kvarvarande positionerna inte kan matchas under gällande villkor.
        tomma = tomma + 1 if fyllda == 0 else 0
        if tomma >= 2:
            break

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
