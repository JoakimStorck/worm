# Omgivningen — regionens öppna rand

Ett scenario simulerar en eller ett fåtal kommuner. I verkligheten går
pendling och flyttningar alltid över regionens gräns, och att stänga gränsen
gör regionen till en annan arbetsmarknad än den verkliga. Detta dokument
beskriver hur gränsen öppnas mot en diffus **omgivning**. Beslutat
2026-09-18; byggordningen står sist.

---

## Varför gränsen inte kan stängas

Fram till nu är scenariot slutet. `ScenarioBuilder.jobbandelar` tar jobben
per kommun ur den del av pendlingsmatrisen där både bostad och arbetsställe
ligger i scenariot, så att summan jobb är lika med summan sysselsatta
invånare. Jobb som innehas av pendlare utifrån tas bort, och invånare som
arbetar utanför finns inte som sysselsatta någonstans.

Pendlingsmatrisen (`commuting`, SCB 2023) täcker alla 290 × 290 kommuner, så
gränsflödena kan räknas för varje scenario:

| scenario | utpendling, andel av boende sysselsatta | inpendling, andel av jobben |
|---|---|---|
| Ovansiljan (Mora, Orsa, Älvdalen) | 10,5 % (1 767) | 10,3 % (1 727) |
| Göteborg ensam | 18,6 % | 34,1 % |
| Oxelösund ensam | 43,5 % | 45,1 % |
| Åre ensam | 23,2 % | 15,0 % |

Ovansiljans utpendling går främst till Falun, Rättvik, Malung-Sälen, Borlänge
och Stockholm; inpendlingen kommer främst från Rättvik. För ett scenario med
en enda kommun är gränsen ofta det dominerande draget: Oxelösund utan sin
pendling är inte Oxelösund.

---

## Omgivningen som randvillkor

Omgivningen är stor mot regionen. Den behandlas därför som **exogen**: en
reservoar som regionen utbyter människor med, men som regionen inte påverkar.
Den beskrivs av data och simuleras inte med egna arbetsgivare eller
individer. Tre flöden går genom randen.

### 1. Utpendling

Regionens invånare kan få erbjudanden om jobb utanför regionen.

- **Destinationen** dras ur invånarens kommuns utpendling i matrisen, så att
  Moraborna i första hand erbjuds jobb i Falun och Rättvik.
- **Yrket** dras ur destinationskommunens profil i TAB4436 (dagbefolkning),
  samma underlag som regionens egna jobb (`core/bransch.py`).
- **Platsen** är en DeSO i destinationskommunen, dragen med befolkningen som
  vikt (`Omgivning.dra_plats`), så pendlingskostnaden räknas med den geometri
  som redan finns. Kommunens yta hade hamnat långt från där folk bor (33 km
  fel i Älvdalen), och befolkningen är en approximation av var jobben ligger.
- **Priset** är fältets pris för yrket, som för alla jobb.
- **Inget arbetsställe.** Ett externt jobb uppstår när erbjudandet görs och
  upphör när anställningen upphör. Det har ingen arbetsgivare och ingen
  vakans i regionens bokföring.
- **Takten** kalibreras så att stocken av utpendlare per kommun motsvarar
  matrisen. Separationen följer samma regler som för regionens jobb.

### 2. Inpendling: en reservoar (avgjort 2026-09-18)

Regionens vakanser får sökande utifrån, ur en **inpendlingsreservoar**:
personer som bor i omgivningen, skapade vid start.

- **De är riktiga agenter**, med kompetenscirklar, reservationslön och ålder,
  eftersom hela poängen är att de konkurrerar med regionens egna. De genereras
  med samma funktion som regionens invånare (`generate_individuals`), i sina
  egna kommuner: ålder, utbildning och yrke ur ursprungskommunens underlag,
  bostad i en DeSO där. Ursprungen dras ur regionens inpendling i matrisen.
- **Varför en reservoar** och inte agenter som skapas vid ansökan och tas bort
  när de lämnar: urvalet bedömer de sökandes konkurrenskraft ur deras rad i
  kompetenscirklarna, så varje extern sökande -- också den som inte får jobbet
  -- hade behövt en rad, och rader kan inte tas bort utan att individernas
  index förskjuts. Reservoaren återanvänder sökning, urval, löner och
  kompetens utan specialfall.
- **Status `extern`.** De ingår inte i regionens arbetskraft. Deras läge i
  omgivningen modelleras inte: de söker med anspråket ρ·Π som en invånare vid
  start, och det sänks inte med tiden. Hemyrkets cirkel är aktiv, eftersom de
  arbetar i omgivningen. Anställs de blir de inpendlare (`employed`,
  `extern`); lämnar de jobbet -- förstört, uppsägning, uppehåll, tillträde som
  gick förlorat -- återgår de till reservoaren och blir inte arbetslösa här.
- **Stationär.** Reservoaren åldras inte och lämnar inte arbetskraften.
- **Storlek och takt.** `inpendling_reservoar_faktor` (3,0) gånger
  matrisens inpendlingsstock ger urval; `inpendling_sokfaktor` (5,0, samma som
  de anställdas) styr hur många som anställs och kalibreras i O5.
- **Vid start** söker en delmängd lika stor som stocken (`extern_start`) med i
  uppstartsmatchningen.

### 3. Flyttningar

Utflyttare lämnar till omgivningen och inflyttare kommer därifrån, per kommun,
ålder och kön ur TAB1212 (flyttningar efter region, ålder och kön,
1997–2024). Studieflyttningen blir ett specialfall: unga flyttar ut för att
studera, och en andel kommer tillbaka med eftergymnasial utbildning, vilket
TAB6928 (utbildningsflöden) kan bära. Det löser den parkerade frågan om
studieorten (`utbildningsmodell.md`, "Två situationer") utan att modellen
behöver lärosäten.

**Flyttningarna byggs tillsammans med inträdet (steg 6b i
`utbildningsmodell.md`)**, eftersom studieflyttningen kräver
utbildningshistorik. Omgivningen utformas nu så att den kan bära dem.

---

## Följder

**Bokföringen.** U = L − J + V gäller bara i ett slutet system. Med randen:

- regionens jobb = invånare som arbetar i regionen + inpendlare + vakanser
- invånarnas sysselsatta = de som arbetar i regionen + utpendlare
- arbetskraften L = invånarna; inpendlarna ingår inte

Identitetskontrollen i rapporten och i `check_invariants.py` skrivs om.

**Jobbmålet** blir alla jobb i regionens kommuner, kolumnsumman i hela
matrisen, i stället för delmatrisens. Nivån är sysselsatta med arbetsställe i
kommunen, inklusive företagare, som TAB4436 saknar.

**Primingen (steg 6a)** börjar med de observerade pendlarna på plats:
inpendlare i regionens jobb och utpendlare i externa jobb.

**Ovansiljan är ett testfall.** Allt ovan ska fungera för varje kommun och
varje kombination; matrisen, TAB4436 och kommungeometrin täcker riket.

---

## Beslut

1. Inpendlare är fullvärdiga agenter medan de arbetar i regionen.
2. Omgivningen är exogen: takterna kalibreras mot matrisens stockar. Att den
   svarar på regionens löner är ett senare steg.
3. Omgivningen utformas för att bära flyttningar, men pendlingen byggs först;
   flyttningarna byggs med inträdet.
4. Omgivningen kommer före primingen (6a), och den nya baslinjen väntar tills
   pendlingen finns.

---

## Byggordning

Varje steg är en egen commit med tester. Mellanlägena mellan O2 och O5 är
inte kalibrerade och körs inte som baslinje.

- **O1. Underlaget.** **Gjort** (`core/omgivning.py`): för ett scenarios
  kommuner, utpendlingen per destination och inpendlingen per ursprung ur
  matrisen, och platser i en DeSO dragen med befolkningen. Ingen
  beteendeändring.
- **O2. Bokföringen.** Individer och jobb bär om de är externa;
  identitetskontrollen räknar med inpendlare och utpendlare (noll tills
  flödena finns). Ingen beteendeändring. **Gjort:** kolumnen `extern`,
  `analyze_world` räknar arbetskraften bland invånarna och jobben bland
  regionens, månads- och årsraderna bär `in_commuters` och `out_commuters`,
  och tidsseriens residual är U − (L − J + V + In − Ut).
- **O3a. Jobbmålet.** **Gjort:** `ScenarioBuilder.pendlingsmarginaler` tar
  jobben ur hela kolumnsumman och de sysselsatta invånarna ur hela radsumman,
  också för en ensam kommun; `jobbandelar` och delmatrisen är borta. Utan
  O3b och O4 fyller invånarna inpendlarnas jobb, så läget körs inte.
- **O3b. Inpendlingen.** **Gjort:** reservoaren enligt avsnitt 2. Provkörning,
  Ovansiljan, två år, frö 1: 5 181 i reservoaren ur 98 kommuner; inpendlare
  649 vid start, 1 122 efter ett år och 1 370 efter två, mot matrisens 1 727.
  Per arbetskommun efter två år Mora 1 063, Orsa 210, Älvdalen 67, mot 1 374,
  124 och 229. Identiteten håller exakt. Reservoarens generering, 98 kommuner
  genom generate_individuals, lägger omkring 70 sekunder till uppbyggnaden.
- **O4. Utpendling.** Externa erbjudanden till invånarna, externa jobb utan
  arbetsställe. Startens utpendlare på plats. **Gjort** (`externt_erbjudande`
  och `anta_externt` i `core/matching_core.py`, `World.skapa_externt_jobb`):
  vid en andel `utpendling_erbjudande_andel` (0,1) av invånarnas sökningar
  kommer ett erbjudande ur destinationens jobbfördelning i TAB4436, med mötet
  min(1, q) utan avståndsdämpning -- destinationen bär redan avståndet -- och
  överskottet mot hennes läge nu. Det externa jobbet är utlovat från start,
  aldrig en vakans, förstörs i regionens takt och upphör när det lämnas.
  Provkörning, två år, frö 1: 106 utpendlare vid start, 176 efter två år, mot
  matrisens 1 767; de antagna jobben ligger i median 43 km bort, matrisens
  utpendling 76 km. Pendlingskostnaden 0,005 per km, kalibrerad för lokal
  pendling, gjorde de längre arbetsresorna olönsamma, och en fjärdedel av
  matrisens utpendling ligger över 215 km.
- **O4b. Ingen pendlingskostnad för externa erbjudanden** (avgjort
  2026-09-18). Långpendlare arbetar ofta ett par dagar i veckan på plats och
  reser med tåg, resten hemifrån; pendling till grannkommuner sker med bil,
  buss eller tåg. Modellen ska inte hantera sådana specialfall nu. Matrisen
  är observerat beteende och bär redan hur långt och hur ofta folk pendlar,
  så erbjudandet värderas på lön mot hennes läge nu, och takten kalibreras
  mot stocken (O5). Provkörning, två år, frö 1: utpendlare 1 183 vid start,
  1 078 efter ett år, 1 033 efter två, mot 1 767; de antagna jobben ligger i
  median 94 km bort, matrisens 76. Uppstarten når sitt tak på 40 omgångar,
  eftersom varje omgång ger några externa tillsättningar.
- **O5. Kalibrering.** Takterna mot matrisens stockar per kommun; mäts över
  körningen, för Ovansiljan och för kommuner med annan pendling (Oxelösund,
  Göteborg, Åre).
- **Därefter** 6a (priming), ny baslinje, och flyttningarna med 6b.
