"""Inträdet: de unga på väg in (6b-2, docs/intradet.md).

Vid 16 får varje ung invånare en UTBILDNINGSPLAN -- slutlig nivå och
inriktning, avslutningsålder, och om hon alls går in i arbetskraften -- och
statusen student. Vid avslutningsåldern läggs utbildningens cirklar och hon
blir arbetslös och söker; det första jobbet är ett utfall av matchningen.
Deltagandet per ålder blir därmed ett utfall, som prövas mot BAS-profilen.

PLANENS FÖRDELNING (beslut 2, 2026-09-19). Nivån dras ur 25-34-åringarnas
fördelning I KOMMUNEN (TAB6928, befolkningen år 2): lagret efter
studieflyttningen, rätt mål för dem som stannar när modellen saknar
flyttningar. TAB6928 har fyra nivågrupper; de delas på SUN:s nivåer, och
inriktningen dras givet nivån, ur TAB655 för 25-34 år i riket. Okänd nivå och
okänd inriktning tas inte med.

AVSLUTNINGSÅLDERN per nivå ur TAB3731 (riket, ettårsklasser): ökningen i
ANDELEN av åldersklassen som inte studerar och har nivån, från en ålder till
nästa. Andelar och inte antal, så att olika stora årskullar inte läses som
inträden. Klassen 30-34 räknas som 31. Forskarnivån syns knappt före 30 och
får 30-33. FÖRGYMNASIAL OCH KORT GYMNASIAL NIVÅ (1-3) avslutas i skolåldern:
deras andel stiger också vid 24-25 (nivå 1: 40 procent av ökningen vid 25),
men det är invandring och vuxenutbildning bland vuxna, inte unga som slutar
skolan, så bara ökningen 16-20 räknas.

ALDRIG IN (beslut 4). Andelen är 1 minus deltagandeprofilens platå -- högsta
deltagandet 30-54 i kommunens profil -- så att in och ut räknas ur samma kurva.

STUDENTEN står utanför arbetskraften, söker inte jobb (det är 6c) och möter
inte utträdeshasarden. Status student, inte in_education, som är omskolning
inom arbetskraften och bär en annan händelsekedja.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

GRUPP_NIVAER = {"02": ("1", "2"), "03": ("3", "4"), "04": ("5",), "05": ("6", "7")}
NIVAER = ("1", "2", "3", "4", "5", "6", "7")
INRIKTNINGAR = ("0", "1", "2", "3", "4", "5", "6", "7", "8")
PLATA_ALDRAR = (30, 54)
SKOLNIVAER, SKOLALDER_MAX = ("1", "2", "3"), 20
HAMTA = ("Inträdets tabeller saknas. Hämta med python scripts/fetch_data.py "
         "--only studiedeltagande och --only Utbildningsfloden, och kör "
         "python scripts/create_database.py.")


def _tabell_finns(conn, namn):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (namn,)).fetchone() is not None


def avslutningsaldrar(studie: pd.DataFrame):
    """Nivå -> (åldrar, sannolikheter) för när studierna avslutas."""
    d = studie.copy()
    d["n"] = d["population"].astype(float)
    tot = d.groupby("age").n.sum()
    ej = d[d.study == "0"].groupby(["age", "level"]).n.sum().unstack(fill_value=0.0)
    aldrar = [str(a) for a in range(16, 30)] + ["30-34"]
    andel = ej.reindex(aldrar).fillna(0.0).div(tot.reindex(aldrar), axis=0)
    numerisk = [16 + i for i in range(14)] + [31]
    ut = {}
    for l in NIVAER:
        if l == "7":
            ut[l] = (np.array([30, 31, 32, 33]), np.full(4, 0.25))
            continue
        if l not in andel.columns:
            continue
        s = andel[l].to_numpy()
        okn = np.maximum(np.diff(np.concatenate([[0.0], s])), 0.0)
        if l in SKOLNIVAER:
            okn = np.where(np.array(numerisk) <= SKOLALDER_MAX, okn, 0.0)
        if okn.sum() <= 0:
            continue
        ut[l] = (np.array(numerisk), okn / okn.sum())
    return ut


class Intradesplan:
    """Fördelningarna för planen, per kommun."""

    def __init__(self, conn, participation):
        for t in ("education_flows_municipality", "population_study_education",
                  "population_level_field"):
            if not _tabell_finns(conn, t):
                raise ValueError(f"Tabellen {t} saknas. " + HAMTA)
        fl = pd.read_sql("SELECT municipal_code, edu_group, value FROM "
                         "education_flows_municipality WHERE measure='population_2' "
                         "AND age_class IN ('25-29','30-34') AND edu_group IN "
                         "('02','03','04','05')", conn)
        self._grupp = {k: g.groupby("edu_group").value.sum()
                       for k, g in fl.groupby("municipal_code")}
        lf = pd.read_sql("SELECT level, field, SUM(population) AS n FROM "
                         "population_level_field WHERE age_class='25-34' "
                         "GROUP BY level, field", conn)
        lf = lf[lf.level.isin(NIVAER) & lf.field.isin(INRIKTNINGAR)]
        niva = lf.groupby("level").n.sum()
        # Nivåns andel inom sin grupp och inriktningen givet nivån, riket 25-34.
        self._inom = {g: np.array([niva.get(l, 0.0) for l in ls]) / max(sum(niva.get(l, 0.0) for l in ls), 1.0)
                      for g, ls in GRUPP_NIVAER.items()}
        self._inr = {}
        for l, g in lf.groupby("level"):
            v = g.set_index("field").n.reindex(list(INRIKTNINGAR)).fillna(0.0).to_numpy()
            self._inr[l] = v / v.sum()
        studie = pd.read_sql("SELECT age, study, level, population FROM "
                             "population_study_education", conn)
        self._alder = avslutningsaldrar(studie)
        self._part = participation or {}

    def nivafordelning(self, kommun):
        """P(nivå) för kommunens plan, över NIVAER."""
        g = self._grupp.get(str(kommun).zfill(4))
        if g is None or g.sum() <= 0:
            raise ValueError(f"Kommun {kommun} saknas i education_flows_municipality. " + HAMTA)
        p = np.zeros(len(NIVAER))
        for grupp, ls in GRUPP_NIVAER.items():
            for l, andel in zip(ls, self._inom[grupp]):
                p[NIVAER.index(l)] += g.get(grupp, 0.0) * andel
        return p / p.sum()

    def aldrig_in(self, kommun):
        q = self._part.get(str(kommun).zfill(4))
        if q is None:
            raise ValueError(f"Deltagandeprofilen saknas för kommun {kommun}.")
        q = pd.Series(q).astype(float)
        platå = q[(q.index >= PLATA_ALDRAR[0]) & (q.index <= PLATA_ALDRAR[1])]
        if platå.empty:
            raise ValueError(f"Deltagandeprofilen för {kommun} saknar åldrarna 30-54.")
        return float(max(0.0, 1.0 - platå.max()))

    def dra(self, kommun, rng, efter_alder=None):
        """(nivå, inriktning, avslutningsålder, går_in). efter_alder: planen
        ska avslutas efter den åldern (startpopulationens studerande)."""
        p = self.nivafordelning(kommun)
        if efter_alder is not None:
            # P(nivå | avslutas efter åldern) ∝ P(nivå) P(avslutas efter | nivå)
            kvar = np.array([self._alder[l][1][self._alder[l][0] > efter_alder].sum()
                             if l in self._alder else 0.0 for l in NIVAER])
            p = p * kvar
            if p.sum() <= 0:
                raise ValueError(f"Ingen plan i {kommun} avslutas efter {efter_alder} år.")
            p = p / p.sum()
        l = NIVAER[rng.choice(len(NIVAER), p=p)]
        if l not in self._alder:
            raise ValueError(f"Nivå {l} saknas i population_study_education; ingen "
                             "avslutningsålder. " + HAMTA)
        aldrar, pa = self._alder[l]
        if efter_alder is not None:
            ok = aldrar > efter_alder
            aldrar, pa = aldrar[ok], pa[ok] / pa[ok].sum()
        a = int(aldrar[rng.choice(len(aldrar), p=pa)])
        f = INRIKTNINGAR[rng.choice(len(INRIKTNINGAR), p=self._inr[l])]
        return l, f, a, bool(rng.random() >= self.aldrig_in(kommun))


PLAN_KOLUMNER = ("plan_level", "plan_field", "plan_entry_age", "plan_enters")


def _plan(world):
    p = getattr(world, "_intradesplan", None)
    if p is None:
        p = world._intradesplan = Intradesplan(world.conn, getattr(world, "participation", {}))
    return p


def studentens_ansprak(world, idx):
    """Den studerandes anspråk för ett extrajobb (6c): percentilen
    studerande_ansprak_percentil i hennes relevansfördelning. Extrajobbet
    jämförs inte med en heltidslön; anspråket är lågt och sänks inte med
    tiden, eftersom hon aldrig är arbetslös."""
    from core.event_handlers import _normkvantil, reservationsgolv
    from core.matching_core import relevansfordelning
    sim = world.cfg_reader.config.get("simulation", {})
    if "studerande_ansprak_percentil" not in sim:
        raise ValueError("simulation.studerande_ansprak_percentil saknas (docs/intradet.md, 6c).")
    f = relevansfordelning(world, idx)
    if f:
        med, sd, _n = f
        return float(med * np.exp(sd * _normkvantil(float(sim["studerande_ansprak_percentil"]))))
    return reservationsgolv(world, idx)


def _studerande_kolumn(world):
    ind = world.individuals
    if "studerande" not in ind.columns:
        ind["studerande"] = False
        world.refresh_ind()


def tilldela_plan(world, idx, t_now, rng, efter_alder=None, med_jobb=False):
    """Gör idx till studerande med en plan och schemalägger inträdet. Utan
    jobb blir hon student och söker extrajobb; med jobb (startens unga i
    arbetskraften, 6c) behåller hon det."""
    ind = world.individuals
    for kol in PLAN_KOLUMNER:
        if kol not in ind.columns:
            ind[kol] = pd.Series([None] * len(ind), index=ind.index, dtype="object")
            world.refresh_ind()
    _studerande_kolumn(world)
    kommun = str(ind.at[idx, "municipal_code"]).zfill(4)
    l, f, a, in_ = _plan(world).dra(kommun, rng, efter_alder)
    alder = float(ind.at[idx, "age"])
    ind.at[idx, "studerande"] = True
    if not med_jobb:
        ind.at[idx, "status"] = "student"
        ind.at[idx, "w_res"] = studentens_ansprak(world, idx)
        world.schedule_search(idx, world.search_interval(idx, t_now))
    ind.at[idx, "plan_level"], ind.at[idx, "plan_field"] = l, f
    ind.at[idx, "plan_entry_age"], ind.at[idx, "plan_enters"] = a, in_
    # Inom avslutningsåret, likformigt: gymnasiet slutar i juni, högskolan
    # vid terminsslut, och modellen har ingen kalender för det.
    t = float(t_now) + (max(a - alder, 0.0) + float(rng.random())) * 365.25
    world._push_event({"time": t, "agent_id": idx, "event_type": "intrade", "params": {}})
    return l, f, a, in_


def handle_intrade(event, world):
    """Studierna är slut: utbildningens cirklar läggs, och den som går in blir
    arbetslös med ett startanspråk vid medianen av sin relevansfördelning
    (beslut 3); den som aldrig går in hamnar utanför arbetskraften."""
    from core.event_handlers import bli_arbetslos
    from core.occupations.competence import EDU_MASS, EDU_RADIUS2
    from core.priming import Utbildningsdragning
    idx, t_now = event["agent_id"], float(event["time"])
    ind = world.individuals
    if idx not in ind.index:
        return
    status = ind.at[idx, "status"]
    med_jobb = status == "employed" and "studerande" in ind.columns and bool(ind.at[idx, "studerande"])
    if status != "student" and not med_jobb:
        return
    if "studerande" in ind.columns:
        ind.at[idx, "studerande"] = False
    dr = getattr(world, "_utbildningsdragning", None)
    if dr is None:
        dr = world._utbildningsdragning = Utbildningsdragning(world.conn)
    rng = np.random.default_rng(np.random.randint(2 ** 31))
    l, f = str(ind.at[idx, "plan_level"]), str(ind.at[idx, "plan_field"])
    lvl = int(l)
    mal = dr.utbildningens_yrke(l, f, rng)
    for kol in ("education_field", "education_ssyk"):
        if kol not in ind.columns:
            ind[kol] = pd.Series([None] * len(ind), index=ind.index, dtype="object")
            world.refresh_ind()
    ind.at[idx, "education_level"] = lvl
    ind.at[idx, "education_field"] = f
    ind.at[idx, "education_ssyk"] = None if mal is None else mal[0]
    if hasattr(world, "circles") and lvl >= 3:
        pos = ind.index.get_loc(idx)
        if mal is None:
            world.circles.add(pos, f"EDU:{lvl}", 0.0, 0.0, 1.0, EDU_MASS[lvl])
        else:
            geom = world._geom_lookup(mal[1])
            if geom is None:
                raise ValueError(f"O*NET-koden {mal[1]} saknar geometri.")
            world.circles.add(pos, f"EDU:{lvl}", float(geom["x_occ"]), float(geom["y_occ"]),
                              EDU_RADIUS2[lvl], EDU_MASS[lvl])
    if med_jobb:
        # Extrajobbet blir en vanlig anställning för den som går in; den som
        # aldrig går in slutar.
        if not bool(ind.at[idx, "plan_enters"]):
            from core.event_handlers import tillbaka_till_studierna
            tillbaka_till_studierna(world, idx, t_now)
            ind.at[idx, "status"] = "not_in_labor_force"
            ind.at[idx, "next_search_time"] = np.nan
            world.event_logger.log_event(world, event, extra={
                "event_detail": "never_entered_left_job", "agent_id": idx, "level": l, "field": f})
            return
        world.event_logger.log_event(world, event, extra={
            "event_detail": "entered_kept_job", "agent_id": idx, "level": l, "field": f})
        return
    # Genereringens slumpade yrke för den som stod utanför arbetskraften är
    # ingen erfarenhet; hon har inget senaste yrke och ingen senaste lön.
    # (Extrajobbets cirkel ligger kvar: den är erfarenhet.)
    for kol in ("onet_code", "last_onet_code", "w_res", "w_last", "w_neg"):
        if kol in ind.columns:
            ind.at[idx, kol] = np.nan
    if not bool(ind.at[idx, "plan_enters"]):
        ind.at[idx, "status"] = "not_in_labor_force"
        world.event_logger.log_event(world, event, extra={
            "event_detail": "never_entered", "agent_id": idx, "level": l, "field": f})
        return
    ind.at[idx, "status"] = "unemployed"
    bli_arbetslos(world, idx, t_now)
    sim = world.cfg_reader.config.get("simulation", {})
    if "intrade_ansprak_percentil" not in sim:
        raise ValueError("simulation.intrade_ansprak_percentil saknas (docs/intradet.md, beslut 3).")
    p0 = float(sim["intrade_ansprak_percentil"])
    med = float(ind.at[idx, "w_rel_med"]) if "w_rel_med" in ind.columns else np.nan
    sd = float(ind.at[idx, "w_rel_sd"]) if "w_rel_sd" in ind.columns else np.nan
    if np.isfinite(med) and np.isfinite(sd):
        from core.event_handlers import _normkvantil
        ind.at[idx, "p_claim0"] = p0
        ind.at[idx, "w_res"] = float(med * np.exp(sd * _normkvantil(p0)))
    else:
        from core.event_handlers import reservationsgolv
        ind.at[idx, "w_res"] = reservationsgolv(world, idx)
    world.schedule_search(idx, world.search_interval(idx, t_now))
    world.event_logger.log_event(world, event, extra={
        "event_detail": "entered_labour_force", "agent_id": idx, "level": l, "field": f,
        "w_res": round(float(ind.at[idx, "w_res"]), 4)})


def nya_sextonaringar(world, t_now):
    """Årsskiftet: invånare som fyllt 16 och står utanför arbetskraften utan
    plan får en. Anropas efter åldrandet."""
    ind = world.individuals
    if getattr(world, "conn", None) is None or "age" not in ind.columns:
        return 0
    ext = ind["extern"].fillna(False).astype(bool) if "extern" in ind.columns else False
    age = pd.to_numeric(ind["age"], errors="coerce")
    utan_plan = (ind["plan_level"].isna() if "plan_level" in ind.columns
                 else pd.Series(True, index=ind.index))
    kand = ind.index[(age >= 16) & (age < 17) & (ind["status"] == "not_in_labor_force")
                     & ~ext & utan_plan]
    rng = np.random.default_rng(np.random.randint(2 ** 31))
    for idx in kand:
        tilldela_plan(world, idx, t_now, rng)
    return int(len(kand))


# ---------------------------------------------------------------------------
# 6b-3: startpopulationens unga utanför arbetskraften
# ---------------------------------------------------------------------------
UNGA_ALDRAR = (16, 29)


def andel_studerande(conn, forvarvsarbetar=False):
    """P(studerar | förvärvsarbetar eller inte, ålder), 16-29, ur TAB3731.

    Startpopulationens unga utanför arbetskraften är de som inte
    förvärvsarbetar (de arbetslösa är få i de åldrarna). Bland dem studerar
    95 procent vid 16, drygt hälften vid 19 och en tredjedel vid 29."""
    if not _tabell_finns(conn, "population_study_education"):
        raise ValueError("Tabellen population_study_education saknas. " + HAMTA)
    d = pd.read_sql("SELECT age, study, employment, SUM(population) AS n "
                    "FROM population_study_education GROUP BY 1, 2, 3", conn)
    d = d[d.employment == "FÖRV"] if forvarvsarbetar else d[d.employment != "FÖRV"]
    ut = {}
    for a in range(UNGA_ALDRAR[0], UNGA_ALDRAR[1] + 1):
        g = d[d.age == str(a)]
        tot = float(g.n.sum())
        if tot <= 0:
            raise ValueError(f"TAB3731 saknar åldern {a}. " + HAMTA)
        ut[a] = float(g[g.study != "0"].n.sum()) / tot
    return ut


def prima_unga(world, t_now, rng):
    """Startpopulationens invånare 16-29 utanför arbetskraften: studerande med
    en plan som avslutas efter hennes ålder, med sannolikheten ur TAB3731,
    annars kvar utanför. Utan steget fick ingen av dem någonsin en plan, och
    årskullarna som var 17-19 vid start kom aldrig in."""
    if getattr(world, "conn", None) is None:
        return {}
    ind = world.individuals
    p = andel_studerande(world.conn)
    ext = ind["extern"].fillna(False).astype(bool) if "extern" in ind.columns else False
    age = pd.to_numeric(ind["age"], errors="coerce")
    utan_plan = (ind["plan_level"].isna() if "plan_level" in ind.columns
                 else pd.Series(True, index=ind.index))
    kand = ind.index[(age >= UNGA_ALDRAR[0]) & (age < UNGA_ALDRAR[1] + 1)
                     & (ind["status"] == "not_in_labor_force") & ~ext & utan_plan]
    n = 0
    for idx in kand:
        a = float(ind.at[idx, "age"])
        if rng.random() < p[int(a)]:
            tilldela_plan(world, idx, t_now, rng, efter_alder=int(a))
            n += 1
    # 6c: STARTENS UNGA I ARBETSKRAFTEN. En gymnasieelev med två kvällar i
    # veckan är sysselsatt i BAS och ligger därför i modellens arbetskraft,
    # men med vuxnas beteende. Den anställda blir studerande med extrajobb
    # med P(studerar | förvärvsarbetar, ålder); den arbetslösa under 20 --
    # BAS har ingen arbetslöshet där -- blir student med P(studerar |
    # förvärvsarbetar inte, ålder).
    p_f = andel_studerande(world.conn, forvarvsarbetar=True)
    unga_lf = ind.index[(age >= UNGA_ALDRAR[0]) & (age < UNGA_ALDRAR[1] + 1)
                        & ind["status"].isin(["employed", "unemployed"]) & ~ext & utan_plan]
    med_jobb = utan = 0
    for idx in unga_lf:
        a = int(float(ind.at[idx, "age"]))
        if ind.at[idx, "status"] == "employed":
            if rng.random() < p_f[a]:
                tilldela_plan(world, idx, t_now, rng, efter_alder=a, med_jobb=True)
                med_jobb += 1
        elif a < 20 and rng.random() < p[a]:
            tilldela_plan(world, idx, t_now, rng, efter_alder=a)
            utan += 1
    return {"unga_studerande": n, "unga_utanfor": int(len(kand) - n),
            "unga_studerande_med_jobb": med_jobb, "unga_arbetslosa_till_studier": utan}
