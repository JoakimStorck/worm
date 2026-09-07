# Individmodellen — arbetarens representation i uppgiftsrummet

Detta dokument specificerar hur en individ representeras i WORM, hur hon
matchas mot jobb, hur lönen bestäms och hur hon rör sig. Det är resultatet av
en genomgång av papper 1 (*The Polar Geometry of Work*) och papper 2 (*Two
scales of occupational mobility*), och av att den ursprungliga individmodellen
i WORM skrevs innan geometrin fanns.

Varje del binds till data eller till ett stiliserat faktum. Det som inte går
att binda är markerat som öppet.

---

## 1. Varför individen är ett annat slags objekt än yrket

Papper 1 är en geometri av **uppgifter och yrken**. Ett yrke är en punkt med
radie, ett krav och ett pris: (ξ, χ, r_o, zon, lön). Det räcker, eftersom ett
yrke är en struktur och inte en aktör.

En individ är en aktör med historik. Hon har utfört en följd av uppgiftsbuntar,
kan därför en bredd av saker, har en formell kvalifikation och ett lönekrav.
Alla fyra avgör vilka jobb hon kan få och vilka hon väljer. Ingen av dem följer
av att ge henne en punkt i planet och flytta den med godtyckliga delta, vilket
var den ursprungliga konstruktionen.

Två missförstånd i den ursprungliga modellen, båda rättade här:

*χ är inte nivå.* Papper 1 definierar χ som hur skarpt uppgiftsinnehållet är
orienterat mot sin riktning. Diskare har χ = 0,54 och ligger längre ut än
servitörer. Advokater har 0,39 och ligger närmare origo än kemiingenjörer.
Inom sektorer förutsäger χ högre utbildningskrav i norr (+3,55) och nordost
(+8,45) men *lägre* i väster (−2,48) och sydväst (−4,93). Att höja χ är att
skärpa sin profil, inte att kvalificera sig.

*Cirkeln avgränsar inte vad man kan.* Advokaten kan diska. Passformen i planet
beskriver var individen är produktiv fullt ut, inte var hon får anställas.
Vad hon får anställas till avgörs av kravet, som är en nivå och inte en
geometrisk storhet.

---

## 2. Individens fem egenskaper

| Egenskap | Symbol | Bestäms av | Bunden till |
|---|---|---|---|
| Riktning | ξ̄ | cirkulärt medelvärde av historikens ξ, varaktighetsviktat | papper 1:s ξ |
| Specificitet | χ̄ | vanligt medelvärde av historikens χ, varaktighetsviktat | papper 1:s χ |
| Riktningskonsekvens | R | resultantlängd \|Σw·e^{iξ}\| / Σw ∈ [0,1] | följer av konstruktionen |
| Nivå | ℓ | SUN-kod ur SCB (tabellen `education_level_municipality`) | data |
| Lönekrav | w_res | förhandlad lön vid anställning; avtar i arbetslöshet | Littles lag, arbetslöshetstider |

Därtill bostad (x, y) i meter, oförändrad.

**Bredden härleds**, den är ingen egen tillväxtregel: för innehåll vid radien
χ̄ med vinkelkoncentration R är RMS-avståndet från medelriktningens punkt

    r_i = χ̄ · √(2(1 − R))

En rak karriär ger R ≈ 1 och r_i ≈ 0 utöver yrkets egen radie. En spretig
karriär ger lågt R och stor bredd.

**Positionen är en konsekvens, inte ett val.** Individen väljer jobb och
utbildning; ξ̄, χ̄ och R följer av vad hon gjort. Fem löpande summor per
individ räcker för inkrementell uppdatering: Σw, Σw·cos ξ, Σw·sin ξ, Σw·χ,
Σw·χ².

### Varför polärt och inte kartesiskt

Papper 1 summerar ett yrke kartesiskt: centroiden av dess uppgifter. Det
blandar avsiktligt ihop specificitet och riktningsjämnhet i ett tal, χ_o.
Tillämpat på en karriär ger samma konstruktion en drift mot origo: den som
gjort två saker i olika riktning hamnar mellan dem och innanför, och efter
ett långt yrkesliv nära centrum oavsett vad hon kunnat. Informationen om hur
specifikt hennes arbete varit går förlorad.

Den polära summeringen håller isär de två. χ̄ är begränsad av de χ hon
faktiskt haft, och R bär riktningsjämnheten separat. Individen behåller sin
karaktär: en specialist med spretig karriär skiljer sig från en generalist
med rak.

Fallgrop: har någon arbetat i motsatta riktningar är ξ̄ illa definierad. R
blir då nära noll, r_i stor, och matchningen vidgas — vilket är rätt beteende
för en person utan tydlig hemvist. Fallet är ovanligt; 73 procent av
rörligheten sker inom ett delsystem.

### Vad som händer vid inträde

En individ utför en delmängd av sitt yrkes uppgifter. Hennes personliga
position vid inträdet avviker därför från yrkets centroid med ungefär
r_o/√k, där k är antalet uppgifter hon faktiskt utför. Med r_o ≈ 0,27 och ett
tjugotal uppgifter ger det ≈ 0,06. Det ersätter den hårdkodade
jitterparametern 0,05 med en härledning som skalar med yrket.

### Historiken uppdateras av exponering

En enda primitiv ersätter dagens delta-regler: *exponera individen för
position p med vikt w*. Varje anställning exponerar med vikt lika med
varaktigheten. Varje avslutad utbildning exponerar med vikt lika med
studietiden. `switch_cost_kappa` utgår: omorientering sänker R av sig själv,
vilket är den urholkning parametern var avsedd att modellera.

Advokaten som diskar ett år får diskningen inräknad. Hennes ξ̄ flyttas mot
sydväst och R sjunker. Det är rätt: erfarenhet utanför cirkeln *är* en
förändring av vem hon är på arbetsmarknaden, och det är så nedåtgående
rörlighet blir bestående.

---

## 3. Jobbet

Position (ξ, χ), radie r_o, krav (Job Zone 1–5 ur O\*NET), fältlön Π ur
prisfältet, plats. Kravet är tillagt; det övriga är oförändrat.

Jobb ligger exakt på sitt yrkes centroid. Det är avsiktligt: den empiriska
referensen för mobilitet mäter avstånd centroid till centroid mellan
SOC-koder. Sprids jobben förlorar modellens u_R sin jämförbarhet.

---

## 4. Matchning: två frågor med olika ägare

För varje par (individ, jobb) ställs två frågor.

### Kan hon få det — arbetsgivarens fråga

    P(anställning) = p_geom(d, σ)^α(zon) · p_nivå(ℓ − zon, tryck)

**Passformen** p_geom = exp(−d²/2σ²) med σ² = γ²(r_o² + r_i²) och d avståndet
mellan hennes position och jobbets. Kalibrerad: γ = 0,875 ger Rayleigh-median
1,03 task-radier, papper 2:s observerade värde.

**Exponenten α(zon)** stiger från nära noll på zon 1 till ett på zon 5. Ju mer
ett jobb kräver, desto mer spelar det roll att man kommer från rätt håll.
Utan den låtsas den symmetriska kärnan att diskning ligger utom räckhåll för
alla som arbetat med något annat. Form och skala är öppna; kalibreras så att
lokaliteten för zon 1-jobb kommer från efterfrågesidan (vem vill) och för
zon 5 från utbudssidan (vem kan).

**Nivåspärren** p_nivå är mjuk: en straffaktor per nivå under kravet, aldrig
ett stopp. Lutningen **mjuknar med lågt lokalt marknadstryck** — vakanser per
sökande inom räckhåll. Arbetsgivare sänker krav när sökande är få och höjer
dem när sökande är många (Modestino, Shoag & Ballance). Det ger en motkraft i
tunna marknader som modellen annars saknar: brist på kvalificerade gör att
kraven mjuknar lokalt. Hypotesen är prövbar mot platsannonsdata.

Nyckeln SUN ↔ Job Zone är öppen och måste konstrueras.

### Vill hon ha det — hennes fråga

Logit över förhandlat överskott:

    S = w_förhandlad − c·km − reservation

med skalan `choice_scale`: nära likvärdiga alternativ får nära lika
sannolikhet; ett närmare jobb väljs framför ett längre bort när lönen är
ungefär densamma. För den arbetslösa är reservationen w_res. För den
anställda är den **nuvarande överskottet plus en bytesfriktion** — tröskeln
det nya måste överstiga för att vara värt besväret. Friktionens storlek är
öppen; utan den byter folk vid minsta förbättring.

---

## 5. Lönen: fältet som grund, individen förhandlar

Fältet Π ger yrkets prisnivå. Den individuella lönen förhandlas fram enligt
Nash, standard i sökteorin sedan Mortensen och Pissarides:

    w = w_res + β · (p·Π − w_res − k_vakans)

**Arbetarens värde i jobbet** är p·Π: fältet gånger passform. Den erfarna
diskaren och advokaten som diskar har olika p och därmed olika värde.
**Hennes alternativ** är w_res. **Arbetsgivarens alternativ** är fortsatt
vakans, vars kostnad k_vakans beror på lokalt tryck inom räckhåll: många
sökande ger arbetsgivaren styrka, få ger arbetaren styrka. β är
förhandlingsstyrkan, i litteraturen ofta kring 0,5.

Tre saker följer som modellen inte kunde uttrycka förut. Löner varierar inom
yrke. Tunnhet får en löneeffekt: få sökande per vakans stärker arbetaren,
vilket delvis kompenserar färre jobb, och det är mätbart i
lönestrukturstatistiken per kommun. Och nedåtgående rörlighet får ett pris:
advokaten som diskar får mindre än fältlönen, eftersom hennes p är låg, men
tar det om hennes w_res fallit nog.

Utbildning ger **ingen egen löneeffekt**. Nivån öppnar jobb; att de betalar
mer är fältets sak. Det tar bort en parameter och gör grindvaktsfrågan i
utbildningsdokumentet skarpare.

Öppet: om k_vakans ska bero på tunnhet i uppgiftsrummet, inte bara på antal
sökande. En arbetsgivare i en tunn marknad har svårt att tillsätta även om
arbetslösheten är hög, eftersom de arbetslösa finns i fel riktning. Det vore
två slags tryck — hur många som söker, och hur många av dem som passar — och
det andra ger tunnheten en direkt löneeffekt.

Inga motbud från befintlig arbetsgivare i denna version.

---

## 6. Sökning: två populationer

**Arbetslösa** söker var fjärde vecka i snitt. w_res avtar med fem procent per
misslyckad sökning ned till ett golv. Detta finns.

**Anställda söker också**, och det är så de flesta yrkesbyten sker. Det
saknas i dag, och frånvaron förklarar en kalibreringsavvikelse: papper 2:s
1,03 task-radier är dominerat av anställda som byter till liknande jobb,
medan modellens 1,36 kommer enbart från arbetslösa som söker bredare. Fel
population.

Sökintensiteten är **puckelformad per jobb**: låg de första månaderna,
stigande till en topp, sedan avtagande med lång tjänstgöring. Farber fann att
separationsrisken stiger de första månaderna och sedan faller; Jovanovic
förklarar det med att man lär sig hur bra matchningen är, och de som stannar
är de för vilka den var bra. Två parametrar — toppens läge och avtagandets
takt — med handtag i tjänstgöringsstatistik. Puckeln räknas per jobb, inte per
yrke: det är anställningens längd som bygger bindning.

Den anställda sökaren använder samma maskineri som den arbetslösa —
relevansmängd, logit över överskott, förhandlad lön — med två skillnader:
reservationen är nuvarande överskott, och bytesfriktionen tillkommer. Byter
hon frigörs den gamla positionen efter **uppsägningstid**, inte vid
matchningen.

`quit_job`, `internal_job_change` och `start_internal_training` ersätts av
denna enda mekanism. Ofrivilliga separationer kvarstår som jobbförstörelse.
Inflödet till arbetslöshet blir därmed förstörelse och ofrivilliga
uppsägningar — det inflöde Littles lag ska räknas på, och det är lägre än
vad modellen hittills antagit.

Konsekvens: byten från anställning är selektiva och därför **riktade uppför
fältet**. Det är den mekanism som ger papper 2:s nettoflöde fysiskt →
kognitivt — inte att arbetslösa dras norrut, utan att anställda byter dit när
tillfälle ges. Med förhandlad lön och nuvarande lön som golv ger den också
lönetillväxt över karriären (Burdett–Mortensen).

---

## 7. Utbildning

Två former, specificerade i `utbildningsmodell.md`.

**Formell utbildning** höjer nivån ℓ stegvis, med förkunskapskrav, och öppnar
jobb. Den rör inte geometrin.

**Omskolning** flyttar positionen mot där välbetalda nåbara jobb finns, med
varaktighet efter sträckan. Målet är en överskottsviktad tyngdpunkt av
tillgängliga vakanser; finns inget som lönar sig sker ingen omskolning.

Båda uppdaterar historiken vid *slutet*, genom exponering. Båda utesluter
anställning under tiden: den som börjar studera släpper sitt utlovade jobb.

---

## 8. Tidsstruktur

Rekryteringstid mellan matchning och tillträde (exponentiell, 30 dagar),
under vilken positionen är utlovad men räknas som öppen vakans. Uppsägningstid
vid byte från anställning. Utbildningstid efter sträcka.

Bokföringen måste sluta exakt: antalet sysselsatta lika med antalet tillsatta
aktiva positioner efter varje händelse. `scripts/check_invariants.py`
kontrollerar det, och varje ny händelsetyp ska ha ett test som kör den mot
invarianten. Fyra buggar i rad kom av att en ny mekanism mötte de befintliga
händelserna på sätt som inte prövats.

---

## 9. Validering

Representationen är en teori, inte en design, om den kan vara fel. Den är
validerad om simulerade individer reproducerar **papper 2:s fyra stiliserade
fakta utan att de kodats in**:

| Faktum | Värde | Väntad mekanism |
|---|---|---|
| Rörligheten är lokal | median 1,03 task-radier, >80 % inom två | passformens kärna, kalibrerad |
| Två delsystem | 73 % inom, 27 % över | geometri och prisfält |
| Centripetala fält | flöden böjer mot delsystemens kärnor | vakansernas täthet: folk rör sig dit jobben är många |
| Asymmetri | 35 % fysiskt → kognitivt, 20 % omvänt | anställda som byter uppför fältet; m₅ = 0,89 |

Därtill: bokföringen sluten, och vakansstocken enligt Littles lag mot svensk
vakansgrad.

Det sista faktumet är det skarpaste testet. Asymmetrin ska följa av att
anställda söker selektivt, och den finns inte i modellen förrän den
mekanismen finns.

---

## 10. Byggordning

Varje steg med tester och invariantkontroll från början.

1. **Historiksummeringen.** Fem summor per individ, exponeringsprimitiven,
   härledd bredd, härledd inträdesposition. `switch_cost_kappa` utgår. Allt
   annat vilar på detta.
2. **Sökning från anställning.** Puckelformad intensitet per jobb,
   bytesfriktion, uppsägningstid. Ersätter `quit_job` och de interna
   händelserna. Rättar kalibreringens population.
3. **Förhandlad lön.** Nash med lokalt tryck. Behöver steg 2 för anställdas
   reservation.
4. **Nivån.** Job Zone-inläsning, SUN-nyckel, mjuk spärr med tryckberoende,
   exponent efter krav. Förutsätter att grindvaktsfrågan är mätt.
5. **Utbildningen** på de nya primitiverna.

Efter steg 2 ska valideringens första och fjärde faktum prövas. Efter steg 5
alla fyra.

---

## 11. Öppna frågor

- Bytesfriktionens storlek.
- Om k_vakans ska bero på tunnhet i uppgiftsrummet.
- Nyckeln SUN ↔ Job Zone.
- Form och skala för α(zon).
- Glömska: om gammal exponering ska nedviktas. Utan drift mot origo finns
  inget som tvingar fram det; parkerad.
- Om R ska påverka anställning utöver r_i — om en spretig karriär är ett
  signalproblem i sig. Parkerad.
- Om bredden inom ett yrke ska växa med tid i yrket. Parkerad.
