"""
core/occupations/price_field.py
-------------------------------
Priset på kompetens Π(r) över enhetsskivan, enligt Technology fields (ekv. 1):

    ln Π(ξ, χ) = m0 + m1 cos ξ + m2 sin ξ + χ (m3 + m4 cos ξ + m5 sin ξ)

Koefficienterna estimeras i technology-fields (scripts/01_wage_field.py, spec
S1_field) och levereras till WORM som FIL: data/geometry/wage_field_coefficients.csv.
Ingen kodberoende mellan repon -- byt fil när modellen revideras.

Nivån är amerikansk (BLS-löner). WORM använder bara FORMEN: Π normaliseras till
relativpris (medel 1 över yrken med egen geometri) i load_task_geometry.py, och
alla löner, reservationslöner och pendlingskostnader uttrycks i löneandelar.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

PARAMS = ["m0", "m1", "m2", "m3", "m4", "m5"]


@dataclass(frozen=True)
class PriceField:
    m0: float
    m1: float
    m2: float
    m3: float
    m4: float
    m5: float
    norm: float = 1.0          # divisor: Π_rel = Π / norm

    @classmethod
    def from_csv(cls, path: str, spec: str = "S1_field") -> "PriceField":
        df = pd.read_csv(path)
        s = df.loc[df["spec"] == spec].set_index("param")["coef"]
        missing = [p for p in PARAMS if p not in s.index]
        if missing:
            raise ValueError(f"saknar koefficienter {missing} i {path} (spec '{spec}')")
        return cls(*(float(s[p]) for p in PARAMS))

    @classmethod
    def from_db(cls, conn) -> "PriceField":
        df = pd.read_sql("SELECT param, coef FROM wage_field_coefficients", conn)
        s = df.set_index("param")["coef"]
        norm = float(s["norm"]) if "norm" in s.index else 1.0
        return cls(*(float(s[p]) for p in PARAMS), norm=norm)

    def with_norm(self, norm: float) -> "PriceField":
        return PriceField(self.m0, self.m1, self.m2, self.m3, self.m4, self.m5, float(norm))

    # -- evaluering ----------------------------------------------------------
    def log_pi(self, xi, chi):
        xi = np.asarray(xi, dtype=float); chi = np.asarray(chi, dtype=float)
        return (self.m0 + self.m1 * np.cos(xi) + self.m2 * np.sin(xi)
                + chi * (self.m3 + self.m4 * np.cos(xi) + self.m5 * np.sin(xi)))

    def pi(self, xi, chi):
        """Absolut Π (BLS-nivå)."""
        return np.exp(self.log_pi(xi, chi))

    def pi_rel(self, xi, chi):
        """Relativpris Π / norm. Detta är vad WORM använder."""
        return self.pi(xi, chi) / self.norm

    def pi_rel_cart(self, x, y):
        x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
        return self.pi_rel(np.arctan2(y, x) % (2 * np.pi), np.hypot(x, y))

    def beta_chi(self, xi):
        """Riktad avkastning på djup: m3 + m4 cos ξ + m5 sin ξ."""
        xi = np.asarray(xi, dtype=float)
        return self.m3 + self.m4 * np.cos(xi) + self.m5 * np.sin(xi)

    def to_rows(self):
        rows = [{"param": p, "coef": getattr(self, p)} for p in PARAMS]
        rows.append({"param": "norm", "coef": self.norm})
        return rows
