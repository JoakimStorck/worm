#!/usr/bin/env python3
"""Individkedjor ur eventloggen: hur ser en stege ut i praktiken?

Aggregaten säger att 64 procent av dem som anställs ur arbetslöshet byter
igen, median 354 dagar senare, med +15 procent. Det här skriptet visar
enskilda individers hela historia i kronologisk ordning -- sökningar,
ansökningar, vem som vann vakansen och med vilken q, tillträden med lön
mot yrkets Pi, uppsägningstider, förstörelser -- så att kedjan kan läsas
som en berättelse och inte som en ratio.

    python scripts/individual_history.py output/run_X                 # 5 stegare
    python scripts/individual_history.py output/run_X --min-steps 3
    python scripts/individual_history.py output/run_X --agent 4711 812
    python scripts/individual_history.py output/run_X --displaced      # förstörda

Urvalet utan --agent: slumpmässigt bland dem med minst --min-steps byten
(default 2), frö --seed. Med --displaced i stället bland dem som förlorat
jobbet genom förstörelse. Yrkestitlar hämtas ur data/worm.sqlite3
(onet_occupations) om den finns, annars visas koden.
"""
import argparse
import glob
import os
import random
import sqlite3
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.analysis.eventlog import read_events, _b, _f  # noqa: E402

WINDOW_DAYS = 45.0   # 40 dagars annonsering plus marginal


def _resolve_run_dir(given):
    """Hittar körningen även när den arkiverats.

    kor_0077.sh flyttar körningar från andra commits till output/arkiv/, så
    en sökväg som fungerade i går ger FileNotFoundError i dag. Katalognamnet
    är unikt, så det räcker att leta upp det: först som angiven, sedan under
    output/arkiv/, sedan var som helst under output/."""
    if os.path.isfile(os.path.join(given, "eventlog.csv")):
        return given
    namn = os.path.basename(os.path.normpath(given))
    for kandidat in (os.path.join("output", "arkiv", namn),
                     os.path.join("output", namn)):
        if os.path.isfile(os.path.join(kandidat, "eventlog.csv")):
            return kandidat
    träffar = sorted(glob.glob(os.path.join("output", "**", namn, "eventlog.csv"),
                               recursive=True))
    if träffar:
        return os.path.dirname(träffar[0])
    nara = sorted(os.path.basename(os.path.dirname(p))
                  for p in glob.glob(os.path.join("output", "**", "eventlog.csv"),
                                     recursive=True))
    raise SystemExit(f"Ingen eventlog.csv för {given}.\n"
                     + ("Körningar som finns: " + ", ".join(nara[-8:]) if nara
                        else "Inga körningar hittades under output/."))


def _titles(db_path):
    if not os.path.isfile(db_path):
        return {}
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT onet_code, title FROM onet_occupations").fetchall()
        conn.close()
    except sqlite3.Error:
        return {}
    return {c: t for c, t in rows}


def _day_label(t):
    year = int(t // 365.25) + 1
    day = int(t - (year - 1) * 365.25)
    return f"år {year:2d} dag {day:3d}"


def _occupation(kod, titles):
    if kod is None or kod == "None":
        return "-"
    t = titles.get(kod)
    if not t:
        return kod
    t = t.split(",")[0].split("(")[0].strip()
    return f"{t} [{kod}]"


def _same_agent(a, b):
    """Samma individ? Loggar FÖRE 0092 har två former för agent_id --
    individual_id (2062_i003443) på ansökan och DataFrame-indexet (3443) på
    match_completed -- så individens EGNA vinster lästes som förluster mot en
    okänd. Numerisk svans jämförs därför också, så att gamla körningar går att
    läsa utan att simuleras om. Nya loggar har en form och träffar direkt."""
    if a is None or b is None:
        return False
    a, b = str(a).strip(), str(b).strip()
    if a == b:
        return True
    tail_a = a.rsplit("_i", 1)[-1].lstrip("0") or "0"
    tail_b = b.rsplit("_i", 1)[-1].lstrip("0") or "0"
    return tail_a.isdigit() and tail_b.isdigit() and tail_a == tail_b


def _vacancy_outcome(application, vacancy_outcomes):
    """Vad hände med vakansen efter ansökan: vann / förlorade mot / ingen /
    förstörd. vacancy_outcomes: job_id -> lista av (tid, line)."""
    job_id_, t = application.get("job_id"), application["time"]
    for t_out, r in vacancy_outcomes.get(job_id_, []):
        if t < t_out <= t + WINDOW_DAYS:
            d = r.get("event_detail")
            if d == "match_completed":
                if _same_agent(r.get("agent_id"), application.get("agent_id")):
                    return "VANN", r
                return f"förlorade mot {r.get('agent_id')} (q {r.get('q_hire')})", r
            if d == "vacancy_closed_unfilled":
                return "ingen anställdes", r
            if d == "vacancy_destroyed":
                return "vakansen förstördes", r
    return "utfall saknas i loggen", None


def _history_lines(aid, events_by_agent, vacancy_outcomes, titles):
    rows = events_by_agent.get(aid, [])
    ut = []
    n_dry = 0

    def flush_dry(t):
        nonlocal n_dry
        if n_dry:
            ut.append(f"  {'':16s}  ... {n_dry} sökning(ar) utan ansökan")
            n_dry = 0

    for r in sorted(rows, key=lambda x: x["time"]):
        t, ev, d = r["time"], r["event"], r.get("event_detail")
        if ev == "start_job_search":
            if d == "match_failed":
                n_dry += 1
                continue
            if d == "search_superseded":
                continue
            if d == "application_filed":
                flush_dry(t)
                outcome, _ = _vacancy_outcome(r, vacancy_outcomes)
                ut.append(f"  {_day_label(t)}  SÖKER som {r.get('status', '?'):10s} "
                          f"ansöker {r.get('job_id')}  w {r.get('w_neg')}  "
                          f"q {r.get('q_hire')}  överskott {r.get('surplus')}  "
                          f"{r.get('commute_km')} km  -> {outcome}")
                continue
        if ev == "close_vacancy" and d == "quit_job":
            flush_dry(t)
            ut.append(f"  {_day_label(t)}  SÄGER UPP SIG från {r.get('job_id')} "
                      f"för {r.get('to_job_id')}, {r.get('notice_days')} dagars uppsägning")
            continue
        if ev == "close_vacancy" and d == "match_completed":
            continue   # står redan som VANN på ansökan
        if ev == "start_job":
            flush_dry(t)
            is_boot = _b(r, "is_bootstrap")
            jtj = _b(r, "job_to_job")
            w, wo, wp = _f(r, "w_neg"), _f(r, "w_occ"), _f(r, "w_prev")
            ratio = f"{w / wo:.3f} × Π_o" if wo == wo and wo else ""
            gain = f"  vinst {100 * (w / wp - 1):+.1f} %" if wp == wp and wp else ""
            kind = "UPPSTART" if is_boot else ("BYTE" if jtj else "ANSTÄLLS ur arbetslöshet")
            ut.append(f"  {_day_label(t)}  {kind}: {r.get('job_id')}  "
                      f"{_occupation(r.get('to_onet'), titles)}  lön {w:.3f} = {ratio}"
                      f"{gain}  q {r.get('q_hire')}  u_R_occ {r.get('u_R_occ', '-')}"
                      + (f"  {r.get('n_applicants')} sökande" if r.get("n_applicants") else ""))
            continue
        if ev == "destroy_job" and d == "job_destroyed_holder_displaced":
            flush_dry(t)
            ut.append(f"  {_day_label(t)}  FÖRLORAR JOBBET: {r.get('job_id')} förstörs")
            continue
        if ev == "start_job" or d in ("job_gone_before_start",
                                      "job_gone_before_start_kept_previous"):
            flush_dry(t)
            ut.append(f"  {_day_label(t)}  {d}: {r.get('job_id')}")
            continue
        if d in ("education_started", "education_finished", "education_no_target",
                 "education_finished_already_employed"):
            flush_dry(t)
            ut.append(f"  {_day_label(t)}  UTBILDNING: {d}")
            continue
    flush_dry(None)
    return ut


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--agent", nargs="*", help="individ-id (agent_id i loggen)")
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--min-steps", type=int, default=2, help="minsta antal byten")
    ap.add_argument("--displaced", action="store_true",
                    help="välj bland dem som förlorat jobbet genom förstörelse")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--db", default="data/worm.sqlite3")
    args = ap.parse_args()

    events = read_events(_resolve_run_dir(args.run_dir))
    titles = _titles(args.db)

    events_by_agent = defaultdict(list)
    vacancy_outcomes = defaultdict(list)
    for r in events:
        aid = r.get("agent_id")
        if aid not in (None, "None"):
            events_by_agent[aid].append(r)
        if r.get("event") in ("close_vacancy", "destroy_job") and r.get("job_id"):
            vacancy_outcomes[r["job_id"]].append((r["time"], r))

    if args.agent:
        chosen = list(args.agent)
    else:
        rng = random.Random(args.seed)
        if args.displaced:
            candidates = [aid for aid, rs in events_by_agent.items()
                          if any(r.get("event_detail") == "job_destroyed_holder_displaced"
                                 for r in rs)]
        else:
            candidates = [aid for aid, rs in events_by_agent.items()
                    if sum(1 for r in rs if r.get("event") == "start_job"
                           and _b(r, "job_to_job")) >= args.min_steps]
        candidates.sort()
        chosen = rng.sample(candidates, min(args.n, len(candidates)))
        print(f"{len(candidates)} individer uppfyller urvalet; visar {len(chosen)} (frö {args.seed})\n")

    for aid in chosen:
        rows = events_by_agent.get(aid)
        if not rows:
            print(f"== individ {aid}: inga händelser i loggen\n")
            continue
        n_moves = sum(1 for r in rows if r.get("event") == "start_job" and _b(r, "job_to_job"))
        n_searches = sum(1 for r in rows if r.get("event") == "start_job_search"
                    and r.get("event_detail") in ("application_filed", "match_failed"))
        n_applications = sum(1 for r in rows if r.get("event_detail") == "application_filed")
        print(f"== individ {aid}: {n_moves} byten, {n_applications} ansökningar av {n_searches} sökningar")
        for line in _history_lines(aid, events_by_agent, vacancy_outcomes, titles):
            print(line)
        print()


if __name__ == "__main__":
    main()
