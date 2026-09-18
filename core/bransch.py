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


class YrkeGivetBransch:
    """Jobbets yrke givet arbetsställets bransch och storleksklass.

    P(O*NET | bransch, klass) = sum_ssyk P(ssyk | bransch, klass) *
    crosswalk(ssyk -> O*NET), med P(ssyk | bransch, klass) ur rikets
    yrkesregister (occupation_by_industry) och crosswalken ur SSYK-ISCO-
    nyckeln och ESCO (ssyk3_onet_crosswalk). Samma register och crosswalk
    som invånarnas yrken byggs av, så de två sidorna delar yrkesstruktur.

    EN FUNKTION FÖR START OCH KÖRNING. Startens jobb drogs tidigare ur
    sni_onet_link eller ur kommunens yrkesprofil, nya jobb under körningen
    ur kommunens profil, och ingen av vägarna tog hänsyn till
    arbetsställets bransch: en läkare kunde anställas på en bilverkstad.
    Scenariobyggaren och World anropar nu båda dra().

    SSYK-grupper utan O*NET-koppling -- okänt yrke (000) och de militära
    (011, 021) -- och O*NET-koder utan geometri räknas bort och resten
    normeras om. Saknad tabell, eller en bransch och klass utan vikt, kastar.
    """

    def __init__(self, conn):
        for tabell in ("occupation_by_industry", "ssyk3_onet_crosswalk",
                       "onet_occupation_space"):
            finns = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                 "AND name=?", (tabell,)).fetchone()
            if finns is None:
                raise ValueError(f"Tabellen {tabell} saknas. Jobbens yrke dras ur "
                                 "yrkesregistret och SSYK-O*NET-crosswalken, som "
                                 "scripts/create_database.py bygger; geometrin ur "
                                 "scripts/load_task_geometry.py --write.")
        # Två led: P(ssyk | bransch, klass) och P(O*NET | ssyk). Produkten är
        # samma fördelning som förut; att leden hålls isär är det som låter
        # ett arbetsställe realisera ett svenskt yrke som EN O*NET-kod.
        # O*NET-koder utan geometri faller i andra ledet, och ssyk-vikten
        # skalas med den andel av crosswalken som finns kvar, så att
        # produkten är oförändrad.
        cw = pd.read_sql(
            "SELECT c.occupation_code AS ssyk, c.onet_code, c.share "
            "  FROM ssyk3_onet_crosswalk c "
            "  JOIN onet_occupation_space g ON g.onet_code = c.onet_code "
            " WHERE c.share > 0", conn)
        self._onet = {}
        for ssyk, g in cw.groupby("ssyk"):
            p = g["share"].to_numpy(dtype=float)
            self._onet[str(ssyk)] = (g["onet_code"].to_numpy(), p / p.sum())
        kvar = cw.groupby("ssyk")["share"].sum()
        reg = pd.read_sql("SELECT sni_code, size_class, ssyk_code, SUM(employed) AS e "
                          "FROM occupation_by_industry GROUP BY 1, 2, 3", conn)
        reg["vikt"] = reg["e"] * reg["ssyk_code"].map(kvar).fillna(0.0)
        reg = reg[reg["vikt"] > 0]
        self._ssyk = {}
        for (bransch, klass), g in reg.groupby(["sni_code", "size_class"]):
            p = g["vikt"].to_numpy(dtype=float)
            self._ssyk[(bransch, klass)] = (g["ssyk_code"].astype(str).to_numpy(), p / p.sum())

    def _ssyk_fordelning(self, bransch, storlek):
        klass = storleksklass(int(storlek))
        try:
            return self._ssyk[(str(bransch), klass)]
        except KeyError:
            raise ValueError(f"Yrkesregistret har inga anställda med O*NET-koppling "
                             f"i bransch {bransch}, {klass}.") from None

    def fordelning(self, bransch, storlek):
        """O*NET-fördelningen för ett jobb i branschen och klassen, sett
        över alla arbetsställen: summan över ssyk av de två leden."""
        ssyk, ps = self._ssyk_fordelning(bransch, storlek)
        vikt = {}
        for s_, p_s in zip(ssyk, ps):
            for kod, p_o in zip(*self._onet[s_]):
                vikt[kod] = vikt.get(kod, 0.0) + p_s * p_o
        koder = np.array(list(vikt))
        return koder, np.array([vikt[k] for k in koder])

    def dra(self, bransch, storlek, rng, realiserade=None):
        """(ssyk, O*NET) för ett nytt jobb.

        realiserade är arbetsställets egna svenska yrken, ssyk -> O*NET. Har
        arbetsstället redan yrket återanvänds dess O*NET-kod: en SSYK3-grupp
        sprids av crosswalken på i median 19 koder med RMS 0,19 inom gruppen,
        och utan detta blev bilverkstadens mekaniker 21 olika yrken och ett
        arbetsställe nästan lika brett som kommunen. Över många arbetsställen
        är fördelningen densamma som om varje jobb dragits för sig. Ett nytt
        yrke dras ur crosswalken och läggs till i realiserade."""
        ssyk, ps = self._ssyk_fordelning(bransch, storlek)
        s_ = str(ssyk[int(rng.choice(len(ssyk), p=ps))])
        if realiserade is not None and s_ in realiserade:
            return s_, realiserade[s_]
        koder, po = self._onet[s_]
        kod = str(koder[int(rng.choice(len(koder), p=po))])
        if realiserade is not None:
            realiserade[s_] = kod
        return s_, kod
