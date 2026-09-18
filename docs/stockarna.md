# Arbetsmarknadens stockar och jämviktsläget (spår C)

Utredningen av varför arbetslösheten fortsätter falla efter uppstarten, även
utan åldrande och inträde. Slutsatser och beslut från dialogen 2026-09-18.

## Identiteten

Med arbetskraften L och antalet positioner J fasta gäller exakt, på individnivå
i loggen:

    U = (L − J) + V + In − Ut

V är `unmatched_jobs`: alla obesatta aktiva positioner i regionen, också de
UTLOVADE där någon tackat ja men inte tillträtt. Identiteten är en
bokföring, inte en modell, och den gör att arbetslöshetens rörelse kan delas
upp utan antaganden.

## Mätningen: det var inte relaxation

Uppstart i ordningen svag, stark, mitten, fem år utan demografi, frö 1
(`output/run_20260918_204749`). L = 17 356, J = 16 839, målen för pendlingen
in 1 727 och ut 1 767.

| år | U | V | In | Ut | ΔU | varav ΔV | varav Δ(In−Ut) |
|---|---|---|---|---|---|---|---|
| 0 | 2 338 | 1 645 | 1 258 | 1 082 | | | |
| 1 | 2 117 | 1 484 | 1 788 | 1 657 | −221 | −161 | −45 |
| 2 | 1 671 | 1 157 | 2 078 | 2 066 | −446 | −327 | −119 |
| 3 | 1 485 | 1 127 | 2 266 | 2 415 | −186 | −30 | −161 |
| 4 | 1 273 | 1 112 | 2 433 | 2 780 | −212 | −15 | −198 |
| 5 | 1 117 | 1 087 | 2 482 | 2 960 | −156 | −25 | −131 |

Vakanserna sätter sig på omkring två år. Från år 3 är det pendlingen som bär
hela fallet, och den har inte stannat efter fem år. Förklaringen i
`utbildningsmodell.md` (6a-i, uppstartens ordning), att resten var "modellens
egen relaxation genom jobbens omsättning", var fel: den bygger på att
arbetslösheten faller, inte på vad som fyller hålet.

## Tre fel

**1. Jobbmålet är sysselsatta, modellen läser det som positioner.** J är
pendlingsmatrisens kolumnsumma (`pendlingsmarginaler`): personer sysselsatta
med arbetsställe i kommunen, alltså BESATTA jobb. Modellen skapar J
positioner och låter en del stå lediga, så varje vakans är en sysselsatt för
lite:

    U = 477 + V + (In − Ut − (1 727 − 1 767))

där 477 är SCB:s arbetslöshet, 2,75 procent. Sambandet u = u_min + V/L stod
redan i `faktisk_arbetsloshet`; slutsatsen, att positionerna måste vara fler
än de sysselsatta, drogs inte.

**2. Utpendlingens stock har ingen jämvikt vid målet.** Externa erbjudanden
förbrukas inte som regionens vakanser: andelen `utpendling_erbjudande_andel`
av sökningarna får ett erbjudande oavsett hur många som redan pendlar ut.
Stocken sätts då av inflöde mot avgång. År 1 är inflödet 1 280 och avgången
omkring 0,54 per år (532 uppsägningar och 226 förstörda jobb på en stock
kring 1 400), vilket ger en jämvikt kring 2 400 -- och inflödet växer. O5
kalibrerade andelen mot NIVÅN år 1, mitt i förloppet. Hälften av
erbjudandena tas av sysselsatta.

**3. Inpendlarnas utträde hänger på demografin.** Utträdet till reservoaren
ligger i `_aldras_och_pensioneras`, som hoppas över helt med
`simulation.demografi: false`. Reservoaren får då omkring 870 jobb om året och
lämnar dem bara när jobbet förstörs eller sägs upp.

## Vakansgraden i data

SCB:s konjunkturstatistik över lediga jobb, TAB6605 (hela ekonomin, per län,
lediga jobb per 100 anställningar), medel 2024K2–2026K2:

| | lediga jobb, totalt | med omgående tillträde |
|---|---|---|
| Dalarnas län | 2,03 % (kvartal 1,4–2,6; osäkerhet ±0,4–0,8) | 1,20 % |
| Norra Mellansverige | 2,32 % | 1,40 % |
| Riket | 2,57 % | 1,68 % |

Tabellen börjar 2024K2; pendlingsmatrisen är 2023. Den äldre serien, TAB4304
(bara näringslivet, NUTS2), ger för Norra Mellansverige 2023
rekryteringsgraden 2,40 (samma begrepp som "totalt") och vakansgraden 0,95
(motsvarar "omgående"). Nivån flyttar sig inte mellan åren så att det spelar
roll här.

Modellen, stationärt från år 2:

| | andel av J |
|---|---|
| öppna vakanser | 4,75 % (~800) |
| utlovade, ej tillträdda | 1,8 % (~300) |
| V i identiteten | 6,5 % (~1 100) |

De öppna vakanserna svarar mot "lediga jobb, totalt": SCB räknar en
befattning som ledig så länge arbetsgivaren söker, också med tillträde längre
fram, men inte när den är tillsatt. Modellen ligger 2,3 gånger över Dalarna.

## Beslut

1. **Måttet är "lediga jobb, totalt", per län, medel över alla kvartal.**
   Varje kommun får sitt läns grad. Modellen har ingen säsong, och ett
   enskilt läns kvartal är för osäkert för att bära en nivå.
2. **Positionerna är J_data · (1 + v\*).** De utlovade positionerna läggs
   INTE till nu. Strikt hör de dit -- den som är under uppsägning räknas som
   sysselsatt en gång, på det gamla jobbet, och den väntande befattningen
   finns inte i J_data -- men andelen är modellens egen (anställningstakt
   gånger väntetid) och kan inte läsas ur SCB. Tills uppsägningstiderna är
   granskade (punkt 4) syns de som friktion i arbetslösheten.
3. **Ordningen 1 → 2 → 3 → 4**, en mekanism per commit:
   1. jobbmålet räknar in vakanserna,
   2. utpendlingen blir ett bestånd av platser i omgivningen som tas i
      anspråk och frigörs, inte en ström av erbjudanden,
   3. inpendlarnas utträde kopplas loss från demografin,
   4. modellens vakansnivå mäts mot data.

## Vad rättelsen av jobbmålet inte löser

Med v\* = 2,03 % tillkommer 342 positioner. Den stationära arbetslösheten blir
omkring 477 + 1 100 − 342 ≈ 1 235, alltså 7,1 procent mot SCB:s 2,75.
Rättelsen är nödvändig men tar en tredjedel av överskottet. **Resten är
modellens egen vakansnivå**, och den är huvudfrågan efter steg 1–3: omkring
0,3 anställningar per besatt jobb och år och cirka 50 dagars öppen vakans,
mot SCB:s 2 procent. Vilken av de två som är fel, och om rekryteringen i
verkligheten börjar redan under den avgåendes uppsägningstid, är punkt 4.

Uppvärmningens längd avgörs först därefter. Vakanserna sätter sig i dag på
omkring två år.

## C1 prövad (2026-09-18)

Positionerna blev 17 181 mot 16 839. Fem år utan demografi, frö 1
(`output/run_20260918_212927`), mot körningen ovan:

| | före | med C1 |
|---|---|---|
| U vid start | 2 338 | 2 664 |
| U år 5 | 1 117 | 1 110 |
| öppna vakanser år 4 | 4,74 % | 5,11 % |
| Ut / In år 5 | 2 960 / 2 482 | 2 801 / 2 555 |

**År 5 syns rättelsen inte i arbetslösheten.** Av de 342 positionerna blev
omkring 100 fler vakanser och omkring 230 mindre nettopendling; tio blev färre
arbetslösa. Så länge utpendlingen är en ström som inte töms (fel 2) sätts
arbetslösheten av flödesbalansen, inte av bokföringen. C1 kan visa sin verkan
först efter C2.

**Startens högre arbetslöshet var världen, inte C1.** Med fler positioner blir
varje arbetsgivardragning en annan, och byggarens frö är scenariofilens
`seed: 12345`, inte `WORM_SEED`. Uppstarten ensam, frö 1:

| genereringsfrö | utan v\* | med v\* |
|---|---|---|
| 12345 | 2 419 | 2 664 |
| 12346 | 2 616 | 2 549 |
| 12347 | 2 478 | 2 505 |
| medel | 2 504 | 2 573 |

Matchningsfröna 1–3 i samma värld skiljer ±30; världarna ±100. De tillagda
positionerna blir vid start nästan helt vakanser (medel 2 188 mot 1 794).

**Följd för alla jämförelser:** `WORM_SEED` varierar bara matchningen och
körningen. Baslinjens fem frön delar en genererad värld och underskattar
spridningen. Ett beslut om genereringsfröet ska följa `WORM_SEED` hör till
nästa baslinje, inte till C1.

## C2 prövad (2026-09-18)

Omgivningen har platser per par av hemkommun och destination, lika många som
pendlingsmatrisen anger (1 767 för Ovansiljan). Ett erbjudande utifrån kommer
bara från en ledig plats, destinationen dras bland de lediga med antalet
lediga som vikt, och platsen frigörs när jobbet lämnas eller förstörs.
`utpendling_erbjudande_andel` är nu takten en ledig plats fylls med, inte
stockens nivå. Fem år utan demografi, frö 1 (`output/run_20260918_214539`):

| år | U | V | In | Ut | antagna utifrån |
|---|---|---|---|---|---|
| 0 | 2 687 | 2 306 | 1 247 | 1 041 | 1 033 |
| 1 | 2 215 | 1 773 | 1 804 | 1 518 | 973 |
| 2 | 1 789 | 1 222 | 2 118 | 1 701 | 775 |
| 3 | 1 734 | 1 021 | 2 268 | 1 712 | 689 |
| 4 | 1 732 | 925 | 2 370 | 1 722 | 700 |
| 5 | 1 659 | 812 | 2 410 | 1 718 | |

Utpendlingen står still vid 97 procent av matrisen från år 2, och
inflödet har sjunkit till avgången, omkring 700 om året. Arbetslösheten är
platt år 2–4.

**Kvar är fel 3.** Vakanserna faller fortfarande, och det är inpendlarna som
tar dem: 2 410 mot matrisens 1 727, utan avmattning. Med demografin avstängd
lämnar de bara när jobbet förstörs eller sägs upp.

**Uppstarten fyller inte platserna.** Den når 1 041 av 1 767; taket på tre
försök utifrån per person och andelen 0,2 räcker inte. Stocken når målet
först år 2. Det hör till primingen (`omgivning.md`: "Primingen börjar med de
observerade pendlarna på plats") och är inte C2.

## C3 prövad (2026-09-18)

Avstängd demografi rör nu bara invånarna: anställda inpendlare möter sin
kommuns utträdeshasard vid sin fasta ålder och återgår till reservoaren också
utan demografi. Fem år, frö 1 (`output/run_20260918_215751`):

| år | U | V | In | Ut | inpendlare som lämnat |
|---|---|---|---|---|---|
| 1 | 2 215 | 1 799 | 1 778 | 1 518 | 26 |
| 2 | 1 801 | 1 285 | 2 083 | 1 711 | 39 |
| 3 | 1 659 | 1 007 | 2 213 | 1 714 | 30 |
| 4 | 1 663 | 926 | 2 301 | 1 726 | 38 |
| 5 | 1 604 | 808 | 2 372 | 1 730 | |

**Rättelsen är riktig men liten.** Utträdet är profilens hasard i arbetsför
ålder, omkring 1,7 procent om året, och tar 30–40 inpendlare om året.
Inpendlarna växer ändå, 2 083 → 2 372 mot matrisens 1 727, och tar
vakanserna.

**Det är samma fel som i C2, på andra sidan randen.** Inpendlarnas
sökintensitet (`inpendling_sokfaktor` 25) kalibrerades i O5 mot nivån år 1.
Stocken sätts av hur ofta reservoaren vinner regionens vakanser mot hur ofta
inpendlarna lämnar, och ingenting förankrar den vid matrisen. Med In vid
målet hade arbetslösheten år 5 varit omkring 1 604 − (2 372 − 1 727) ≈ 960,
5,5 procent. Hur inpendlingen ska förankras är ett designbeslut (C2b) och
inte gjort här: till skillnad från utpendlingen, där omgivningen är
efterfrågan, är efterfrågan här regionens egen, och när invånarna går i
pension utan att ersättas ska inpendlingen kunna växa.

## C2b prövad (2026-09-18)

Inpendlingen har platser per par av ursprung och arbetskommun, lika många som
matrisens inpendling (1 727 för Ovansiljan). Upptagna är parets
reservoarmedlemmar som är anställda i regionen eller har tackat ja; de räknas
ur tabellen vid varje fråga. En reservoarmedlem söker inte och är inte
behörig i urvalet när paret är fullt. En anställd inpendlare som byter jobb
behöver ingen ny plats. Valt framför en omkalibrerad sökfaktor, som hade
gällt en kommun och glidit med demografin, och framför en modell av
reservoarens hemmamarknad. Att inpendlingen ska kunna växa när regionen
stramas åt är en egen mekanism, att pröva mot matrisens tidsserie när
inträdet och flyttningarna finns. Fem år, frö 1 (`output/run_20260918_221128`):

| år | U | V | In | Ut | u |
|---|---|---|---|---|---|
| 0 | 2 687 | 2 306 | 1 247 | 1 041 | 15,5 % |
| 1 | 2 124 | 1 938 | 1 598 | 1 572 | 12,3 % |
| 2 | 1 643 | 1 566 | 1 628 | 1 702 | 9,5 % |
| 3 | 1 356 | 1 261 | 1 649 | 1 713 | 7,8 % |
| 4 | 1 258 | 1 160 | 1 652 | 1 709 | 7,3 % |
| 5 | 1 190 | 1 065 | 1 677 | 1 717 | 6,9 % |

Båda pendlingsstockarna står still vid 96–97 procent av matrisen från år 2.
Det som rör sig är vakanserna, som invånarna nu fyller i stället för
inpendlarna, och de faller fortfarande omkring 100 om året. Det är C4.

## C4: vakansnivån, mätt (2026-09-18)

C3-körningen, år 3–4 (C2b ändrar inte vakansernas mekanik):

| | modellen |
|---|---|
| tillsättningar i regionen | 3 681 om året, 0,226 per besatt jobb |
| varav vinnaren anställd (byte) | 60 procent |
| vakansens ålder vid beslut | p10 40, median 42, medel 61, p90 63 dagar |
| väntan till första sökande | median 2, medel 21 dagar |
| öppen tid (Littles lag) | 64 dagar |
| utlovad tid (beslut + uppsägning) | 26 dagar |

**Den öppna tiden är nästan helt parametrar.** Annonsen öppnar vid första
ansökan och stänger efter `application_window_days` = 40: medianen 42 är
fönstret. Medlet dras upp av en svans som väntar länge på första sökande.

**Vad data kräver.** Med SCB:s 2,03 procent och modellens anställningstakt
0,226 blir den öppna tiden 0,0203/0,226 · 365 ≈ 33 dagar, hälften av
modellens. Anställningstakten själv är inte prövad mot data: SCB:s
statistikdatabas har ingen tabell över nyanställningar eller jobbflöden.

**Rekryteringen börjar för sent.** Vid ett byte behåller den som går sitt jobb
under uppsägningstiden, och positionen blir ledig först när hon tillträder
det nya -- först då öppnar annonsen. I verkligheten rekryterar arbetsgivaren
under uppsägningstiden, och SCB räknar en befattning som "snart blir ledig"
som ett ledigt jobb. 60 procent av tillsättningarna är byten, så varje byte
ger en kedja av tomma positioner som i verkligheten till stor del överlappar.

Tre spakar, i den ordning de bör prövas:
1. **Rekrytering under uppsägningstiden.** Annonsen öppnar när uppsägningen
   lämnas, inte när positionen blir tom. Strukturell, och den gör modellens
   lediga jobb jämförbara med SCB:s begrepp.
2. **Ansökningsfönstret.** 40 dagar är en fast minsta vakanstid. Kortare, eller
   ett löpande urval, men först efter 1: fönstret överlappar då
   uppsägningstiden.
3. **Bytestakten.** 60 procent av 0,226 är 0,136 byten per jobb och år; TODO
   anger omkring 10 procent som mål (`on_the_job_search_factor`). Fler byten
   ger fler kedjor av vakanser.

## Arbetslöshetsmåttet (2026-09-18)

**Jämförelsen var mellan två olika begrepp.** SCB:s tal i
`labour_market_status` (2,35, 3,51 och 3,17 procent; 2,75 för Ovansiljan) är
BAS, registerbaserad arbetsmarknadsstatistik för november 2023, 20–65 år:
sysselsatt är den som haft betalt arbete någon gång under månaden, arbetslös
den som inte haft det och är inskriven på Arbetsförmedlingen. Modellens
`unemployed_individuals` är en ögonblicksbild, där varje kort glapp mellan
två jobb och varje väntan på tillträde räknas, i åldrarna 15–74.
Analysrapportens referens, 7,5 procent "svensk arbetslöshet", var AKU för
riket -- ett tredje begrepp.

Resten av underlaget är också BAS med november som referens:
pendlingsmatrisens sysselsatta, dagbefolkningen och arbetskraftsprofilerna.
Det är därför BAS modellen ska mätas mot.

**Nu:** `arbetsloshet_bas` (`core/statistics/basic_stats.py`) räknar vid varje
månadsskifte invånarna 20–65 år som varit arbetslösa hela månaden
(`unemployed_since` före månadens början), mot invånarna 20–65 år i
arbetskraften. Månadsraden bär `unemployed_bas` och `labour_force_bas`,
tidsserien `u_bas` och sammanfattningen `u_bas_pct`. Rapporten jämför
`u_bas_pct` med SCB:s tal för scenariots kommuner tillsammans och har ingen
referens för ögonblicksbilden. Identiteten U = L − J + V + In − Ut är
bokföring och räknas som förut på ögonblicksbilden.

Skillnaden i slutläget för svepet i C4 (fem år, frö 1):

| fönster | ögonblick | hela sista månaden | därav 20–65 |
|---|---|---|---|
| 40 | 6,95 % | 6,08 % | 6,00 % |
| 30 | 6,28 % | 5,49 % | 5,44 % |
| 20 | 5,77 % | 4,99 % | 4,84 % |
| 15 | 5,55 % | 4,79 % | 4,67 % |

**Inte modellerat:** inskrivningen. En arbetslös som inte är inskriven är i
BAS utanför arbetskraften; modellen har ingen sådan skillnad, så dess tal är
en övre gräns för BAS.

**På datasidan:** arbetskraften räknas bakåt som L = syss / (1 − u) med
syss för 15–74 år ur pendlingsmatrisen och u för 20–65 ur
arbetsmarknadsstatusen. Det går inte att rätta med ett u för 15–74: BAS
redovisar arbetslösa bara för 20–65 (TAB2921 har ".." för 15–74, 15–19 och
65–74), eftersom begreppet vilar på inskrivningen. Strikt vore L = syss +
syss(20–65) · u/(1 − u); skillnaden för Ovansiljan är omkring 54 arbetslösa
(1 893 sysselsatta utanför 20–65 gånger 2,8 procent), 0,3 procent av
arbetskraften, och de ligger utanför åldrarna som modellens mått räknar.

**Noterat:** den som väntar på tillträde och förlorar jobbet innan
(`job_gone_before_start`) får `unemployed_since` nollställd fast hon aldrig
arbetade. Det gör henne till nyinskriven i måttet och i anspråkets sänkning.

## C4, prövat (2026-09-18)

**Bytestakten styr inte vakansnivån.** Svep av `on_the_job_search_factor`,
fem år, frö 1, fönster 40:

| faktor | byten per år | tillsättningar per besatt | öppna år 4 | utlovade år 4 | vakansens ålder, medel | u_bas år 5 |
|---|---|---|---|---|---|---|
| 10 | 16,2 % | 0,248 | 4,80 % | 1,74 % | 69 d | 5,98 % |
| 14 | 13,9 % | 0,228 | 4,89 % | 1,54 % | 82 d | 5,81 % |
| 18 | 11,7 % | 0,205 | 4,78 % | 1,31 % | 83 d | 5,58 % |
| 24 | 10,2 % | 0,192 | 4,77 % | 1,17 % | 95 d | 5,24 % |

Färre sökande anställda ger färre tillsättningar, men varje vakans väntar
längre på sina sökande, och stocken står still. Faktorn ändras inte: den är
satt mot sökfrekvensen (1,1 sökning per anställd och år, AKU:s nivå; se
kommentaren i `_simulation_defaults.yml`, 0090), och bytena ska enligt samma
beslut bäras av ingångslönens rabatt. **Att bytena är 16 procent om året mot
omkring 10 är en egen kalibreringsfråga, utanför C4.**

**Vakansstocken sätter sig fortfarande år 4–5.** Vakanser äldre än ett år är
2–4 procent av tillsättningarna år 3–4 men 26–41 procent av vakansdagarna,
med p99 på 1 000–1 300 dagar: positioner skapade under det första året, när
mismatchen efter uppstarten var störst. I slutläget år 5 är bilden en annan:

| fönster | öppna år 5 | varav lediga sedan t = 0 | uppstått under körningen |
|---|---|---|---|
| 40 | 3,74 % | 0,28 % | 3,46 % |
| 15 | 2,16 % | 0,23 % | 1,93 % |

Årsmedlen ovan överskattar därför det stationära läget, och fönstret prövas
över tio år.

## C4b: ansökningsfönstret (2026-09-18)

Tio år, frö 1, medel år 5–9 (stocken har satt sig från år 5):

| fönster | öppna vakanser | utlovade | u_bas |
|---|---|---|---|
| 40 | ~4,6 % | 1,5 % | ~5,9 % |
| 25 | ~3,4 % | 1,9 % | ~5,3 % |
| 20 | ~3,1 % | 1,8 % | ~4,9 % |
| 15 | ~3,0 % | 1,5 % | ~4,5 % |

SCB:s rekryteringstid (TAB4307) är lediga jobb genom nyanställningar, samma
Littles lag som modellens öppna tid, och ligger på 32 dagar för näringslivet
2022–2024. Med rekryteringsgraden 2,7 procent ger den en anställningstakt
kring 0,3 per jobb och år; modellens 0,25 är i rätt storleksordning. Det var
tiden per vakans som var för lång: 64–69 dagar med fönstret 40, omkring 45
med 20. **Fönstret sätts till 20 dagar.** Under 20 planar nivån ut kring 3,0
procent, och där sätts golvet av vakanser som länge saknar lämplig sökande.

Kvar av skillnaden mot SCB, med fönstret 20: öppna vakanser omkring 1
procentenhet över Dalarnas 2,03, och de utlovade positionerna, omkring 1,8
procent av jobben, som ännu inte finns i jobbmålet (C4c). Väntan på
lämpliga sökande är en egen fråga om mismatch, inte om rekryteringens
tider.

## Rekryteringstiden per bransch: tiden ligger på fel ställen (2026-09-18)

SCB:s rekryteringstid varierar med läget i uppgiftsrummet, T = 47,7 +
χ(2,2 cos ξ + 156,5 sin ξ) över näringsgrenarna (TAB4307, 2023,
`scripts/rekryteringstid_mot_uppgiftsrum.py`). Aggregatet räcker därför inte
som prövning. Modellens motsvarighet per bransch, öppen stock i slutläget
genom tillsättningar per år (år 5–9), tio år, frö 1, fönstret 20
(`output/run_20260918_224453`):

| bransch | jobb | öppna | modell, dagar | SCB, dagar |
|---|---|---|---|---|
| B+C tillverkning | 2 088 | 25 | 23 | 47 |
| D+E energi | 200 | 1 | 10 | 71 |
| F bygg | 2 014 | 23 | 20 | 33 |
| G handel | 1 695 | 44 | 39 | 30 |
| H transport | 627 | 11 | 29 | 26 |
| **I hotell och restaurang** | 737 | **58** | **121** | **12** |
| J information och kommunikation | 115 | 2 | 27 | 81 |
| K+L finans, fastighet | 329 | 10 | 48 | 40 |
| M+N företagstjänster | 1 021 | 24 | 38 | 49 |
| P+Q utbildning, vård | 6 091 | 127 | 31 | 25 |
| R+S+T+U övrigt | 764 | 18 | 38 | 21 |

Korrelationen mot SCB är **negativ**, −0,55 (−0,36 med fönstret 40). Nivån
totalt är ungefär rätt, men tiden ligger där verkligheten är snabbast, och de
långa rekryteringarna i SCB -- IT, energi, tillverkning -- går fort i
modellen.

**Hotell och restaurang bär överskottet.** 7,9 procent av branschens jobb står
öppna, i median 283 dagar, mot SCB:s kortaste rekryteringstid, 12 dagar. Det
är inte geografin: 43 av 58 ligger i Mora. Det är inte kraven: r_req 0,08 i
median. Det är lönen. De öppna betalar i median 0,56, de besatta i samma
bransch 0,69, och de arbetslösas anspråk ligger i median på 0,68 (p25 0,55).
Jobben är för dåligt betalda för de arbetslösa som finns.

I verkligheten fylls de av dem modellen saknar: unga på väg in, studerande,
nyanlända -- de med lägst anspråk och kortast erfarenhet. **Golvet kring 3
procent öppna vakanser är alltså inte i första hand kompetens-mismatch utan
det saknade inträdet (6b).** Att kalibrera vakansnivån vidare innan inträdet
finns vore att kalibrera bort en frånvaro.

Mätningen är en ögonblicksbild av stocken och brusig för små branscher (J har
115 jobb). Mönstret i I är inte brus.
