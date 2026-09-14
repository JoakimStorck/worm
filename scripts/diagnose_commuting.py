"""
diagnose_commuting.py  (scripts/)
---------------------------------
Dag- mot nattbefolkning per kommun, och pendlingsflödena, modell mot SCB.

Pendlingen i modellen är symmetrisk per konstruktion. scenariobuilder sätter

    target_jobs = workforce - n_unemployed

per kommun, alltså exakt lika många jobb som kommunen har sysselsatta
invånare. Nettopendlingen blir därmed noll i varje kommun och det enda som
kan uppstå är symmetriska bruttoflöden. I SCB:s tal för Mora, Orsa och
Rättvik är Mora en arbetsplatskommun och Orsa en utpendlingskommun, och den
skillnaden går inte att kalibrera fram med commute_cost_per_km: den kan skala
bruttoflödena men inte skapa ett netto.

Skriptet mäter felet innan något ändras, så att en senare omläggning av
target_jobs har en baslinje att jämföras mot. Det ändrar ingenting.

TVÅ MÅTT, eftersom de fångar olika fel:

  DAG/NATT   jobb i kommunen delat med sysselsatta boende i kommunen.
             Modellen ger 1.00 överallt per konstruktion. Avvikelsen från
             SCB:s kvot är storleken på den saknade frihetsgraden.

  FLÖDEN     varje riktning för sig, och asymmetrin i varje par. Ett par med
             rätt summa men fel riktning är ett annat fel än ett par med rätt
             riktning och fel nivå, och åtgärderna skiljer sig.

STÄNGNINGEN ÄR EN APPROXIMATION och rapporteras som sådan. Modellen känner
bara scenariots kommuner, så en Rättviksbo som i verkligheten pendlar till
Leksand eller Falun måste i modellen antingen stanna eller ta ett av de tre
alternativen. SCB-talen avgränsas till samma tre kommuner för att jämförelsen
ska vara rättvis, men andelen av kommunens verkliga utpendling som därmed
faller utanför skrivs ut: är den stor är kommunen ett svagt testfall oavsett
hur väl modellen träffar.

    python scripts/diagnose_commuting.py                 # senaste körningen
    python scripts/diagnose_commuting.py output/run_A
"""
import argparse
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.analysis.eventlog import read_events  # noqa: E402

DB = "data/worm.sqlite3"


def _senaste(outdir="output"):
    kand = [os.path.join(outdir, d) for d in sorted(os.listdir(outdir))
            if os.path.isfile(os.path.join(outdir, d, "eventlog.csv"))]
    if not kand:
        raise SystemExit("Ingen körning med eventlog.csv under output/.")
    return kand[-1]


def _kommuner(run_dir):
    import json
    p = os.path.join(run_dir, "run_meta.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            m = json.load(f)
        return [str(k) for k in (m.get("municipalities") or [])]
    return []


def modellens_flode(run_dir):
    """Slutläget: var individerna bor mot var de arbetar.

    Tas ur final_state, inte ur tillsättningarna. share_hires_cross_municipality
    är ett FLÖDE och SCB:s matris en STOCK; ska de två jämföras måste modellens
    sida också vara en stock, annars mäter kvoten skillnaden mellan flöde och
    stock lika mycket som skillnaden mellan modell och verklighet.
    """
    ind = pd.read_csv(os.path.join(run_dir, "final_state_individuals.csv"))
    jobb = pd.read_csv(os.path.join(run_dir, "final_state_jobs.csv"))
    jobbkom = dict(zip(jobb["job_id"].astype(str),
                       jobb["municipal_code"].astype(str)))
    ut = {}
    for iid, jid in zip(ind["individual_id"].astype(str),
                        ind.get("job_id", pd.Series(dtype=object))):
        if pd.isna(jid):
            continue
        hem = str(iid).split("_i", 1)[0]
        arb = jobbkom.get(str(jid))
        if arb:
            ut[(hem, arb)] = ut.get((hem, arb), 0) + 1
    return ut


def scb_flode(koder, db_path=DB):
    if not os.path.isfile(db_path):
        return {}, None
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql("SELECT * FROM commuting", conn)
        conn.close()
    except Exception:
        return {}, None
    df["home_municipality"] = df["home_municipality"].astype(str)
    df["work_municipality"] = df["work_municipality"].astype(str)
    ar = int(df["year"].max()) if "year" in df and df["year"].notna().any() else None
    if ar is not None:
        df = df[df["year"] == ar]
    hela = df[df["home_municipality"].isin(koder)]
    inom = hela[hela["work_municipality"].isin(koder)]
    flode = {(r.home_municipality, r.work_municipality): int(r.employed)
             for r in inom.itertuples()}
    # Hur stor del av kommunens utpendling som går utanför scenariot.
    utanfor = {}
    for k in koder:
        alla = hela[hela["home_municipality"] == k]["employed"].sum()
        i = inom[inom["home_municipality"] == k]["employed"].sum()
        utanfor[k] = float(1 - i / alla) if alla else np.nan
    return flode, (ar, utanfor)


def _dagnatt(flode, koder):
    natt = {k: sum(v for (h, _), v in flode.items() if h == k) for k in koder}
    dag = {k: sum(v for (_, a), v in flode.items() if a == k) for k in koder}
    return dag, natt


def main():
    p = argparse.ArgumentParser(description="Pendling: modell mot SCB.")
    p.add_argument("run_dir", nargs="?", default=None)
    p.add_argument("--db", default=DB)
    a = p.parse_args()
    run_dir = a.run_dir or _senaste()

    koder = _kommuner(run_dir)
    if len(koder) < 2:
        raise SystemExit("Scenariot har färre än två kommuner: pendling går "
                         "inte att pröva.")

    mod = modellens_flode(run_dir)
    scb, meta = scb_flode(koder, a.db)
    if not scb:
        raise SystemExit("Tabellen commuting saknas eller täcker inte "
                         "scenariots kommuner. Ladda den med "
                         "core.database.load_commuting_matrix.")
    ar, utanfor = meta

    namn = {}
    try:
        conn = sqlite3.connect(a.db)
        for kod, n in conn.execute(
                "SELECT municipal_code, municipality FROM municipalities"):
            namn[str(kod)] = n
        conn.close()
    except Exception:
        pass
    n = lambda k: namn.get(k, k)  # noqa: E731

    print(f"\nKörning: {os.path.basename(run_dir.rstrip('/'))}   "
          f"SCB: {ar}   kommuner: {', '.join(n(k) for k in koder)}\n")

    # --- DAG/NATT ---
    md, mn = _dagnatt(mod, koder)
    sd, sn = _dagnatt(scb, koder)
    print("Jobb per sysselsatt invånare (dag/natt), inom scenariots kommuner")
    print(f"{'kommun':<12}{'modell':>9}{'SCB':>9}{'diff':>9}")
    for k in koder:
        m = md[k] / mn[k] if mn[k] else np.nan
        s = sd[k] / sn[k] if sn[k] else np.nan
        print(f"{n(k):<12}{m:>9.2f}{s:>9.2f}{m - s:>+9.2f}")
    print("  Modellen ger 1.00 per konstruktion: target_jobs = workforce - "
          "n_unemployed,\n  alltså lika många jobb som sysselsatta invånare i "
          "varje kommun.\n")

    # --- FLÖDEN ---
    print("Flöden över kommungräns")
    print(f"{'riktning':<26}{'modell':>9}{'SCB':>9}{'kvot':>8}")
    par = [(h, aa) for h in koder for aa in koder if h != aa]
    for h, aa in sorted(par, key=lambda x: -scb.get(x, 0)):
        m, s = mod.get((h, aa), 0), scb.get((h, aa), 0)
        kvot = m / s if s else np.nan
        print(f"{n(h) + ' → ' + n(aa):<26}{m:>9d}{s:>9d}{kvot:>8.2f}")

    print("\nAsymmetri per par (större riktning delat med mindre)")
    print(f"{'par':<26}{'modell':>9}{'SCB':>9}")
    sedda = set()
    for h, aa in par:
        if (aa, h) in sedda:
            continue
        sedda.add((h, aa))
        mm = sorted([mod.get((h, aa), 0), mod.get((aa, h), 0)])
        ss = sorted([scb.get((h, aa), 0), scb.get((aa, h), 0)])
        km = mm[1] / mm[0] if mm[0] else np.nan
        ks = ss[1] / ss[0] if ss[0] else np.nan
        print(f"{n(h) + ' ↔ ' + n(aa):<26}{km:>9.2f}{ks:>9.2f}")
    print("  En kvot nära 1.00 är ett symmetriskt par. Modellens värden ligger "
          "där\n  av samma skäl som dag/natt ligger på 1.00.\n")

    # --- STÄNGNINGEN ---
    print("Andel av kommunens verkliga utpendling som faller utanför scenariot")
    for k in koder:
        print(f"  {n(k):<12}{100 * utanfor[k]:>6.1f} %")
    print("  Modellen känner bara scenariots kommuner. En kommun med hög andel "
          "här\n  är ett svagt testfall oavsett hur väl modellen träffar de "
          "flöden som finns.\n")


if __name__ == "__main__":
    main()
