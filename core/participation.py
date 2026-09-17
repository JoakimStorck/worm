"""Arbetskraftsdeltagande per ettårsklass.

Modellen behöver veta vilka årskullar arbetskraften bor i. SCB redovisar
femårsgrupper på kommunnivå, så profilen byggs i tre steg: gruppernas
deltagande ur data, en monoton interpolation till ettårsklasser inom dem,
och ett antagande ovanför den ålder där data tar slut.

VAR DATA TAR SLUT. BAS redovisar klasserna 16-66, 20-66, 65-69 och 70-74 på
kommunnivå men publicerar dem inte: de är tomma i alla 290 kommuner, alla år
och båda tabellerna. Klassen 16-65 finns först från 2023, samma år som
riktåldern höjdes från 65 till 66. Arbetskraften vid 65 år går alltså att
räkna fram som differensen 16-65 minus 16-64, men vid 66 och uppåt finns
ingenting.

ANTAGANDET ÖVANFÖR 65 är en logistisk kurva i ålder, centrerad på
riktåldern och normerad så att den ansluter kontinuerligt till det uppmätta
värdet vid 65. Riktåldern är därmed en parameter att svepa, vilket är hela
poängen med att göra antagandet explicit: utträdets tidpunkt är en
policyfråga, och modellen ska kunna svara på vad den gör med vakansstocken.

SKARVEN. Det uppmätta värdet vid 65 kommer från 2024, då riktåldern var 66.
Höjs modellens riktålder till 67 ansluter kurvan fortfarande till ett värde
som speglar 66. Ett svep över riktåldern mäter därför effekten av utträdet
OVANFÖR 65, inte av att hela kurvan förskjuts. Att låta data flytta med
kräver en profil per riktålder, och den finns inte.
"""
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator

# Femårsgrupperna som BAS publicerar på kommunnivå, med det åldersintervall
# var och en täcker. 65 år står för sig själv: den kommer ur differensen
# mellan aggregaten och är ingen grupp.
GRUPPER = [("16-19", 16, 19), ("20-24", 20, 24), ("25-29", 25, 29),
           ("30-34", 30, 34), ("35-39", 35, 39), ("40-44", 40, 44),
           ("45-49", 45, 49), ("50-54", 50, 54), ("55-59", 55, 59),
           ("60-64", 60, 64)]
SISTA_MATTA_ALDERN = 65


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def grupptal(rader):
    """Arbetskraft och befolkning per grupp, plus 65 år ur differensen.

    rader är en DataFrame med age_group, in_labour_force och total för EN
    kommun och ETT år, som den ligger i labour_force_by_age.
    """
    k = rader.set_index("age_group")

    def par(grupp):
        if grupp not in k.index:
            return None
        return (float(k.loc[grupp, "in_labour_force"]), float(k.loc[grupp, "total"]))

    ut = []
    for namn, lo, hi in GRUPPER:
        p = par(namn)
        if p is None:
            raise ValueError(f"åldersgruppen {namn} saknas")
        ut.append((namn, lo, hi, p[0], p[1]))

    a64, a65 = par("16-64"), par("16-65")
    if a64 is not None and a65 is not None:
        # RÖJANDESKYDDET kan göra differensen negativ: BAS är skyddad med en
        # statistisk metod, och SCB påpekar att redovisade totaler inte alltid
        # är lika med summan av delarna. Storleksordningen är enstaka personer
        # mot en årskull på ett par hundra, så negativa värden nollas hellre
        # än att kastas.
        ut.append(("65", 65, 65, max(0.0, a65[0] - a64[0]),
                   max(0.0, a65[1] - a64[1])))
    return ut


def profil(rader, befolkning, retirement_age=67.0, retirement_spread=0.8,
           max_alder=74):
    """Deltagandet per ettårsklass som en Series indexerad på ålder.

    befolkning är folkmängden per ettårsklass för samma kommun (en Series
    indexerad på ålder), och används till att fördela gruppens arbetskraft
    inom gruppen. Skalningen per grupp gör att summan av de interpolerade
    ettårsklasserna blir gruppens uppmätta arbetskraft: en interpolation som
    inte bevarar summan hade ändrat arbetskraftens storlek, och då stämmer
    modellen inte längre mot SCB.
    """
    grupper = grupptal(rader)
    mitt = np.array([(lo + hi) / 2.0 for _, lo, hi, _, _ in grupper])
    q_grupp = np.array([(a / n if n > 0 else 0.0) for _, _, _, a, n in grupper])

    # PCHIP och inte spline: den är monoton mellan stödpunkterna och kan
    # därför inte svänga upp mellan 60-64 och 65, där kurvan faller brant.
    kurva = PchipInterpolator(mitt, q_grupp, extrapolate=True)
    aldrar = np.arange(16, int(max_alder) + 1)
    q = pd.Series(np.clip(kurva(aldrar.astype(float)), 0.0, 1.0), index=aldrar)

    # Skala inom varje grupp så att gruppens arbetskraft bevaras.
    #
    # NÄMNAREN ÄR PYRAMIDEN, inte BAS egen befolkningskolumn. Det är
    # pyramiden arbetskraften ska läggas på, så det är mot den summan
    # antalet måste stämma. De två källorna avgränsar nästan lika -- båda
    # räknar folkbokförda -- men inte exakt, och avviker de kraftigt är det
    # ett tecken på att fel år eller fel kommun jämförs.
    N = pd.Series(befolkning).reindex(aldrar).fillna(0.0).astype(float)
    for namn, lo, hi, _, n_grupp in grupper:
        if namn == "65" or n_grupp <= 0:
            continue
        n_pyramid = float(N.loc[[a for a in range(lo, hi + 1) if a in N.index]].sum())
        if n_pyramid > 0 and not 0.8 <= n_pyramid / n_grupp <= 1.25:
            print(f"[deltagande] {namn}: pyramiden har {n_pyramid:.0f} personer "
                  f"mot BAS {n_grupp:.0f} ({n_pyramid / n_grupp:.2f}x)")
    for _, lo, hi, a_grupp, _ in grupper:
        i = [a for a in range(lo, hi + 1) if a in q.index]
        namn = q.loc[i] * N.loc[i]
        if namn.sum() > 0:
            q.loc[i] = np.clip(q.loc[i] * (a_grupp / namn.sum()), 0.0, 1.0)

    # 65 år kommer ur differensen och ersätter det interpolerade värdet.
    for namn, lo, hi, a_grupp, n_grupp in grupper:
        if namn == "65" and n_grupp > 0:
            q.loc[65] = min(1.0, a_grupp / n_grupp)

    # ANTAGANDET ÖVANFÖR 65. Logistisk i ålder, centrerad på riktåldern och
    # normerad mot det uppmätta värdet vid 65, så att kurvan är kontinuerlig
    # i skarven. Bredden styr hur många år övergången tar.
    w = max(float(retirement_spread), 1e-6)
    R = float(retirement_age)
    ankare = _sigmoid((R - SISTA_MATTA_ALDERN) / w)
    for a in range(SISTA_MATTA_ALDERN + 1, int(max_alder) + 1):
        andel = _sigmoid((R - a) / w) / ankare if ankare > 0 else 0.0
        q.loc[a] = float(np.clip(q.loc[SISTA_MATTA_ALDERN] * andel, 0.0, 1.0))
    return q


def utträdeshasard(q):
    """Sannolikheten att lämna arbetskraften under året, per ålder.

    Faller deltagandet från q(a) till q(a+1) har andelen 1 - q(a+1)/q(a) av
    dem som var kvar lämnat. Det ersätter en absolut gräns vid riktåldern:
    utträdet fördelas över de åldrar där kurvan faller i stället för att alla
    lämna samma dag.

    Stigande deltagande ger hasard noll -- ingen kommer TILLBAKA in i
    arbetskraften av åldersskäl i modellen, och en negativ hasard hade varit
    just det.
    """
    q = pd.Series(q).astype(float)
    nasta = q.shift(-1)
    h = 1.0 - (nasta / q.where(q > 0))
    h = h.clip(lower=0.0, upper=1.0).fillna(0.0)
    # Sista åldern i profilen: alla som är kvar lämnar, annars blir det
    # hundraåringar i arbetskraften.
    h.iloc[-1] = 1.0
    return h
