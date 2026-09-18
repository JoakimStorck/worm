"""Omgivningen: regionens öppna rand (docs/omgivning.md).

Det här är underlaget, steg O1: flödena över randen ur pendlingsmatrisen och
platserna i omgivningen. Ingen mekanism använder det ännu.

FLÖDENA. Pendlingsmatrisen (tabellen commuting, SCB, senaste året) täcker alla
290 × 290 kommuner. För en region -- scenariots kommuner -- delas den i tre:
flödena inom regionen, utpendlingen från regionens kommuner till kommuner
utanför, och inpendlingen till regionens kommuner från kommuner utanför.
Kolumnsumman är alla sysselsatta med arbetsställe i kommunen, inklusive
inpendlarna; radsumman alla sysselsatta invånare, inklusive utpendlarna.

PLATSERNA. En pendlare utanför regionen placeras i en DeSO i sin kommun,
dragen med befolkningen som vikt, och får DeSO-områdets tyngdpunkt. Kommunens
YTA hade gett en punkt långt från där folk bor: 33 km fel i Älvdalen, 16 i
Falun, 14 i Mora. Att dra DeSO i stället för att ta den befolkningsviktade
tyngdpunkten ger dessutom pendlingsavstånden en spridning. För destinationer
är befolkningen en approximation av var jobben ligger.

Koordinaterna är SWEREF99 TM i meter, som regionens individer och
arbetsställen.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HAMTA = ("Pendlingsmatrisen (commuting) och DeSO-områdena (deso) byggs av "
         "scripts/create_database.py.")


def _kod(k) -> str:
    return str(k).strip().zfill(4)


class Omgivning:
    def __init__(self, conn, kommuner, ar=None):
        for tabell in ("commuting", "deso"):
            finns = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                 "AND name=?", (tabell,)).fetchone()
            if finns is None:
                raise ValueError(f"Tabellen {tabell} saknas. " + HAMTA)
        self.region = sorted({_kod(k) for k in kommuner})
        if not self.region:
            raise ValueError("Regionen har inga kommuner.")
        if ar is None:
            ar = conn.execute("SELECT MAX(year) FROM commuting").fetchone()[0]
        m = pd.read_sql("SELECT home_municipality AS bo, work_municipality AS arb, "
                        "       SUM(employed) AS n FROM commuting WHERE year = ? "
                        " GROUP BY 1, 2", conn, params=(int(ar),))
        m["bo"], m["arb"] = m["bo"].map(_kod), m["arb"].map(_kod)
        m = m[m["n"] > 0]
        saknas = [k for k in self.region if k not in set(m["bo"]) | set(m["arb"])]
        if saknas:
            raise ValueError(f"Pendlingsmatrisen {ar} saknar kommunerna {saknas}. " + HAMTA)
        self.ar = int(ar)
        i_bo, i_arb = m["bo"].isin(self.region), m["arb"].isin(self.region)
        self.inom = m[i_bo & i_arb].reset_index(drop=True)
        self.utpendling = m[i_bo & ~i_arb].reset_index(drop=True)
        self.inpendling = m[~i_bo & i_arb].reset_index(drop=True)
        self._jobb = m[i_arb].groupby("arb")["n"].sum()
        self._sysselsatta = m[i_bo].groupby("bo")["n"].sum()
        # Uppslagen per kommun görs en gång: utpendlingen dras vid var femte
        # sökning, och ett pandas-filter per dragning kostade 17 sekunder av
        # uppstarten. Ordningen inom varje kommun är tabellens, så dragningarna
        # är desamma som med filtret.
        self._ut = {k: (g["arb"].to_numpy(), g["n"].to_numpy(dtype=float))
                    for k, g in self.utpendling.groupby("bo", sort=False)}
        self._in = {k: (g["bo"].to_numpy(), g["n"].to_numpy(dtype=float))
                    for k, g in self.inpendling.groupby("arb", sort=False)}

        d = pd.read_sql("SELECT deso_code, population, geom_wkt FROM deso", conn)
        d = d[d["population"].fillna(0) > 0]
        d["kommun"] = d["deso_code"].str[:4]
        from shapely import wkt
        c = d["geom_wkt"].map(lambda s: wkt.loads(s).centroid)
        d["x"], d["y"] = c.map(lambda p: p.x), c.map(lambda p: p.y)
        self._deso = {k: (g[["x", "y"]].to_numpy(),
                          g["population"].to_numpy(dtype=float) / g["population"].sum())
                      for k, g in d.groupby("kommun")}

    # ---- nivåer ------------------------------------------------------------
    def jobb(self, kommun) -> int:
        """Alla sysselsatta med arbetsställe i kommunen, inpendlarna inräknade."""
        return int(self._jobb.get(_kod(kommun), 0))

    def sysselsatta(self, kommun) -> int:
        """Alla sysselsatta invånare, utpendlarna inräknade."""
        return int(self._sysselsatta.get(_kod(kommun), 0))

    def andel_utpendling(self, kommun) -> float:
        k = _kod(kommun)
        ut = self._ut.get(k)
        return float((ut[1].sum() if ut is not None else 0.0) / max(self.sysselsatta(k), 1))

    def andel_inpendling(self, kommun) -> float:
        k = _kod(kommun)
        return float(self.inpendling.loc[self.inpendling.arb == k, "n"].sum()
                     / max(self.jobb(k), 1))

    # ---- dragningar --------------------------------------------------------
    def dra_destination(self, hemkommun, rng) -> str:
        """Kommun utanför regionen dit en invånare i hemkommun pendlar."""
        ut = self._ut.get(_kod(hemkommun))
        if ut is None:
            raise ValueError(f"Ingen utpendling från {hemkommun} i matrisen {self.ar}.")
        koder, p = ut
        return str(koder[int(rng.choice(len(p), p=p / p.sum()))])

    def dra_ursprung(self, arbetskommun, rng) -> str:
        """Kommun utanför regionen som en inpendlare till arbetskommun bor i."""
        inp = self._in.get(_kod(arbetskommun))
        if inp is None:
            raise ValueError(f"Ingen inpendling till {arbetskommun} i matrisen {self.ar}.")
        koder, p = inp
        return str(koder[int(rng.choice(len(p), p=p / p.sum()))])

    def dra_plats(self, kommun, rng):
        """(x, y) i en DeSO i kommunen, dragen med befolkningen som vikt."""
        try:
            xy, p = self._deso[_kod(kommun)]
        except KeyError:
            raise ValueError(f"DeSO-områden med befolkning saknas för kommun {kommun}. "
                             + HAMTA) from None
        x, y = xy[int(rng.choice(len(p), p=p))]
        return float(x), float(y)
