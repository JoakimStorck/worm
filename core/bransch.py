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

- Kommunens branschfördelning är dagbefolkningen: anställda med arbetsplats
  i kommunen per bransch (TAB4436, employment_workplace_occupation_sni).
  Tidigare togs den ur invånarnas bransch (employment_deso_sni,
  nattbefolkning), vilket för en utpendlingskommun lade jobben där
  invånarna bor: Orsa fick 9,7 procent tillverkningsjobb i stället för 5,5.
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

# "Okänd verksamhet" bär ingen information om bransch. Ett arbetsställe måste
# ha en bransch, så andelen fördelas om över de kända.
OKANDA = {"00"}

HAMTA = ("Tabellerna byggs av scripts/create_database.py: "
         "employment_workplace_occupation_sni ur TAB4436 (hämtas med "
         "python scripts/fetch_data.py --only \"dagbef yrke bransch\") och "
         "occupation_by_industry ur yrkesregistret (data/TAB4347_sv.csv).")


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
        for tabell in ("occupation_by_industry", "employment_workplace_occupation_sni"):
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
        """Kommunens andel av jobben per bransch (dagbefolkning, senaste
        året), okänd verksamhet borträknad."""
        df = pd.read_sql("SELECT sni_code, SUM(employed) AS e "
                         "  FROM employment_workplace_occupation_sni "
                         " WHERE municipal_code = ? AND year = "
                         "       (SELECT MAX(year) FROM employment_workplace_occupation_sni) "
                         " GROUP BY 1",
                         self.conn, params=(str(municipal_code).zfill(4),))
        df = df[~df["sni_code"].astype(str).isin(OKANDA)]
        df = df[df["e"] > 0]
        if df.empty:
            raise ValueError(f"employment_workplace_occupation_sni saknar kommun "
                             f"{municipal_code}. " + HAMTA)
        saknas = sorted(set(df["sni_code"]) - set(self.p_klass.index))
        if saknas:
            raise ValueError(f"Branscherna {saknas} i employment_workplace_occupation_sni "
                             "saknas i occupation_by_industry; branschgrupperna ska vara "
                             "desamma.")
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


# Stödyrken: chefer (SSYK 1), administration och kundtjänst (4), städ och
# liknande (91). De finns på alla slags arbetsställen och fördelas därför
# utan avståndsvikt; 16,9 procent i riket, 7-35 procent per bransch.
def ar_stodyrke(ssyk) -> bool:
    s_ = str(ssyk)
    return s_.startswith(("1", "4")) or s_.startswith("91")


class Kommunprofil:
    """Jobbens yrken ur kommunens egen profil (individmodell.md avsnitt 3,
    "Kommunens profil i arbetsställena").

    VARFÖR. Rikets P(yrke | bransch) gav kommunens yrkesfördelning en gemensam
    massa på 0,78 i median mot den faktiska, mot 0,95 för ett slumpurval av
    samma storlek. Värst i bruksorter: Oxelösund 0,58. Modellen bygger på
    befintliga kommuner, så de ska ha sin faktiska profil från start: en
    kommun som domineras av en industri gör det i modellen också.

    VID START, EN POOL. Kommunens jobb i bransch s får yrken ur kommunens
    P_k(ssyk | s) (TAB4436, dagbefolkning) i heltal, så att summan över
    arbetsställena är kommunens profil exakt. Arbetsställena tas i fallande
    storlek; vart och ett tar först ett kärnyrke ur poolen med antalet som
    vikt -- stålverket får troligast metallarbetarna -- och fylls sedan jobb
    för jobb ur det som återstår, med vikten

        antal * exp(-d^2 / 2 r_c^2)   för profilyrken
        antal                          för stödyrken

    där d är avståndet mellan SSYK-gruppernas tyngdpunkter i uppgiftsrummet
    och r_c kärnans task-radie. Bredden är kärnyrkets egen radie, ingen fri
    parameter. Spetsigheten följer av poolen: finns bara närliggande yrken i
    kommunens bransch blir arbetsställena smala av sig själva.

    UNDER KÖRNING, EN DRAGNING. Ett nytt jobb dras ur P_k(ssyk | s) med samma
    vikt mot arbetsställets kärna. Aggregatet bevaras då i väntevärde, inte
    exakt.

    Yrken som inte kan placeras i uppgiftsrummet -- okänt yrke (0002) och
    SSYK utan crosswalk till en O*NET-kod med geometri, som de militära --
    räknas bort och resten normeras om. Saknad tabell, eller en kommun och
    bransch utan yrken, kastar. Storleksklassen påverkar inte yrket: TAB4436
    saknar den.
    """

    def __init__(self, conn, ar=None):
        for tabell in ("employment_workplace_occupation_sni", "ssyk3_onet_crosswalk",
                       "onet_occupation_space"):
            finns = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                 "AND name=?", (tabell,)).fetchone()
            if finns is None:
                raise ValueError(f"Tabellen {tabell} saknas. Jobbens yrke dras ur "
                                 "kommunens profil i TAB4436 och SSYK-O*NET-crosswalken, "
                                 "som scripts/create_database.py bygger; geometrin ur "
                                 "scripts/load_task_geometry.py --write. " + HAMTA)
        cw = pd.read_sql(
            "SELECT c.occupation_code AS ssyk, c.onet_code, c.share, "
            "       g.x_occ, g.y_occ, g.r_o "
            "  FROM ssyk3_onet_crosswalk c "
            "  JOIN onet_occupation_space g ON g.onet_code = c.onet_code "
            " WHERE c.share > 0", conn)
        self._onet, lage = {}, {}
        for ssyk, g in cw.groupby("ssyk"):
            w = g["share"].to_numpy(dtype=float)
            w = w / w.sum()
            self._onet[str(ssyk)] = (g["onet_code"].to_numpy(), w)
            r_o = g["r_o"].to_numpy(dtype=float)
            lage[str(ssyk)] = (float(w @ g["x_occ"].to_numpy(dtype=float)),
                               float(w @ g["y_occ"].to_numpy(dtype=float)),
                               float(w @ np.where(np.isfinite(r_o), r_o, 0.27)))
        self._lage = lage
        if ar is None:
            ar = conn.execute("SELECT MAX(year) FROM "
                              "employment_workplace_occupation_sni").fetchone()[0]
        df = pd.read_sql("SELECT municipal_code, sni_code, ssyk_code, SUM(employed) AS n "
                         "  FROM employment_workplace_occupation_sni WHERE year = ? "
                         " GROUP BY 1, 2, 3", conn, params=(int(ar),))
        df = df[df["ssyk_code"].astype(str).isin(lage) & (df["n"] > 0)]
        self._p = {}
        for (k, s_), g in df.groupby(["municipal_code", "sni_code"]):
            n = g["n"].to_numpy(dtype=float)
            self._p[(str(k), str(s_))] = (g["ssyk_code"].astype(str).to_numpy(), n / n.sum())

    # ---- underlag ----------------------------------------------------------
    def profil(self, kommun, bransch):
        try:
            return self._p[(str(kommun).zfill(4), str(bransch))]
        except KeyError:
            raise ValueError(f"TAB4436 har inga anställda med placerbart yrke i kommun "
                             f"{kommun}, bransch {bransch}. " + HAMTA) from None

    def pool(self, kommun, bransch, n: int) -> pd.Series:
        """Heltal per yrke som summerar till n (största rest)."""
        koder, p = self.profil(kommun, bransch)
        exakt = p * int(n)
        heltal = np.floor(exakt).astype(int)
        rest = int(n) - int(heltal.sum())
        if rest > 0:
            heltal[np.argsort(-(exakt - heltal), kind="stable")[:rest]] += 1
        return pd.Series(heltal, index=koder)

    def _logvikt(self, koder, karna):
        """log(avståndsvikt) mot kärnan: 0 för stödyrken och utan kärna."""
        if karna is None:
            return np.zeros(len(koder))
        kx, ky, kr = self._lage[str(karna)]
        xy = np.array([self._lage[k][:2] for k in koder])
        d2 = (xy[:, 0] - kx) ** 2 + (xy[:, 1] - ky) ** 2
        lv = -d2 / (2.0 * kr ** 2)
        lv[np.array([ar_stodyrke(k) for k in koder])] = 0.0
        return lv

    # ---- vid start: poolen fördelas ------------------------------------------
    def fordela(self, kommun, bransch, storlekar, rng):
        """Fördelar branschens pool på arbetsställena. Returnerar, i samma
        ordning som storlekar, (kärna, [ssyk per jobb])."""
        storlekar = [int(m) for m in storlekar]
        pool = self.pool(kommun, bransch, sum(storlekar))
        koder = pool.index.to_numpy()
        kvar = pool.to_numpy().astype(float)
        profil_mask = np.array([not ar_stodyrke(k) for k in koder])
        ut = [None] * len(storlekar)
        for i in sorted(range(len(storlekar)), key=lambda j: -storlekar[j]):
            m = storlekar[i]
            # kärnan är ett profilyrke; finns inga kvar har arbetsstället ingen
            val = kvar * profil_mask
            karna = None
            if val.sum() > 0:
                karna = str(koder[int(rng.choice(len(koder), p=val / val.sum()))])
            lv = self._logvikt(koder, karna)
            jobb = []
            if karna is not None and m > 0:
                j = int(np.flatnonzero(koder == karna)[0])
                kvar[j] -= 1
                jobb.append(karna)
            while len(jobb) < m:
                ok = kvar > 0
                lw = np.where(ok, np.log(np.where(ok, kvar, 1.0)) + lv, -np.inf)
                w = np.exp(lw - lw[ok].max())
                j = int(rng.choice(len(koder), p=w / w.sum()))
                kvar[j] -= 1
                jobb.append(str(koder[j]))
            ut[i] = (karna, jobb)
        return ut

    # ---- under körning: dragning ---------------------------------------------
    def dra_nytt(self, kommun, bransch, karna, rng) -> str:
        """Yrke för ett nytt jobb på ett arbetsställe med kärnan karna."""
        koder, p = self.profil(kommun, bransch)
        lw = np.log(p) + self._logvikt(koder, karna if karna in self._lage else None)
        w = np.exp(lw - lw.max())
        return str(koder[int(rng.choice(len(koder), p=w / w.sum()))])

    # ---- O*NET: ett svenskt yrke är en kod per arbetsställe ------------------
    def onet(self, ssyk, rng, realiserade=None) -> str:
        """O*NET-koden för ssyk på ett arbetsställe. realiserade är
        arbetsställets egna yrken, ssyk -> O*NET; har arbetsstället redan
        yrket återanvänds koden (steg a: en SSYK3-grupp sprids av crosswalken
        på i median 19 koder)."""
        if realiserade is not None and ssyk in realiserade:
            return realiserade[ssyk]
        koder, w = self._onet[str(ssyk)]
        kod = str(koder[int(rng.choice(len(koder), p=w))])
        if realiserade is not None:
            realiserade[ssyk] = kod
        return kod
