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
