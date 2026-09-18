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
