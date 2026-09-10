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
        Vektoriserat över jobben; summa över individens cirklar.

        OKAPAT. min(1, .) satt här tidigare, och det gjorde q = 1 till ett
        MAXIMUM i stället för en normering av den mogna arbetaren i eget
        yrke. Följden var en atom: 41 procent av alla anställningar låg på
        exakt w/Pi = 0.85, eftersom p = q**(k*r) blev exakt 1 för var och en
        som slog i taket, och Pi var ett supremum ingen kunde passera --
        0.00 procent låg över fältlönen, mot hälften om Pi är yrkets median.
        Varje förbättring av matchningen gjorde det VÄRRE, eftersom högre q
        betyder fler i taket: efter urvalet (0055) steg atomen från 24 till
        44 procent.

        Summan är en summa av produkter, alltså approximativt lognormal, och
        den som har flera cirklar som alla överlappar jobbet är värd MER än
        den med en enda perfekt. Bredd betalar sig, vilket är ett påstående om
        världen som följer ur geometrin i stället för att klistras på. q = 1
        är fortfarande normeringen (m_ref, skärpefaktorn), men som medianen
        bland mogna arbetare i eget yrke, inte som tak.

        Sannolikhetsrollen -- mötesdraget i search_once -- kräver [0, 1] och
        kapar själv. Värderollen får det som kommer.
        """
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
        return self._union(contrib, cx[:, 0], cy[:, 0], r2[:, 0])

    def _union(self, contrib, cx, cy, r2):
        """Täckning, inte summa: varje cirkel räknas bara till den del den
        täcker något de starkare inte redan täcker.

        Summan över cirklar hade ingen gräns. Massan är bunden av balansen
        tillväxt mot glömska, m* = a/lambda = 13, och en ensam cirkel exakt på
        jobbet mättar mot 1 -- men N skarpa cirklar på samma ställe gav q = N.
        Därav en premie på FRAGMENTERING: tjugo år i ett jobb gav 1.00, samma
        tjugo år delade på tre närliggande jobb gav 3 x 0.887 = 2.66. Den som
        bytte ofta blev mer konkurrenskraftig än den som stannade, med samma
        erfarenhet, och över tio år divergerade allt: median q vid anställning
        1.21, 67 procent över ett, andelen av beståndet över Pi 80 procent,
        vakansstocken tredubblad.

        Jobbet är ett moln av uppgifter. Bredd lönar sig när en andra
        erfarenhet täcker uppgifter i jobbet som den första inte täckte -- och
        bara då. Två cirklar på samma ställe täcker samma uppgifter två gånger.
        Det som ska mätas är UNIONEN av täckning, och den kan inte överstiga
        hela jobbet: q får en övre gräns i geometrin, inte i en min().

        Cirklarna tas i fallande bidragsordning. Cirkel k räknas med faktorn
        prod_{l<k} (1 - O_lk * c_l), där O_lk är Bhattacharyya-överlappet
        mellan två isotropa gaussiska cirklar -- sluten form ur centrum och
        bredder, i [0, 1]. Två identiska mogna cirklar ger 1.00, inte 2.00.
        Tre halva på samma ställe ger 1.00, inte 2.66. Två cirklar som täcker
        olika delar av ett brett jobb räknas båda. Bredd i den vanliga
        meningen -- erfarenhet från flera trakter -- lönar sig därmed inte som
        en stapel på ett jobb man redan behärskar, utan i RÖRLIGHETEN: fler
        jobb inom räckhåll, bättre passform i vart och ett, och en bättre
        position vid nästa byte. Det är Burdett-Mortensens stege i
        uppgiftsrummet, och det är vad Buhai och Teulings hittar i data:
        avkastningen på tjänstetid är selektion på utsidor, inte deterministisk
        tillväxt.

        Överlappet mäts mellan cirklarna, inte via jobbet. En jobbmedveten
        variant -- hur mycket av DET HÄR jobbet täcker k som l inte täckte --
        är rätt storhet men en trippelprodukt; den står som nästa steg i
        docs/lonemodell.md.
        """
        K, J = contrib.shape
        if K == 1:
            return contrib[0]
        # Bhattacharyya mellan isotropa gaussiska cirklar k och l
        dx = cx[:, None] - cx[None, :]
        dy = cy[:, None] - cy[None, :]
        s2 = r2[:, None] + r2[None, :]
        O = (np.exp(-(dx ** 2 + dy ** 2) / (2.0 * s2))
             * (2.0 * np.sqrt(r2[:, None] * r2[None, :]) / s2))
        q = np.zeros(J)
        for j in range(J):
            c = contrib[:, j]
            ordning = np.argsort(-c)
            tackt = np.ones(K)               # 1 - täckt andel, per cirkel
            tot = 0.0
            for k in ordning:
                if c[k] <= 0.0:
                    break
                novel = 1.0
                for l in ordning:
                    if l == k:
                        break
                    novel *= (1.0 - O[l, k] * min(c[l], 1.0))
                tot += c[k] * novel
            q[j] = tot
        return q

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
