"""
core/analysis/eventlog.py
-------------------------
En parser för eventloggen, och en definition av vad en tabell är.

Tidigare hade validate_mobility, convergence och figures varsin kopia av
samma _parse, och check_invariants och compare_municipalities läste
tillståndsfilerna med varsin egen logik. Fem skript, fem tolkningar av samma
data, och en felkälla varje gång loggformatet rörs.

Eventloggen är rader av "tid, händelse, nyckel värde, nyckel värde, ...".
Det duger för felsökning men gör varje analys till en parsningsövning. Här
görs den en gång, till tre tabeller:

    transitions   en rad per tillträde: käll- och målyrke, u_R, löner, q
    timeseries    en rad per månad: stockar och flöden
    summary       en rad per körning: nyckeltalen, för jämförelse mellan
                  körningar och som indata till regressioner
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

MGMT_PREFIX = "11-"


def parse_line(line):
    """En loggrad -> dict, eller None. Enda stället detta görs."""
    parts = [p.strip() for p in line.rstrip("\n").split(",")]
    if len(parts) < 2:
        return None
    rec = {}
    try:
        rec["time"] = float(parts[0])
    except ValueError:
        return None
    rec["event"] = parts[1]
    for f in parts[2:]:
        if f:
            k, _, v = f.partition(" ")
            rec[k] = v.strip()
    return rec


def read_events(run_dir):
    """Alla loggrader som dicts. Läses en gång och återanvänds."""
    path = os.path.join(run_dir, "eventlog.csv")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            r = parse_line(line)
            if r is not None:
                out.append(r)
    return out


def _f(rec, key, default=np.nan):
    try:
        return float(rec[key])
    except (KeyError, TypeError, ValueError):
        return default


def _b(rec, key, default=False):
    """Boolesk loggpost. parse_line ger STRÄNGAR, och bool("False") är True:
    med bool(r.get(...)) var winner_employed sant för varje tillsättning och
    job_to_job sant för varje anställning under körning. Två av stegens tre
    mått var därmed konstanter -- 100 procent till anställda, byten lika med
    alla anställningar -- och restpoolsdiagnosen i lonemodell.md 4.2 byggde
    på dem."""
    v = rec.get(key)
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
def transitions_table(events):
    """En rad per tillträde.

    Kolumnerna occ_change och is_mgmt bär de urskiljningar valideringen gör:
    CPS räknar bara yrkesbyten, och tvärflödet är befordran snarare än
    uppgiftsbaserad rörlighet.
    """
    rows = []
    for r in events:
        if r.get("event") != "start_job" or "u_R" not in r:
            continue
        src, tgt = str(r.get("from_onet", "")), str(r.get("to_onet", ""))
        rows.append({
            "time": r["time"],
            "year": r["time"] / 365.25,
            "agent_id": r.get("agent_id"),
            "job_id": r.get("job_id"),
            "from_onet": src or None,
            "to_onet": tgt or None,
            "d_task": _f(r, "d_task"),
            "u_R": _f(r, "u_R"),
            "u_R_occ": _f(r, "u_R_occ"),
            "w_field": _f(r, "w_field"),
            "w_neg": _f(r, "w_neg"),
            "q_hire": _f(r, "q_hire"),
            "commute_km": _f(r, "commute_km"),
            "n_applicants": _f(r, "n_applicants"),
            "is_bootstrap": _b(r, "is_bootstrap"),
            "job_to_job": _b(r, "job_to_job"),
            "w_prev": _f(r, "w_prev"),
            "vacancy_age_days": _f(r, "vacancy_age_days"),
            "w_occ": _f(r, "w_occ"),
            "r_req": _f(r, "r_req"),
            "occ_change": bool(int(r.get("occ_change", 1))) if "occ_change" in r else np.nan,
            "is_mgmt": (src.startswith(MGMT_PREFIX) or tgt.startswith(MGMT_PREFIX))
                       if (src or tgt) else np.nan,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        # Mot YRKETS fältlön, inte jobbets. Med w = Pi_j * p**theta och
        # Pi_j = Pi_o * exp(eta) står eta i både täljare och nämnare om man
        # delar med w_field och försvinner identiskt: bottenkvartilen låg på
        # exakt 1.000 med 43 procent på punkten trots att sd(log w_field)
        # inom yrke var 0.103. w_neg/w_occ är det mått SCB:s
        # lönestrukturstatistik per SSYK går att jämföra med.
        nämnare = df["w_occ"] if "w_occ" in df.columns else df["w_field"]
        nämnare = nämnare.fillna(df["w_field"])
        df["wage_ratio"] = df["w_neg"] / nämnare.replace(0, np.nan)
        # Arbetsgivarkomponenten isolerad: Pi_j / Pi_o = exp(eta)
        if "w_occ" in df.columns:
            df["employer_premium"] = df["w_field"] / df["w_occ"].replace(0, np.nan)
        # Det urval CPS jämförs mot: yrkesbyten utan chefsövergångar.
        # Uppstartens anställningar är INTE mobilitet. De går genom
        # handle_start_job och hamnar därför i tabellen -- 10 165 av 21 594 i
        # en femårskörning -- och räknades som yrkesövergångar eftersom
        # individens seedade onet_code skiljer sig från jobbets. Det blåste
        # upp n_cps_sample från 8 285 till 17 900 och spädde ut median u_R:
        # uppstartens egna övergångar hade median 0.687 mot körningens
        # 0.76-0.80, eftersom konkurrensen per vakans är som störst när alla
        # är lediga samtidigt. De ligger kvar i tabellen med sin flagga -- de
        # är det bästa måttet på hur väl uppstarten matchar -- men utanför
        # valideringsurvalet.
        df["in_cps_sample"] = (df["occ_change"].fillna(False).astype(bool)
                               & ~df["is_mgmt"].fillna(False).astype(bool)
                               & ~df["is_bootstrap"].fillna(False).astype(bool))
    return df


def timeseries_table(events):
    """En rad per månad: stockar, flöden och identitetens residual."""
    rows = []
    for r in events:
        if r.get("event") != "new_month":
            continue
        emp, unemp = _f(r, "employed"), _f(r, "unemployed")
        vac, J = _f(r, "unmatched_jobs"), _f(r, "active_jobs")
        L = emp + unemp
        rows.append({
            "time": r["time"], "year": r["time"] / 365.25,
            "month": int(_f(r, "month", 0)),
            "employed": emp, "unemployed": unemp, "vacancies": vac,
            "open_vacancies": _f(r, "open_vacancies", vac),
            "active_jobs": J, "posted": _f(r, "posted"),
            "not_in_labour_force": _f(r, "not_in_labour_force"),
            "labour_force": L,
            "u": 100 * unemp / L if L else np.nan,
            "v": 100 * vac / J if J else np.nan,
            # SCB:s vakansgrad räknar lediga befattningar, inte utlovade.
            "v_open": 100 * _f(r, "open_vacancies", vac) / J if J else np.nan,
            "tightness": vac / unemp if unemp else np.nan,
            # U = L - J + V ska hålla exakt; avvikelsen är ett larm.
            "identity_residual": unemp - (L - J + vac),
        })
    return pd.DataFrame(rows)


def flows_table(events):
    """Antal händelser per typ och detalj: sökningar, träffar, förstörelse."""
    from collections import Counter
    c = Counter()
    for r in events:
        c[r.get("event", "?")] += 1
        d = r.get("event_detail")
        if d:
            c[f"detail:{d}"] += 1
    return pd.DataFrame(sorted(c.items()), columns=["key", "count"])


# ---------------------------------------------------------------------------
def summary_row(run_dir, events=None, tr=None, ts=None):
    """En rad per körning: nyckeltalen samlade.

    Detta är tabellen en regression av utfall på uppgiftsrummets täckning ska
    läsa, och den som gör flera frön och flera kommuner jämförbara.
    """
    events = events if events is not None else read_events(run_dir)
    tr = tr if tr is not None else transitions_table(events)
    ts = ts if ts is not None else timeseries_table(events)

    row = {"run": os.path.basename(run_dir.rstrip("/"))}

    # Härkomst: utan den blandar en samlad tabell körningar från olika
    # kodversioner, och en jämförelse mäter kodhistorik.
    mp = os.path.join(run_dir, "run_meta.json")
    if os.path.isfile(mp):
        import json
        try:
            with open(mp, encoding="utf-8") as f:
                meta = json.load(f)
            row.update({
                "scenario": meta.get("scenario"),
                "seed": meta.get("seed"),
                "commit": (meta.get("git_commit") or "")[:8],
                "dirty": bool(meta.get("git_dirty")),
                "municipalities": ",".join(map(str, meta.get("municipalities") or [])),
            })
            sim = meta.get("simulation") or {}
            for k in ("sigma_gamma", "commute_cost_per_km", "choice_scale",
                      "job_destruction_rate", "rho_reservation"):
                if k in sim:
                    row[f"p_{k}"] = sim[k]
        except Exception:
            pass

    if not ts.empty:
        last = ts.iloc[-1]
        row.update({
            "months": len(ts), "years": round(float(last["year"]), 2),
            "employed": last["employed"], "unemployed": last["unemployed"],
            "vacancies": last["vacancies"], "active_jobs": last["active_jobs"],
            "labour_force": last["labour_force"],
            "u_pct": round(float(last["u"]), 3), "v_pct": round(float(last["v"]), 3),
            "v_open_pct": round(float(last["v_open"]), 3)
            if "v_open" in ts.columns and pd.notna(last["v_open"]) else np.nan,
            "tightness": round(float(last["tightness"]), 4),
            "u_min_pct": round(100 * float(last["labour_force"] - last["active_jobs"])
                               / float(last["labour_force"]), 3)
            if last["labour_force"] else np.nan,
            "identity_residual_max": float(ts["identity_residual"].abs().max()),
        })

    if not tr.empty:
        cps = tr[tr["in_cps_sample"]] if "in_cps_sample" in tr else tr
        row.update({
            "n_transitions": len(tr),
            "n_cps_sample": len(cps),
            "share_same_occ": round(float((~tr["occ_change"].fillna(True)).mean()), 4),
            "share_mgmt": round(float(tr["is_mgmt"].fillna(False).mean()), 4),
        })
        if len(cps):
            u = cps["u_R_occ"].dropna()
            if len(u):
                row.update({
                    "median_u_R": round(float(u.median()), 4),
                    "p90_u_R": round(float(u.quantile(0.90)), 4),
                    "p99_u_R": round(float(u.quantile(0.99)), 4),
                    "share_within_1R": round(float((u <= 1.0).mean()), 4),
                    "share_beyond_2R": round(float((u > 2.0).mean()), 4),
                })
            w = cps["wage_ratio"].dropna()
            if len(w):
                row.update({
                    "median_wage_ratio": round(float(w.median()), 4),
                    "median_w_neg": round(float(cps["w_neg"].median()), 4),
                    "median_w_field": round(float(cps["w_field"].median()), 4),
                    "sd_log_wage": round(float(np.std(np.log(
                        cps["w_neg"].replace(0, np.nan).dropna()))), 4),
                })
            q = cps["q_hire"].dropna()
            if len(q):
                row["median_q_hire"] = round(float(q.median()), 4)
                row["p10_q_hire"] = round(float(q.quantile(0.10)), 4)
                row["share_q_below_0.4"] = round(float((q < 0.40).mean()), 4)
                row["min_q_hire"] = round(float(q.min()), 4)
            # STEGEN. Byten per år som andel av anställda, och lönevinsten per
            # byte. Med kappa ~ 26 blir bytena många och vinsterna stora; med
            # empiriska 2-5 få och små. Det är måttet som skiljer en för snabb
            # stege från en felförankrad Pi.
            körning = tr[~tr.get("is_bootstrap", False).fillna(False).astype(bool)] \
                if "is_bootstrap" in tr.columns else tr
            jtj = körning[körning["job_to_job"].fillna(False).astype(bool)] \
                if "job_to_job" in körning.columns else körning.iloc[:0]
            row["n_job_to_job"] = int(len(jtj))
            _ar = float(row.get("years") or 0.0)
            if row.get("employed") and _ar > 0:
                row["job_to_job_rate"] = round(
                    len(jtj) / _ar / max(float(row["employed"]), 1.0), 4)
            if len(jtj) and "w_prev" in jtj.columns:
                g = pd.to_numeric(jtj["w_neg"], errors="coerce") / \
                    pd.to_numeric(jtj["w_prev"], errors="coerce")
                g = g.replace([np.inf, -np.inf], np.nan).dropna()
                if len(g):
                    row["job_to_job_wage_gain"] = round(float(g.median()), 4)
            # DET FÖRSTA STEGET. Svepet 0089 visade att bytena inte styrs av
            # söktakten: halverad sökning gav 17 procent färre byten, och
            # träffsäkerheten per sökning fördubblades. Tolkning: stegen är
            # i huvudsak det första steget efter arbetslöshet -- den som
            # anställts ur arbetslöshet till en lön under Pi har överskott mot
            # nästan varje vakans och flyttar vid nästa sökning. Två mått
            # prövar det: ingångslönen relativt YRKETS Pi efter ursprung, och
            # tiden från anställning ur arbetslöshet till nästa byte.
            if "w_occ" in körning.columns and "job_to_job" in körning.columns:
                is_jtj = körning["job_to_job"].fillna(False).astype(bool)
                for namn, m in (("from_unemployment", ~is_jtj), ("job_to_job", is_jtj)):
                    wage_ratio = (pd.to_numeric(körning.loc[m, "w_neg"], errors="coerce") /
                          pd.to_numeric(körning.loc[m, "w_occ"], errors="coerce"))
                    wage_ratio = wage_ratio.replace([np.inf, -np.inf], np.nan).dropna()
                    if len(wage_ratio):
                        row[f"entry_wage_ratio_{namn}"] = round(float(wage_ratio.median()), 4)
                # Tid till nästa byte, per individ: från varje anställning ur
                # arbetslöshet till individens nästa job_to_job-tillträde.
                # Samma sak här: slingan över alla par per individ var
                # kvadratisk i antalet tillträden per person. Tiden till
                # NÄSTA byte är differensen mot nästa job_to_job-rad, och
                # den fås genom att backfylla bytenas tidpunkter inom
                # individen.
                ordered = körning.sort_values(["agent_id", "time"])
                is_move = ordered["job_to_job"].fillna(False).astype(bool)
                t_move = ordered["time"].where(is_move)
                nasta = t_move.groupby(ordered["agent_id"], sort=False).bfill()
                gaps = (nasta - ordered["time"])[~is_move.to_numpy()]
                gaps = gaps[gaps.notna() & (gaps > 0)].to_numpy(dtype=float)
                if len(gaps):
                    row["days_to_first_step_median"] = round(float(np.median(gaps)), 1)
                    row["share_first_step_within_year"] = round(
                        float(np.mean(gaps <= 365.25)), 4)
                    n_from_unemp = int((~is_jtj).sum())
                    if n_from_unemp:
                        row["share_unemployed_hires_that_step"] = round(
                            len(gaps) / n_from_unemp, 4)
            # FÖRLORANDE BYTEN OCH GAMLA ANSÖKNINGAR. Individkedjorna (0091)
            # visade byten med NEGATIV lönevinst: ansökan lämnas som
            # arbetslös, erbjudandet kommer efter att hon tagit ett annat
            # jobb, och tillträdet sker ändå -- beslutet fattas vid ansökan,
            # aldrig vid erbjudandet. Måtten säger hur stor den kanalen är.
            if len(jtj) and "w_prev" in jtj.columns:
                w_ny = pd.to_numeric(jtj["w_neg"], errors="coerce")
                w_fore = pd.to_numeric(jtj["w_prev"], errors="coerce")
                par = pd.concat([w_ny, w_fore], axis=1).dropna()
                if len(par):
                    row["share_moves_wage_loss"] = round(
                        float((par.iloc[:, 0] < par.iloc[:, 1]).mean()), 4)
                appl = {(r.get("agent_id"), r.get("job_id")): r.get("status")
                        for r in events if r.get("event_detail") == "application_filed"}
                status_vid_ansokan = [
                    appl.get((r["agent_id"], r["job_id"]))
                    for _, r in jtj.iterrows()
                    if (r.get("agent_id"), r.get("job_id")) in appl]
                if status_vid_ansokan:
                    row["share_moves_applied_while_unemployed"] = round(
                        float(np.mean([s == "unemployed" for s in status_vid_ansokan])), 4)
                    row["share_moves_application_matched"] = round(
                        len(status_vid_ansokan) / len(jtj), 4)
                # VARFÖR BYTET LÖNAR SIG. w = Pi_o * exp(eta) * p^theta, och
                # alla tre logaritmerna finns i loggen: w_occ är Pi_o,
                # w_field/w_occ är exp(eta), w_neg/w_field är p^theta. Mellan
                # två på varandra följande anställningar för SAMMA individ
                # blir därför
                #
                #     dlog w_neg = dlog Pi_o + d eta + d(theta log p)
                #
                # en exakt uppdelning: yrkets pris, arbetsgivareffekten och
                # passformen. Och w_prev (lönen hon HADE vid bytet) mot
                # w_neg vid förra anställningen är revisionens bidrag under
                # anställningen. Bytespremien log(w_neg/w_prev) är alltså
                # de tre komponenterna MINUS vad revisionen redan gav.
                # Det är måttet som skiljer spakarna: växer passformen medan
                # revisionen står still är beta_q spaken, inte friktionen.
                kol = {"w_neg", "w_field", "w_occ"}
                if kol <= set(körning.columns):
                    # VEKTORISERAT. En itertuples-slinga över par per individ
                    # tog tio sekunder per körning, femtio för fem -- mätt,
                    # inte gissat: 33 000 tillträden i 12 000 grupper.
                    # groupby.shift(1) ger föregående anställning för samma
                    # individ i ett svep, 0.05 sekunder.
                    par = körning.sort_values(["agent_id", "time"])
                    fore = par.groupby("agent_id", sort=False)[
                        ["w_occ", "w_field", "w_neg"]].shift(1)
                    m = (par["job_to_job"].fillna(False).astype(bool).to_numpy()
                         & fore["w_neg"].notna().to_numpy()
                         & par["w_neg"].notna().to_numpy())
                    if m.any():
                        with np.errstate(divide="ignore", invalid="ignore"):
                            b = np.log(par.loc[m, ["w_occ", "w_field", "w_neg"]]
                                       .to_numpy(dtype=float))
                            a = np.log(fore.loc[m].to_numpy(dtype=float))
                        ok = np.all(np.isfinite(a), axis=1) & np.all(np.isfinite(b), axis=1)
                        a, b = a[ok], b[ok]
                        if len(a):
                            d_occ = b[:, 0] - a[:, 0]
                            d_eta = (b[:, 1] - b[:, 0]) - (a[:, 1] - a[:, 0])
                            d_fit = (b[:, 2] - b[:, 1]) - (a[:, 2] - a[:, 1])
                            row["n_move_decomp"] = int(len(a))
                            row["move_d_occ_mean"] = round(float(d_occ.mean()), 4)
                            row["move_d_eta_mean"] = round(float(d_eta.mean()), 4)
                            row["move_d_fit_mean"] = round(float(d_fit.mean()), 4)
                            if "w_prev" in par.columns:
                                with np.errstate(divide="ignore", invalid="ignore"):
                                    lw_prev = np.log(pd.to_numeric(
                                        par.loc[m, "w_prev"], errors="coerce")
                                        .to_numpy(dtype=float)[ok])
                                giltig = np.isfinite(lw_prev)
                                if giltig.any():
                                    row["move_d_revision_mean"] = round(
                                        float((lw_prev - a[:, 2])[giltig].mean()), 4)
                                    row["move_gain_mean"] = round(
                                        float((b[:, 2] - lw_prev)[giltig].mean()), 4)
            # Yrkesavståndet i svansen: medianen 0.66 döljer enskilda hopp
            # över halva skivan (u_R_occ 2.7 i kedjorna).
            if "u_R_occ" in körning.columns:
                uro = pd.to_numeric(körning["u_R_occ"], errors="coerce").dropna()
                if len(uro):
                    row["u_R_occ_p90"] = round(float(uro.quantile(0.90)), 4)
                    row["share_u_R_occ_above_1"] = round(float((uro > 1.0).mean()), 4)
            # SÖKINTENSITETEN, efter status. Sedan 0088 bär varje sökning sin
            # status; sökningar per personår är det tal parametrarna påstår
            # (365/28 = 13 arbetslös, 13/on_the_job_search_factor anställd)
            # och det som förr var okänt, eftersom kedjor dog och dubblerades.
            searches = [r for r in events if r.get("event") == "start_job_search"
                   and r.get("event_detail") in ("application_filed", "match_failed")
                   and "status" in r]
            if searches and _ar > 0 and len(ts):
                for st in ("employed", "unemployed"):
                    n_st = sum(1 for r in searches if r.get("status") == st)
                    stock = float(ts[st].mean()) if st in ts.columns else 0.0
                    if stock > 0:
                        row[f"searches_per_year_{st}"] = round(n_st / _ar / stock, 3)
            # VAKANSENS 117 DAGAR, DELAD. Stocken är flöde gånger varaktighet,
            # och varaktigheten består av fyra poster som ska summera till
            # samma tal: väntan på första sökanden, fönstret, tiden fram till
            # tillträdet, och de dagar som tillbringas i positioner som ALDRIG
            # tillsätts. Den sista går inte att mäta per vakans -- de har ingen
            # sluthändelse -- men den faller ut som rest: totala vakansdagar
            # minus de dagar de tillsatta positionerna stod öppna.
            vantan = [_f(r, "wait_first_applicant_days") for r in events
                      if r.get("event_detail") == "advert_opened"]
            vantan = [v for v in vantan if v == v]
            if vantan:
                row["wait_first_applicant_median"] = round(float(np.median(vantan)), 1)
                row["wait_first_applicant_mean"] = round(float(np.mean(vantan)), 1)
                row["n_adverts_opened"] = len(vantan)
            beslut = [_f(r, "vacancy_age_at_decision") for r in events
                      if r.get("event_detail") == "match_completed"]
            beslut = [b for b in beslut if b == b]
            if beslut:
                row["vacancy_age_at_decision_median"] = round(float(np.median(beslut)), 1)
            row["n_offers_declined"] = sum(
                1 for r in events if r.get("event_detail") == "offer_declined")
            row["n_all_declined"] = sum(
                1 for r in events if r.get("event_detail") == "vacancy_closed_unfilled"
                and str(r.get("all_declined", "")).lower() == "true")
            row["n_search_superseded"] = sum(
                1 for r in events if r.get("event_detail") == "search_superseded")
            # RESTPOOLEN: vem vinner urvalen
            mc = [r for r in events if r.get("event_detail") == "match_completed"]
            if mc:
                we = [_b(r, "winner_employed") for r in mc]
                row["share_hires_from_employment"] = round(float(np.mean(we)), 4)
                for namn in ("employed", "unemployed"):
                    v = [_f(r, f"q_median_{namn}") for r in mc]
                    v = [x for x in v if x is not None and np.isfinite(x)]
                    if v:
                        row[f"q_applicants_{namn}"] = round(float(np.median(v)), 4)
            # VAKANSERNAS ÅLDER vid tillsättning
            va = pd.to_numeric(körning.get("vacancy_age_days"), errors="coerce").dropna() \
                if "vacancy_age_days" in körning.columns else pd.Series(dtype=float)
            if len(va) > 20:
                row["vacancy_age_median"] = round(float(va.median()), 1)
                row["vacancy_age_p90"] = round(float(va.quantile(0.90)), 1)

            # BESTÅNDET och REVISIONEN loggas på new_year-raderna, inte i
            # transitions. Utan detta stannar de i eventlog.csv och når aldrig
            # tabellerna -- samma väg som n_applicants och theta tappades.
            ny = [r for r in events if r.get("event") == "new_year"]
            for f, agg in (("stock_sd_log_w", "last"),
                           ("stock_share_above_pi", "last"),
                           ("stock_w_p90p10", "last"),
                           ("stock_w_p50", "last"), ("stock_w_p10", "last"),
                           ("stock_w_p90", "last"), ("revision_g_mean", "mean"),
                           ("revision_g_p10", "mean"), ("revision_g_p90", "mean"),
                           ("revision_share_zero", "mean"),
                           ("revision_share_below_mark", "mean"),
                           ("revision_d_bar", "mean"), ("revision_n", "last")):
                v = [_f(r, f) for r in ny]
                v = [x for x in v if x is not None and np.isfinite(x)]
                if v:
                    row[f] = round(float(v[-1] if agg == "last" else np.mean(v)), 5)

            # GLOBAL fördelning: lönenivån över alla yrken, alltså den
            # storhet lönestrukturstatistikens P90/P10 (2.20 för 2025) mäter.
            # Inom yrke är en annan sak och står per kvartil i figurens data.
            wn = pd.to_numeric(tr.get("w_neg"), errors="coerce").dropna()
            wn = wn[wn > 0]
            if len(wn) > 50:
                p10, p90 = wn.quantile(0.10), wn.quantile(0.90)
                row["flow_w_p90p10"] = round(float(p90 / p10), 4)
                row["flow_sd_log_w"] = round(float(np.std(np.log(wn))), 4)
            # Hur stor del av variansen i log lön ligger i ARBETSGIVAREN.
            # AKM ger 10-20 procent; det är kontrollen på employer_wage_sd.
            if "employer_premium" in tr.columns:
                ep = pd.to_numeric(tr["employer_premium"], errors="coerce").dropna()
                ep = ep[ep > 0]
                if len(ep) > 50 and len(wn) > 50:
                    v_eta = float(np.var(np.log(ep)))
                    v_tot = float(np.var(np.log(wn)))
                    row["employer_var_share"] = round(v_eta / v_tot, 4) if v_tot > 0 else np.nan

            na = (tr["n_applicants"].dropna() if "n_applicants" in tr.columns
                  else pd.Series(dtype=float))
            if len(na):
                row["median_applicants"] = round(float(na.median()), 2)
                row["mean_applicants"] = round(float(na.mean()), 3)
                row["share_uncontested"] = round(float((na <= 1).mean()), 4)

            km = tr["commute_km"].dropna() if "commute_km" in tr.columns else pd.Series(dtype=float)
            if len(km):
                row["median_commute_km"] = round(float(km.median()), 2)
                row["p90_commute_km"] = round(float(km.quantile(0.90)), 2)

            # Vakansvaraktighet ur Littles lag: V = flode x varaktighet. Ingen
            # vakans bar en tidsstampel, sa den exakta varaktigheten per
            # position gar inte att mata. Medelstocken over manaderna delat med
            # anstallningar per ar ar rakt fram och giltig i jamvikt, och det
            # ar det matt som avgor v -- och darmed u, eftersom
            # U = L - J + V ger u = u_min + V/L exakt.
            if len(ts) and "vacancies" in ts.columns:
                yrs = float(ts["year"].iloc[-1]) if "year" in ts.columns else 0.0
                # Flödet är KÖRNINGENS tillsättningar. Uppstartens ligger i
                # tr med sin flagga men sker vid t = 0 och är inte ett flöde
                # över tiden; med dem i nämnaren blev varaktigheten en
                # tredjedel för kort.
                n_flow = int((~tr["is_bootstrap"].fillna(False).astype(bool)).sum()) \
                    if "is_bootstrap" in tr.columns else len(tr)
                if yrs > 0 and n_flow:
                    row["mean_vacancies"] = round(float(ts["vacancies"].mean()), 1)
                    row["vacancy_days"] = round(
                        float(ts["vacancies"].mean()) / (n_flow / yrs) * 365.25, 1)
                    # Samma Little, men på de LEDIGA befattningarna: tiden från
                    # utlysning till att rekryteringen är löst, vilket är den
                    # varaktighet SCB:s vakansstatistik mäter. Skillnaden mot
                    # vacancy_days är uppsägningstiden.
                    if "open_vacancies" in ts.columns:
                        row["mean_open_vacancies"] = round(
                            float(ts["open_vacancies"].mean()), 1)
                        row["open_vacancy_days"] = round(
                            float(ts["open_vacancies"].mean()) / (n_flow / yrs) * 365.25, 1)
                    # Resten av vakansdagarna: de som tillbringas i positioner
                    # som ALDRIG tillsätts. De har ingen sluthändelse och går
                    # inte att mäta per vakans, men faller ut som rest -- totala
                    # vakansdagar minus de dagar de tillsatta stod öppna.
                    if "vacancy_age_days" in tr.columns:
                        alder = pd.to_numeric(
                            tr.loc[~tr["is_bootstrap"].fillna(False).astype(bool),
                                   "vacancy_age_days"], errors="coerce").dropna()
                        totala = float(ts["vacancies"].mean()) * yrs * 365.25
                        if totala > 0 and len(alder):
                            row["vacancy_days_share_unfilled"] = round(
                                max(0.0, 1.0 - float(alder.sum()) / totala), 4)

            if "r_req" in cps.columns and cps["r_req"].notna().any():
                # Det avslöjande måttet: låg q i jobb med högt krav.
                hi = cps[cps["r_req"] >= 0.6]
                if len(hi):
                    row["share_lowq_in_demanding"] = round(
                        float((hi["q_hire"] < 0.40).mean()), 4)
                    row["n_demanding_hires"] = int(len(hi))

    # Täckning ur sluttillståndet, om det finns
    jp = os.path.join(run_dir, "final_state_jobs.csv")
    if os.path.isfile(jp):
        jobs = pd.read_csv(jp, usecols=lambda c: c in
                           ("x_occ", "y_occ", "active", "individual_id", "municipal_code"))
        if {"x_occ", "y_occ"} <= set(jobs.columns):
            if "active" in jobs.columns:
                jobs = jobs[jobs["active"].astype(bool)]
            for s in (0.15, 0.25):
                row[f"coverage_{s}"] = round(coverage(jobs["x_occ"].to_numpy(),
                                                      jobs["y_occ"].to_numpy(), s), 4)
    return row


def coverage(x, y, s, n_r=120, n_t=240):
    """Ytandel av enhetsskivan inom avståndet s från någon position.

    Polärt rutnät viktat med r, eftersom cellerna har arean r*dr*dtheta.
    Samma definition som figurerna använder.
    """
    x = x[np.isfinite(x)]; y = y[np.isfinite(y)]
    if x.size == 0:
        return np.nan
    tg, rg = np.meshgrid(np.linspace(0, 2 * np.pi, n_t), np.linspace(0, 1.0, n_r))
    gx, gy = rg * np.cos(tg), rg * np.sin(tg)
    covered = np.zeros(gx.shape, dtype=bool)
    for st in range(0, x.size, 400):
        bx, by = x[st:st + 400], y[st:st + 400]
        d2 = (gx[..., None] - bx) ** 2 + (gy[..., None] - by) ** 2
        covered |= (d2.min(axis=-1) <= s * s)
    return float((covered * rg).sum() / rg.sum())


# ---------------------------------------------------------------------------
def export(run_dir, out_dir=None):
    """Skriver transitions, timeseries, flows och summary till tables/."""
    out_dir = out_dir or os.path.join(run_dir, "tables")
    os.makedirs(out_dir, exist_ok=True)
    events = read_events(run_dir)
    tr = transitions_table(events)
    ts = timeseries_table(events)
    fl = flows_table(events)
    row = summary_row(run_dir, events, tr, ts)

    tr.to_csv(os.path.join(out_dir, "transitions.csv"), index=False)
    ts.to_csv(os.path.join(out_dir, "timeseries.csv"), index=False)
    fl.to_csv(os.path.join(out_dir, "flows.csv"), index=False)
    pd.DataFrame([row]).to_csv(os.path.join(out_dir, "summary.csv"), index=False)
    return {"transitions": tr, "timeseries": ts, "flows": fl, "summary": row,
            "out_dir": out_dir}


def load_tables(run_dir):
    """Läser exporterade tabeller, eller skapar dem om de saknas."""
    t = os.path.join(run_dir, "tables")
    if not os.path.isfile(os.path.join(t, "transitions.csv")):
        return export(run_dir)
    return {"transitions": pd.read_csv(os.path.join(t, "transitions.csv")),
            "timeseries": pd.read_csv(os.path.join(t, "timeseries.csv")),
            "flows": pd.read_csv(os.path.join(t, "flows.csv")),
            "summary": pd.read_csv(os.path.join(t, "summary.csv")).iloc[0].to_dict(),
            "out_dir": t}


# ---------------------------------------------------------------------------
# Serier av körningar
# ---------------------------------------------------------------------------
def collect_runs(run_dirs):
    """Summary för flera körningar som en DataFrame.

    Med flera frön per scenario är en enskild körning inte ett resultat.
    Spridningen inom scenario måste kunna skiljas från skillnaden mellan
    scenarier, annars tolkas brus som effekt."""
    rows = []
    for rd in run_dirs:
        try:
            rows.append(summary_row(rd))
        except Exception as e:
            print(f"hoppar över {os.path.basename(str(rd))}: {type(e).__name__}: {e}")
    return pd.DataFrame(rows)


def group_stats(df, by="scenario", metrics=None):
    """Median och spridning per grupp, samt antal frön.

    Redovisar interkvartilavstånd snarare än standardavvikelse: med få frön är
    medianen robustare och IQR säger mer om var utfallen faktiskt ligger."""
    metrics = metrics or [c for c in
                          ("u_pct", "v_pct", "tightness", "median_u_R",
                           "median_wage_ratio", "coverage_0.25", "share_same_occ")
                          if c in df.columns]
    if by not in df.columns:
        df = df.assign(**{by: "alla"})
    out = []
    for key, g in df.groupby(by, dropna=False):
        row = {by: key, "n_runs": len(g),
               "seeds": ",".join(map(str, sorted(g["seed"].dropna().astype(int))))
               if "seed" in g else ""}
        for m in metrics:
            x = pd.to_numeric(g[m], errors="coerce").dropna()
            if x.empty:
                continue
            row[f"{m}_median"] = float(x.median())
            row[f"{m}_q25"] = float(x.quantile(0.25))
            row[f"{m}_q75"] = float(x.quantile(0.75))
            row[f"{m}_min"] = float(x.min())
            row[f"{m}_max"] = float(x.max())
        out.append(row)
    return pd.DataFrame(out)


def pooled_transitions(run_dirs, cps_only=True):
    """Övergångar från flera körningar i en tabell, med run-kolumn.

    Med fem frön ska en fördelningsfigur visa bandet, inte ett godtyckligt
    frö."""
    frames = []
    for rd in run_dirs:
        try:
            tr = load_tables(rd)["transitions"]
        except Exception:
            continue
        if tr.empty:
            continue
        if cps_only and "in_cps_sample" in tr.columns:
            tr = tr[tr["in_cps_sample"].fillna(False).astype(bool)]
        tr = tr.copy()
        tr["run"] = os.path.basename(str(rd).rstrip("/"))
        frames.append(tr)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def ecdf_band(values_by_run, grid=None, lo=0.0, hi=3.5, n=200):
    """Median-CDF och band över körningar.

    values_by_run : dict run -> array. Returnerar DataFrame med x, median,
    q25, q75, min, max -- alltså den serie en bandfigur ritar och som skrivs
    bredvid den."""
    grid = grid if grid is not None else np.linspace(lo, hi, n)
    curves = []
    for arr in values_by_run.values():
        a = np.asarray(arr, dtype=float)
        a = a[np.isfinite(a)]
        if a.size:
            curves.append(np.searchsorted(np.sort(a), grid, side="right") / a.size)
    if not curves:
        return pd.DataFrame()
    M = np.vstack(curves)
    return pd.DataFrame({"x": grid,
                         "median": np.median(M, axis=0),
                         "q25": np.percentile(M, 25, axis=0),
                         "q75": np.percentile(M, 75, axis=0),
                         "min": M.min(axis=0), "max": M.max(axis=0),
                         "n_runs": M.shape[0]})
