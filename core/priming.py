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

Utbildningscirkeln lämnas som den är: den ska dras givet yrket ur TAB4360 och
TAB4359 (6a-ii), när läsarna i steg 4 finns. Reservoaren i omgivningen som inte
fått jobb lämnas också; hemyrkets cirkel är hennes pågående arbete.
"""
from __future__ import annotations

import numpy as np


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
    world._write_competence_summary()
    return {"priming_flyttade": flyttade, "priming_arbetslosa": arbetslosa}
