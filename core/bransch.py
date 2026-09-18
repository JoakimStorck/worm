"""Arbetsställenas bransch och storlek.

Arbetsgivarnas bransch drogs tidigare ur employment_municipality_sni, en
handbyggd fil utan hämtning där talen var avrundade till femtiotal, Mora
hade 4 250 anställda i stället för drygt 10 000, och offentlig förvaltning
och utbildning var noll. Branschen drogs dessutom i proportion till antalet
ARBETSSTÄLLEN och oberoende av storleken, så handelns småbutiker fick lika
stora arbetsgivare som allt annat. Mora fick 47 procent av jobben i handel
och inga i vård och omsorg, mot 10 och 23 procent bland invånarna.

Nu följer JOBBEN kommunens branschfördelning, och storleken dras givet
branschen:

- Kommunens branschfördelning är employment_deso_sni summerad över
  kommunens DeSO-områden: sysselsatta invånare per bransch
  (nattbefolkning). Arbetsställena ligger i dagbefolkningen, så det är en
  approximation, men den enda källan i databasen som är hel.
- P(storleksklass | bransch) är rikets fördelning av anställda över
  arbetsställets storleksklass, ur yrkesregistret (occupation_by_industry).
  Branschgrupperna är desamma i båda tabellerna (B+C, D+E, M+N, R+S+T+U).
- Kommunens jobbmål fördelas först på branscherna, och arbetsställen dras
  inom varje bransch tills dess mål är fyllt. Att dra bransch per
  arbetsställe gav en brusig fördelning i en liten kommun: ett enda
  arbetsställe med 938 anställda flyttade nio procentenheter.
- Inom en bransch dras storleksklassen med sannolikheten P(klass |
  bransch) / medelstorlek(klass). Då följer andelen JOBB per klass rikets
  fördelning, och antalet arbetsställen blir ett utfall.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Registrets storleksklasser. Den öppna klassen stängs av scenariots
# workplace_max_size, och storleken dras log-likformigt inom den: anställda
# per arbetsställe är skevt fördelade, och en likformig dragning upp till
# tusen hade gjort 100+-klassens medel till 550.
STORLEKSKLASSER = (
    ("1-4 anställda", 1, 4),
    ("5-9 anställda", 5, 9),
    ("10-19 anställda", 10, 19),
    ("20-49 anställda", 20, 49),
    ("50-99 anställda", 50, 99),
    ("100+ anställda", 100, None),
)

# "Uppgift saknas" bär ingen information om bransch. Ett arbetsställe måste
# ha en bransch, så andelen fördelas om över de kända.
OKANDA = {"US", "TOTAL"}

HAMTA = ("Tabellerna byggs av scripts/create_database.py: employment_deso_sni "
         "ur data/scb_sysselsatta_deso.csv och occupation_by_industry ur "
         "yrkesregistret (data/TAB4347_sv.csv).")


def storleksklass(n: int) -> str:
    for namn, lo, hi in STORLEKSKLASSER:
        if n >= lo and (hi is None or n <= hi):
            return namn
    raise ValueError(f"storleken {n} ligger i ingen storleksklass")


class Branschstruktur:
    def __init__(self, conn, max_storlek: int):
        if max_storlek is None or int(max_storlek) < 100:
            raise ValueError("workplace_max_size måste anges och vara minst 100: "
                             "den stänger storleksklassen 100+.")
        self.conn = conn
        self.max_storlek = int(max_storlek)
        for tabell in ("occupation_by_industry", "employment_deso_sni"):
            finns = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                 "AND name=?", (tabell,)).fetchone()
            if finns is None:
                raise ValueError(f"Tabellen {tabell} saknas. " + HAMTA)
        riket = pd.read_sql("SELECT sni_code, size_class, SUM(employed) AS e "
                            "FROM occupation_by_industry GROUP BY 1, 2", conn)
        klasser = [k for k, _, _ in STORLEKSKLASSER]
        okanda_klasser = set(riket["size_class"]) - set(klasser)
        if okanda_klasser:
            raise ValueError(f"occupation_by_industry har okända storleksklasser "
                             f"{sorted(okanda_klasser)}")
        p = riket.pivot(index="sni_code", columns="size_class", values="e")
        p = p.reindex(columns=klasser).fillna(0.0)
        self.p_klass = p.div(p.sum(axis=1), axis=0)
        self.medel = np.array([self._medelstorlek(lo, hi) for _, lo, hi in STORLEKSKLASSER])

    def _medelstorlek(self, lo, hi):
        if hi is not None:
            return (lo + hi) / 2.0
        return (self.max_storlek - lo) / np.log(self.max_storlek / lo)

    def branschandelar(self, municipal_code) -> pd.Series:
        """Kommunens andel sysselsatta per bransch, okända borträknade."""
        df = pd.read_sql("SELECT sni_code, SUM(employed) AS e FROM employment_deso_sni "
                         "WHERE substr(deso_code, 1, 4) = ? GROUP BY 1",
                         self.conn, params=(str(municipal_code).zfill(4),))
        df = df[~df["sni_code"].astype(str).str.upper().isin(OKANDA)]
        df = df[df["e"] > 0]
        if df.empty:
            raise ValueError(f"employment_deso_sni saknar kommun {municipal_code}. " + HAMTA)
        saknas = sorted(set(df["sni_code"]) - set(self.p_klass.index))
        if saknas:
            raise ValueError(f"Branscherna {saknas} i employment_deso_sni saknas i "
                             "occupation_by_industry; branschgrupperna ska vara desamma.")
        s = df.set_index("sni_code")["e"].astype(float)
        return s / s.sum()

    def jobb_per_bransch(self, municipal_code, target_jobs: int) -> pd.Series:
        """Heltal per bransch som summerar till target_jobs (största rest)."""
        andel = self.branschandelar(municipal_code)
        exakt = andel * int(target_jobs)
        heltal = np.floor(exakt).astype(int)
        rest = int(target_jobs) - int(heltal.sum())
        if rest > 0:
            ordning = np.argsort(-(exakt - heltal).to_numpy(), kind="stable")[:rest]
            heltal.iloc[ordning] += 1
        return heltal

    def dra_storlek(self, bransch, rng) -> int:
        q = self.p_klass.loc[bransch].to_numpy() / self.medel
        q = q / q.sum()
        _, lo, hi = STORLEKSKLASSER[int(rng.choice(len(q), p=q))]
        if hi is not None:
            return int(rng.integers(lo, hi + 1))
        return int(np.exp(rng.uniform(np.log(lo), np.log(self.max_storlek + 1))))

    def dra_arbetsstallen(self, municipal_code, target_jobs: int, rng):
        """Lista av (bransch, storlek). Det sista arbetsstället i varje bransch
        kapas så att branschens jobbmål träffas exakt."""
        ut = []
        for bransch, mal in self.jobb_per_bransch(municipal_code, target_jobs).items():
            n = 0
            while n < mal:
                storlek = min(self.dra_storlek(bransch, rng), mal - n)
                ut.append((bransch, storlek))
                n += storlek
        return ut
