"""
core/occupations/requirement.py
-------------------------------
Kravintensitet per jobb ur kapabilitetsfältet i Technology fields.

Problemet. Konkurrenskraften q mäter överlapp mellan individens erfarenhet och
jobbets uppgiftsmoln. Att behandla q som produktivitet för alla jobb ger två
motsatta fel med samma q. En arbetare med q = 0.05 vid ett kirurgjobb
producerar inte fem procent av en kirurg -- hon producerar ingenting, för hon
kan inte operera. En advokat med q = 0.1 vid diskbänken producerar inte tio
procent av en diskare -- hon producerar nästan fullt, för vem som helst kan
diska. Hur överlapp översätts till produktivitet beror på hur mycket jobbet
KRÄVER specifik erfarenhet.

Kravet är inte en geometrisk storhet, och prisfältet duger inte som proxy:
djup betalas i norr men krävs i nordost (papper 1: löne- och
utbildningsgradienten pekar 61 respektive 36 grader). Advokater och
sjuksköterskor fick r nära noll ur prisfältet.

Kapabilitetsfältet Q(x, y) = a0 + a4 x + a5 y, estimerat i technology-fields
på O*NET:s skills och abilities (R2 0.74, pol vid 52 grader), rangordnar i
stället som man väntar: läkare 0.84, advokater 0.81, sjuksköterskor 0.77,
undersköterskor 0.36, lastbilsförare 0.17, diskare 0.00.

Produktivitet i jobb j:   p = q ** (k * r_j)

r_j = 0 ger p = 1 oavsett q; r_j = 1 ger p = q**k. Det är exponenten
alpha(zon) i docs/individmodell.md, med kravet ur ett estimerat fält i
stället för Job Zone. När Job Zone finns (steg 4) byts r_j ut; formen står.
Grindvaktsfrågan blir exakt hur väl Q förutsäger Job Zone.

Koefficienterna levereras som fil, data/geometry/capability_field_coefficients.csv,
i linje med att artefakter flödar mellan repon utan kodberoenden.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd


class CapabilityField:
    __slots__ = ("a0", "a4", "a5", "q_lo", "q_hi")

    def __init__(self, a0, a4, a5, q_lo=None, q_hi=None):
        self.a0, self.a4, self.a5 = float(a0), float(a4), float(a5)
        self.q_lo = q_lo
        self.q_hi = q_hi

    @classmethod
    def from_csv(cls, path, spec="Q_plane", cluster="S1"):
        """Q_plane är teorins treparametersform; S1 är huvudspecifikationen."""
        df = pd.read_csv(path)
        d = df[(df["spec"] == spec) & (df["cluster"] == cluster)]
        d = d.drop_duplicates("param").set_index("param")["coef"]
        missing = [k for k in ("a0", "a4", "a5") if k not in d.index]
        if missing:
            raise ValueError(f"saknar {missing} i {path} ({spec}/{cluster})")
        return cls(d["a0"], d["a4"], d["a5"])

    @classmethod
    def from_db(cls, conn):
        df = pd.read_sql("SELECT param, coef FROM capability_field_coefficients", conn)
        d = df.set_index("param")["coef"]
        return cls(d["a0"], d["a4"], d["a5"],
                   q_lo=float(d["q_lo"]) if "q_lo" in d.index else None,
                   q_hi=float(d["q_hi"]) if "q_hi" in d.index else None)

    def Q(self, x, y):
        return self.a0 + self.a4 * np.asarray(x, float) + self.a5 * np.asarray(y, float)

    def calibrate(self, x, y, lo_q=0.05, hi_q=0.95):
        """Normering ur yrkesfördelningen: p5 -> 0, p95 -> 1."""
        Q = self.Q(x, y)
        self.q_lo, self.q_hi = float(np.nanquantile(Q, lo_q)), float(np.nanquantile(Q, hi_q))
        return self

    def requirement(self, x, y):
        """r i [0, 1]. Kräver kalibrering."""
        if self.q_lo is None or self.q_hi is None:
            raise ValueError("kapabilitetsfältet är inte kalibrerat (q_lo/q_hi saknas)")
        Q = self.Q(x, y)
        return np.clip((Q - self.q_lo) / max(self.q_hi - self.q_lo, 1e-9), 0.0, 1.0)

    def to_rows(self):
        rows = [{"param": "a0", "coef": self.a0}, {"param": "a4", "coef": self.a4},
                {"param": "a5", "coef": self.a5}]
        if self.q_lo is not None:
            rows += [{"param": "q_lo", "coef": self.q_lo}, {"param": "q_hi", "coef": self.q_hi}]
        return rows


def productivity(q, r, k=2.0):
    """p = q ** (k * r). r = 0: alla är fullt produktiva. r = 1: q ** k."""
    # Inget klipp på q: taket satt på två ställen (här och i competitiveness),
    # så att ta bort det ena räckte inte. q > 1 ger p > 1 och w > Pi, vilket
    # är vad Pi som median kräver. Vid r = 0 är p = q**0 = 1 oavsett.
    q = np.maximum(np.asarray(q, float), 0.0)
    r = np.clip(np.asarray(r, float), 0.0, 1.0)
    return np.power(q, k * r)
