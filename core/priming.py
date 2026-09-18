"""Primingen av startpopulationen, steg 6a-i (docs/utbildningsmodell.md,
"Två situationer").

Startpopulationen ska se ut som en befintlig arbetskraft under startåret, utan
en inkörningsperiod. Före primingen drogs ett startyrke oberoende av jobben, och
tjänstetidens massa lades där; uppstartsmatchningen placerade sedan 94 procent
i ett annat yrke (12 165 av 12 962 i baslinjens frö 1). Erfarenheten låg alltså
där hon inte arbetade och suddades ut, medan en tom cirkel byggdes där hon
arbetade.

ORDNINGEN (avgjord 2026-09-18). Startyrkets cirkel guidar uppstartsmatchningen
-- den avgör vart i uppgiftsrummet hon söker. Efter placeringen flyttas
erfarenheten: den som fått ett jobb får jobbets cirkel med tjänstetidens massa
och vilaradien, och startyrkets cirkel tas bort. Den som är arbetslös vid start
behåller startyrket som sitt senaste yrke; cirkeln läcker och suddas ut som
efter en arbetslöshetstid, dragen exponentiellt, och arbetslöshetens klocka
ställs bakåt lika mycket, så att anspråk och benägenheter stämmer från början.

Reservoaren i omgivningen som inte fått jobb lämnas; hemyrkets cirkel är hennes
pågående arbete.

UTBILDNINGEN (6a-ii, prima_utbildningen). Nivå och inriktning dras givet yrket,
åldern ur den rakade fördelningen (core/utbildningsfordelning.py), och
utbildningscirkeln läggs där utbildningen pekade när hon var ny: på ett yrke
draget ur P(yrke | nivå, inriktning) för 25-29-åringar -- samma dragning som
inträdaren får (6b). Beslut 5 i utbildningsmodell.md, alternativ (b), avgjort
2026-09-18. Tidigare drogs nivån ur kommunens nivåfördelning oberoende av
yrket, inriktningen fanns inte, och cirkeln låg på det nuvarande yrket.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _ar_arbetscirkel(nyckel: str) -> bool:
    return not str(nyckel).startswith(("EDU:", "RETRAIN:"))


def prima_startpopulationen(world, t_now=0.0, rng=None):
    if not hasattr(world, "circles"):
        return {}
    rng = rng if rng is not None else np.random.default_rng()
    c = world.circles
    p = world.competence_params()
    ind = world.individuals
    jobs = world.jobs
    ji = world.job_index()
    m_sat = p.a / p.lam
    sim = world.cfg_reader.config.get("simulation", {})
    medel = float(sim.get("start_arbetsloshet_medel_dagar", 115.0))
    status = ind["status"].to_numpy()
    tenure = (ind["tenure_years"].to_numpy(float) if "tenure_years" in ind.columns
              else np.zeros(len(ind)))
    flyttade = arbetslosa = 0
    for i in range(len(ind)):
        if status[i] == "employed":
            j = int(world._active_slot[i])
            pos = ji.get(ind.at[i, "job_id"])
            if j < 0 or pos is None:
                continue
            t = tenure[i] if np.isfinite(tenure[i]) else 0.0
            c.mass[i, j] = m_sat * (1.0 - np.exp(-p.lam * max(t, 0.0)))
            c.rho2[i, j] = c.rho2_home[i, j]
            for k in np.flatnonzero(c.key[i] >= 0):
                if k != j and _ar_arbetscirkel(c.key_names[c.key[i, k]]):
                    c.remove(i, k)
            flyttade += 1
        elif status[i] == "unemployed":
            kod = ind.at[i, "onet_code"] if "onet_code" in ind.columns else None
            j = c.latest(i, str(kod)) if kod is not None else -1
            d = float(rng.exponential(medel))
            if j >= 0:
                ar = d / 365.25
                c.mass[i, j] *= np.exp(-p.lam * ar)
                tak = (p.diffusion_max_ratio * c.rho2_home[i, j]
                       if p.diffusion_max_ratio and p.diffusion_max_ratio > 0 else 4.0)
                c.rho2[i, j] = min(c.rho2[i, j] + 2.0 * p.D * ar, tak, 4.0)
            if "unemployed_since" in ind.columns:
                ind.at[i, "unemployed_since"] = float(t_now) - d
            arbetslosa += 1
    utb = prima_utbildningen(world, rng)
    world._write_competence_summary()
    return {"priming_flyttade": flyttade, "priming_arbetslosa": arbetslosa, **utb}


# ---------------------------------------------------------------------------
# 6a-ii: utbildningen givet yrket
# ---------------------------------------------------------------------------
OKAND_NIVA, OKAND_INRIKTNING, ALLMAN = "US", "9", "0"
DRAGNINGSKLASS = "25-29"            # inträdarens ålder: nära examen, före driften


from functools import lru_cache


@lru_cache(maxsize=8)
def _klassgranser(klasser):
    return sorted((_aldersgrans(k), k) for k in klasser)


def _aldersgrans(klass):
    """"065-69" -> (65, 69)."""
    lo, hi = str(klass).split("-")
    return int(lo), int(hi)


def _aldersklass(alder, klasser):
    """Åldersklassen i tabellen som innehåller åldern; under den lägsta den
    lägsta, över den högsta den högsta."""
    gr = _klassgranser(tuple(klasser))
    a = int(np.floor(alder))
    for (lo, hi), k in gr:
        if lo <= a <= hi:
            return k
    return gr[0][1] if a < gr[0][0][0] else gr[-1][1]


NIVAER = ("1", "2", "3", "4", "5", "6", "7")
INRIKTNINGAR = ("0", "1", "2", "3", "4", "5", "6", "7", "8")
CELLER = [(l, f) for l in NIVAER for f in INRIKTNINGAR]
NIVAGRUPP = {"1": "21", "2": "21", "3": "3", "4": "4", "5": "5", "6": "61", "7": "61"}
GRUPPER = ("21", "3", "4", "5", "61")
_CELLGRUPP = np.array([GRUPPER.index(NIVAGRUPP[l]) for l, _ in CELLER])
KOMMUNENS_ALDER = (20, 65)           # TAB6666


class Utbildningsdragning:
    """Dragningarna för 6a-ii och 6b ur den rakade fördelningen.

    KÖNET SUMMERAS: individerna bär inget kön, så fördelningen tas över båda.
    Det är ett modellval, inte en reserv; när individerna får kön ska det in
    här.

    OKÄND NIVÅ ELLER INRIKTNING dras inte (öppet beslut 4 i
    utbildningsmodell.md). Hon får nivå och inriktning bland de kända, i
    proportion; att ge de okända bara grundskola hade underskattat dem
    systematiskt."""

    def __init__(self, conn):
        from core.utbildningsfordelning import bygg_fordelning
        d, _ = bygg_fordelning(conn)
        d = d.groupby(["age_class", "ssyk_code", "level", "field"], as_index=False).employed.sum()
        self.klasser = sorted(d.age_class.unique())
        kand = d[d.level.isin(NIVAER) & d.field.isin(INRIKTNINGAR)]
        cell = {c: k for k, c in enumerate(CELLER)}
        self._lf = {}
        for (k, o), g in kand.groupby(["age_class", "ssyk_code"]):
            v = np.zeros(len(CELLER))
            for l, f, n in zip(g.level, g.field, g.employed):
                v[cell[(l, f)]] += n
            if v.sum() > 0:
                self._lf[(k, o)] = v / v.sum()
        cw = pd.read_sql("SELECT occupation_code AS ssyk, onet_code, share "
                         "FROM ssyk3_onet_crosswalk", conn)
        # UTBILDNINGENS YRKE BARA BLAND YRKEN MED PLATS I RUMMET. De militära
        # (011, 021, 031) och okänt yrke (0002) saknar O*NET-koppling; deras
        # andel av 25-29-åringarna med varje utbildning fördelas på de övriga.
        # Bortfallet står i self.bortfall.
        placerbara = set(cw.ssyk)
        u = kand[kand.age_class == DRAGNINGSKLASS]
        self.bortfall = float(u[~u.ssyk_code.isin(placerbara)].employed.sum()
                              / max(u.employed.sum(), 1.0))
        self._o = {}
        for (l, f), g in u[u.ssyk_code.isin(placerbara)].groupby(["level", "field"]):
            w = g.employed.to_numpy(float)
            if w.sum() > 0:
                self._o[(l, f)] = (g.ssyk_code.to_numpy(), w / w.sum())
        # P(ssyk | onet) ∝ crosswalkens andel x yrkets anställda: för dem vars
        # yrke bara finns som O*NET-kod (arbetslösa vid start, reservoaren).
        anst = d.groupby("ssyk_code").employed.sum()
        cw["w"] = cw.share * cw.ssyk.map(anst).fillna(0.0)
        self._ssyk = {k: (g.ssyk.to_numpy(), g.w.to_numpy(float) / g.w.sum())
                      for k, g in cw.groupby("onet_code") if g.w.sum() > 0}
        self._onet = {k: (g.onet_code.to_numpy(), g.share.to_numpy(float) / g.share.sum())
                      for k, g in cw.groupby("ssyk") if g.share.sum() > 0}

    def ssyk_for_onet(self, onet, rng):
        s = self._ssyk.get(str(onet))
        if s is None:
            raise ValueError(f"O*NET-koden {onet} saknas i ssyk3_onet_crosswalk.")
        return str(s[0][rng.choice(len(s[1]), p=s[1])])

    def fordelning(self, ssyk, alder):
        """P(nivå, inriktning | yrke, ålder) över CELLER, bara kända."""
        k = _aldersklass(alder, self.klasser)
        t = self._lf.get((k, str(ssyk)))
        if t is None:
            raise ValueError(f"Yrket {ssyk} har inga anställda med känd utbildning "
                             f"i åldersklassen {k}.")
        return t

    def utbildningens_yrke(self, niva, inriktning, rng):
        """(ssyk, onet) där utbildningen pekade, eller None för allmän
        utbildning och förgymnasial nivå: den cirkeln ligger i origo."""
        if inriktning == ALLMAN or int(niva) <= 2:
            return None
        t = self._o.get((str(niva), str(inriktning)))
        if t is None:
            raise ValueError(f"Ingen 25-29-åring med nivå {niva} och inriktning "
                             f"{inriktning} i fördelningen.")
        ssyk = str(t[0][rng.choice(len(t[1]), p=t[1])])
        o = self._onet.get(ssyk)
        if o is None:
            raise ValueError(f"SSYK {ssyk} saknas i ssyk3_onet_crosswalk.")
        return ssyk, str(o[0][rng.choice(len(o[1]), p=o[1])])


def kommunens_nivaer(conn, kommuner, kolumn="employed"):
    """TAB6666: andelen per nivågrupp, 20-65 år, per kommun, utan okänd nivå,
    för de sysselsatta (kolumn employed) eller de arbetslösa (unemployed).
    Kastar om tabellen eller en kommun saknas."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND "
                    "name='employment_education_municipality'").fetchone() is None:
        raise ValueError("Tabellen employment_education_municipality saknas. Hämta med "
                         "python scripts/fetch_data.py --only \"Arbetsmarknadsstatus kommun "
                         "utbildning\" och kör python scripts/create_database.py.")
    if kolumn not in ("employed", "unemployed"):
        raise ValueError(kolumn)
    df = pd.read_sql(f"SELECT municipal_code, level_group, {kolumn} AS n "
                     "FROM employment_education_municipality", conn)
    df = df[df.level_group.isin(GRUPPER)]
    ut = {}
    for k in kommuner:
        g = df[df.municipal_code == k].set_index("level_group").n.reindex(GRUPPER)
        if g.isna().any() or g.sum() <= 0:
            raise ValueError(f"Kommun {k} saknas i employment_education_municipality.")
        ut[k] = g.to_numpy(float) / g.sum()
    return ut


def luta_mot_kommunen(P, mal, iterationer=200, tol=1e-9):
    """Faktorer lambda per nivågrupp så att medlet av de lutade raderna,
    q_i ∝ P_i · lambda[grupp], har nivågruppernas andelar mal. P är
    personer x CELLER."""
    lam = np.ones(len(GRUPPER))
    for _ in range(iterationer):
        Q = P * lam[_CELLGRUPP][None, :]
        Q /= Q.sum(axis=1, keepdims=True)
        andel = np.array([Q[:, _CELLGRUPP == g].sum() for g in range(len(GRUPPER))]) / len(P)
        steg = np.divide(mal, andel, out=np.ones_like(mal), where=andel > 0)
        lam *= steg
        if np.abs(andel - mal).max() < tol:
            break
    return lam


def prima_utbildningen(world, rng):
    """Startpopulationens utbildning givet yrket (6a-ii).

    För varje anställd, arbetslös och reservoarmedlem med ett yrke: yrket är
    jobbets SSYK för den anställda, annars startyrkets (O*NET, översatt till
    SSYK). Nivå och inriktning dras ur P(nivå, inriktning | yrke, ålder),
    LUTAD MOT KOMMUNEN: rikets fördelning givet yrket överskattar
    utbildningen i glesbygden (Ovansiljans sysselsatta 20-65 år har 20,5
    procent eftergymnasial utbildning om minst tre år mot 27,4 utan
    lutningen), så en faktor per kommun och nivågrupp anpassas tills
    kommunens sysselsatta 20-65 år har TAB6666:s fördelning. Faktorn gäller
    alla från kommunen; reservoaren får sin ursprungskommuns.

    Utbildningscirkeln ersätter den gamla; grundskolans står kvar. Allmän
    utbildning och förgymnasial nivå läggs i origo med radien 1 (Stapeln i
    utbildningsmodell.md), annars på utbildningens yrke med nivåns radie och
    massa.

    En värld utan databas (syntetiska tester) lämnas orörd. Med databas
    kastar saknade tabeller och kommuner."""
    if getattr(world, "conn", None) is None or not hasattr(world, "circles"):
        return {}
    from core.occupations.competence import EDU_MASS, EDU_RADIUS2
    dr = getattr(world, "_utbildningsdragning", None)
    if dr is None:
        dr = world._utbildningsdragning = Utbildningsdragning(world.conn)
    ind, jobs, c = world.individuals, world.jobs, world.circles
    ji = world.job_index()
    status = ind["status"].to_numpy()
    alder = pd.to_numeric(ind["age"], errors="coerce").to_numpy(float)
    kommun = ind["municipal_code"].astype(str).str.zfill(4).to_numpy()
    for kol in ("education_field", "education_ssyk"):
        if kol not in ind.columns:
            ind[kol] = pd.Series([None] * len(ind), index=ind.index, dtype="object")

    # Kolumnerna läses en gång: .at per person kostade mer än dragningarna.
    job_id = ind["job_id"].to_numpy() if "job_id" in ind.columns else np.full(len(ind), None)
    onet_ind = ind["onet_code"].to_numpy() if "onet_code" in ind.columns else np.full(len(ind), None)
    jobb_ssyk = jobs["ssyk_code"].to_numpy() if "ssyk_code" in jobs.columns else None
    saknas = lambda v: v is None or (isinstance(v, float) and np.isnan(v))
    rader, P = [], []
    for i in np.flatnonzero(np.isin(status, ("employed", "unemployed", "extern"))):
        ssyk = None
        if status[i] == "employed" and jobb_ssyk is not None:
            pos = ji.get(job_id[i])
            if pos is not None:
                ssyk = jobb_ssyk[pos]
        if saknas(ssyk):
            if saknas(onet_ind[i]):
                continue
            ssyk = dr.ssyk_for_onet(onet_ind[i], rng)
        rader.append(i)
        P.append(dr.fordelning(str(ssyk), alder[i]))
    if not rader:
        return {}
    rader, P = np.asarray(rader), np.vstack(P)

    # LUTNINGEN, per kommun och för sysselsatta och arbetslösa var för sig,
    # anpassad på kommunens 20-65-åringar. De arbetslösa har en egen: i
    # Ovansiljan har 31 procent av dem förgymnasial utbildning mot 10
    # procent av de sysselsatta, och utan den fick de arbetslösa de
    # sysselsattas fördelning, eftersom dragningen bara ser yrket. Det är
    # primingens stationaritetsantagande: startårets tvärsnitt ser ut som
    # datan. Reservoarens medlemmar arbetar i sin ursprungskommun (status
    # extern) och räknas som sysselsatta där.
    st = status[rader]
    i_alder = (alder[rader] >= KOMMUNENS_ALDER[0]) & (alder[rader] <= KOMMUNENS_ALDER[1])
    kommuner = sorted(set(kommun[rader]))
    Q = P.copy()
    lam_ut = {}
    for grupp, statusar, kolumn in (("sysselsatta", ("employed", "extern"), "employed"),
                                    ("arbetslösa", ("unemployed",), "unemployed")):
        i_grupp = np.isin(st, statusar)
        berorda = sorted(set(kommun[rader][i_grupp]))
        if not berorda:
            continue
        mal = kommunens_nivaer(world.conn, berorda, kolumn)
        for k, m in mal.items():
            ik = (kommun[rader] == k) & i_grupp
            anp = ik & i_alder
            lam = luta_mot_kommunen(P[anp] if anp.any() else P[ik], m)
            Q[ik] = P[ik] * lam[_CELLGRUPP][None, :]
            lam_ut[(k, grupp)] = lam
    Q /= Q.sum(axis=1, keepdims=True)

    i_origo = 0
    niva_ut = np.empty(len(rader), dtype=int)
    inr_ut = np.empty(len(rader), dtype=object)
    ssyk_ut = np.empty(len(rader), dtype=object)
    for r, i in enumerate(rader):
        niva, inr = CELLER[rng.choice(len(CELLER), p=Q[r])]
        for k in np.flatnonzero(c.key[i] >= 0):
            namn = c.key_names[c.key[i, k]]
            if str(namn).startswith("EDU:") and namn != "EDU:0":
                c.remove(i, k)
        lvl = int(niva)
        mal_yrke = dr.utbildningens_yrke(niva, inr, rng)
        if lvl >= 3:
            if mal_yrke is None:
                c.add(i, f"EDU:{lvl}", 0.0, 0.0, 1.0, EDU_MASS[lvl])
                i_origo += 1
            else:
                geom = world._geom_lookup(mal_yrke[1])
                if geom is None:
                    raise ValueError(f"O*NET-koden {mal_yrke[1]} saknar geometri.")
                c.add(i, f"EDU:{lvl}", float(geom["x_occ"]), float(geom["y_occ"]),
                      EDU_RADIUS2[lvl], EDU_MASS[lvl])
        niva_ut[r], inr_ut[r] = lvl, inr
        ssyk_ut[r] = None if mal_yrke is None else mal_yrke[0]
    for kol, v in (("education_level", niva_ut), ("education_field", inr_ut),
                   ("education_ssyk", ssyk_ut)):
        if kol == "education_level":
            ind[kol] = ind[kol].astype(object)
        ind.iloc[rader, ind.columns.get_loc(kol)] = v
    world._utbildning_lutning = lam_ut
    return {"utbildning_dragen": int(len(rader)), "utbildning_i_origo": i_origo,
            "utbildning_bortfall_oplacerbara": round(dr.bortfall, 4)}
