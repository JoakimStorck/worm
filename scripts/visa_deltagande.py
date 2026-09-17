#!/usr/bin/env python
"""Visar deltagandeprofilen per kommun, innan den används till något.

    python scripts/visa_deltagande.py 2062 2034 2039
    python scripts/visa_deltagande.py 2062 --riktalder 65 67 69

Profilen byggs av BAS femårsgrupper plus 65 år ur differensen mellan
aggregaten, och ovanför 65 av ett antagande med riktåldern som parameter.
Kolumnen "personer" är q(a) gånger folkmängden i årskullen, alltså hur många
modellen lägger i arbetskraften vid den åldern.
"""
import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from core.participation import profil, utträdeshasard

DB = os.path.join("data", "worm.sqlite3")


def las(conn, kod, ar):
    rader = pd.read_sql(
        "SELECT age_group, in_labour_force, total FROM labour_force_by_age "
        "WHERE municipal_code = ? AND year = ?", conn, params=(kod, ar))
    bef = pd.read_sql(
        "SELECT age, n_total FROM population_by_age "
        "WHERE municipal_code = ? AND year = ?", conn, params=(kod, ar))
    if rader.empty or bef.empty:
        raise SystemExit(f"Saknar data för kommun {kod} år {ar}")
    return rader, bef.set_index("age")["n_total"].astype(float)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kommuner", nargs="+")
    ap.add_argument("--ar", type=int, default=2024)
    ap.add_argument("--riktalder", type=float, nargs="+", default=[67.0])
    ap.add_argument("--bredd", type=float, default=0.8)
    a = ap.parse_args()

    conn = sqlite3.connect(DB)
    for kod in a.kommuner:
        rader, bef = las(conn, kod, a.ar)
        print(f"\n===== kommun {kod}, {a.ar}")
        for R in a.riktalder:
            q = profil(rader, bef, retirement_age=R, retirement_spread=a.bredd)
            h = utträdeshasard(q)
            arbetskraft = (q * bef.reindex(q.index).fillna(0.0)).sum()
            print(f"\n  riktålder {R:.0f}, bredd {a.bredd}: "
                  f"arbetskraft {arbetskraft:.0f}")
            print("   ålder  deltagande  personer  utträde")
            for alder in list(range(16, 26, 2)) + list(range(30, 60, 10)) + \
                    list(range(60, 75)):
                n = float(bef.get(alder, 0.0))
                mark = "  <- data slutar" if alder == 65 else ""
                print(f"   {alder:5d}      {q[alder]:.3f}    {q[alder] * n:6.0f}"
                      f"    {h[alder]:.3f}{mark}")
    conn.close()


if __name__ == "__main__":
    main()
