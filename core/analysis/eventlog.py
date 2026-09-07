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
            "occ_change": bool(int(r.get("occ_change", 1))) if "occ_change" in r else np.nan,
            "is_mgmt": (src.startswith(MGMT_PREFIX) or tgt.startswith(MGMT_PREFIX))
                       if (src or tgt) else np.nan,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["wage_ratio"] = df["w_neg"] / df["w_field"].replace(0, np.nan)
        # Det urval CPS jämförs mot: yrkesbyten utan chefsövergångar.
        df["in_cps_sample"] = (df["occ_change"].fillna(False).astype(bool)
                               & ~df["is_mgmt"].fillna(False).astype(bool))
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
            "active_jobs": J, "posted": _f(r, "posted"),
            "not_in_labour_force": _f(r, "not_in_labour_force"),
            "labour_force": L,
            "u": 100 * unemp / L if L else np.nan,
            "v": 100 * vac / J if J else np.nan,
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
