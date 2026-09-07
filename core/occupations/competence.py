"""
core/occupations/competence.py
------------------------------
Individen som överlagrade kompetenscirklar. Se docs/individmodell.md, avsnitt 2.

Varje individ har upp till K cirklar. En cirkel har centrum (x, y), radie i
kvadrat rho2, massa m, en nyckel (yrke eller utbildning) och en egen
vilaradie rho2_home som den skärps mot när den används.

Representation: fyllda arrayer N x K, tomma platser har key == -1 och mass 0.
Det gör månadsuppdateringen till några vektoroperationer över hela
populationen och konkurrenskraften till en liten skalärprodukt per sökande.

Dynamik per år (dt i år):
    exponering  dm/dt = +a            för den aktiva cirkeln
    läckage     dm/dt = -lambda m     för alla       -> mättnad a/lambda
    diffusion   d(rho2)/dt = +2D      för inaktiva   -> toppen ~ 1/(rho2_0 + 2Dt)
    skärpning   d(rho2)/dt = (rho2_home - rho2)/tau  för den aktiva

Konkurrenskraft i jobb j med radie r_o vid avstånd d_k från cirkel k:
    q = min(1, sum_k (1 - exp(-m_k/m_ref)) * 2 r_o^2/(rho2_k + r_o^2)
                       * exp(-d_k^2 / (2 gamma^2 (rho2_k + r_o^2))))
"""
from __future__ import annotations

import numpy as np

EMPTY = -1


class CompetenceParams:
    __slots__ = ("a", "lam", "D", "tau_months", "m_ref", "gamma", "K")

    def __init__(self, a=1.0, lam=None, D=0.015, tau_months=6.0, m_ref=2.0,
                 gamma=0.875, K=12, half_life_years=15.0):
        self.a = float(a)
        self.lam = float(lam) if lam is not None else float(np.log(2) / half_life_years)
        self.D = float(D)
        self.tau_months = float(tau_months)
        self.m_ref = float(m_ref)
        self.gamma = float(gamma)
        self.K = int(K)

    @classmethod
    def from_config(cls, sim: dict) -> "CompetenceParams":
        c = sim.get("competence", {}) or {}
        return cls(
            a=c.get("exposure_rate", 1.0),
            half_life_years=c.get("leak_half_life_years", 15.0),
            D=c.get("diffusion", 0.015),
            tau_months=c.get("sharpen_months", 6.0),
            m_ref=c.get("m_ref_years", 2.0),
            gamma=sim.get("sigma_gamma", 0.875),
            K=c.get("max_circles", 12),
        )


class Circles:
    """Fyllda arrayer N x K. Nycklar är heltal via key_index."""

    def __init__(self, n: int, K: int):
        self.n, self.K = int(n), int(K)
        self.x = np.zeros((n, K)); self.y = np.zeros((n, K))
        self.rho2 = np.ones((n, K)); self.rho2_home = np.ones((n, K))
        self.mass = np.zeros((n, K))
        self.key = np.full((n, K), EMPTY, dtype=np.int64)
        self.key_index: dict = {}          # nyckelsträng -> heltal
        self.key_names: list = []

    # ---- nycklar ---------------------------------------------------------
    def code(self, key) -> int:
        if key not in self.key_index:
            self.key_index[key] = len(self.key_names)
            self.key_names.append(key)
        return self.key_index[key]

    # ---- exponering --------------------------------------------------------
    def add(self, i: int, key, x: float, y: float, rho2: float, mass: float,
            rho2_home: float | None = None):
        """Lägg massa på cirkeln med nyckeln key, eller skapa den. Finns den
        redan sammanvägs radien massviktat. Är alla platser upptagna faller
        den med minst massa bort (aldrig den nya)."""
        k = self.code(key)
        row = self.key[i]
        hit = np.flatnonzero(row == k)
        if hit.size:
            j = int(hit[0])
            m0 = self.mass[i, j]
            tot = m0 + mass
            if tot > 0:
                self.rho2[i, j] = (m0 * self.rho2[i, j] + mass * rho2) / tot
            self.mass[i, j] = tot
            return j
        free = np.flatnonzero(row == EMPTY)
        j = int(free[0]) if free.size else int(np.argmin(self.mass[i]))
        self.key[i, j] = k
        self.x[i, j], self.y[i, j] = x, y
        self.rho2[i, j] = rho2
        self.rho2_home[i, j] = rho2 if rho2_home is None else rho2_home
        self.mass[i, j] = mass
        return j

    # ---- dynamik -----------------------------------------------------------
    def evolve(self, dt_years: float, active_key: np.ndarray, p: CompetenceParams):
        """En tidsstegning för hela populationen. active_key[i] är nyckelkoden
        för individens aktiva yrke, eller EMPTY om hon inte arbetar."""
        occupied = self.key != EMPTY
        active = occupied & (self.key == active_key[:, None])
        # läckage på allt
        self.mass *= np.exp(-p.lam * dt_years)
        # exponering på den aktiva
        self.mass[active] += p.a * dt_years
        # diffusion på inaktiva, skärpning på aktiva
        inactive = occupied & ~active
        self.rho2[inactive] += 2.0 * p.D * dt_years
        if active.any():
            f = 1.0 - np.exp(-12.0 * dt_years / p.tau_months)
            self.rho2[active] += f * (self.rho2_home[active] - self.rho2[active])
        np.minimum(self.rho2, 4.0, out=self.rho2)          # praktiskt tak
        self.mass[~occupied] = 0.0

    # ---- konkurrenskraft --------------------------------------------------------
    def competitiveness(self, i: int, jx, jy, jro, p: CompetenceParams):
        """q för individ i mot jobb med centra (jx, jy) och radier jro.
        Vektoriserat över jobben; summa över individens cirklar."""
        jx = np.asarray(jx, float); jy = np.asarray(jy, float); jro = np.asarray(jro, float)
        occ = self.key[i] != EMPTY
        if not occ.any():
            return np.zeros(jx.shape)
        cx = self.x[i, occ][:, None]; cy = self.y[i, occ][:, None]
        r2 = self.rho2[i, occ][:, None]; m = self.mass[i, occ][:, None]
        ro2 = (jro ** 2)[None, :]
        width = r2 + ro2
        d2 = (cx - jx[None, :]) ** 2 + (cy - jy[None, :]) ** 2
        contrib = ((1.0 - np.exp(-m / p.m_ref))
                   * (2.0 * ro2 / width)
                   * np.exp(-0.5 * d2 / (p.gamma ** 2 * width)))
        return np.minimum(1.0, contrib.sum(axis=0))

    # ---- sammanfattning --------------------------------------------------------
    def summarize(self):
        """Härledda mått per individ: centroid (skärpeviktad), chi, xi,
        riktningskonsekvens R och spridning r_i. För loggning och kompatibilitet."""
        occ = self.key != EMPTY
        w = np.where(occ, self.mass / (self.rho2 + 1e-9), 0.0)   # massa gånger täthet
        wsum = w.sum(axis=1)
        safe = np.where(wsum > 0, wsum, 1.0)
        x = (w * self.x).sum(axis=1) / safe
        y = (w * self.y).sum(axis=1) / safe
        chi = np.hypot(x, y)
        xi = np.arctan2(y, x) % (2 * np.pi)
        ang = np.arctan2(self.y, self.x)
        R = np.hypot((w * np.cos(ang)).sum(axis=1), (w * np.sin(ang)).sum(axis=1)) / safe
        r_i = np.sqrt((w * self.rho2).sum(axis=1) / safe)
        none = wsum <= 0
        x[none] = 0.0; y[none] = 0.0; chi[none] = 0.0; R[none] = 0.0; r_i[none] = 1.0
        return {"x_occ": x, "y_occ": y, "chi": chi, "xi": xi, "R": R, "r_i": r_i}


# ---------------------------------------------------------------------------
# Initiering ur en startpopulation
# ---------------------------------------------------------------------------
EDU_RADIUS2 = {0: 1.0, 1: 1.0, 2: 0.8, 3: 0.5, 4: 0.5, 5: 0.35, 6: 0.25, 7: 0.25}
EDU_MASS = {0: 1.0, 1: 1.0, 2: 0.6, 3: 1.0, 4: 1.5, 5: 2.5, 6: 3.5, 7: 4.5}


def seed_circles(circles: Circles, i: int, onet_code, x_occ, y_occ, r_o,
                 tenure_years: float, edu_level: int, p: CompetenceParams,
                 rng=None):
    """Startpopulation: grundskola, nivåns cirkel (yrkets riktning som proxy)
    och en arbetscirkel med massa mättnad*(1 - e^{-lambda*tenure}) och en
    skärpa som svarar mot pågående aktivitet."""
    circles.add(i, "EDU:0", 0.0, 0.0, 1.0, EDU_MASS[0])
    lvl = int(edu_level) if edu_level is not None and not np.isnan(float(edu_level)) else 0
    lvl = max(0, min(7, lvl))
    if lvl >= 2:
        circles.add(i, f"EDU:{lvl}", float(x_occ), float(y_occ),
                    EDU_RADIUS2[lvl], EDU_MASS[lvl])
    if onet_code is not None and tenure_years > 0:
        m_sat = p.a / p.lam
        m = m_sat * (1.0 - np.exp(-p.lam * tenure_years))
        circles.add(i, str(onet_code), float(x_occ), float(y_occ),
                    float(r_o) ** 2, m, rho2_home=float(r_o) ** 2)
