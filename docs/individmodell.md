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

## 2. Individen som överlagrade cirklar

Individen är inte en punkt med radie. Hon är en **samling cirklar**, en per
erfarenhet, och summan av dem är ett fält över uppgiftsskivan. Cirkeln är
samma primitiv som papper 1 bygger yrken av — centroid plus radie — så
individen är gjord av samma delar som rummet hon rör sig i. Papper 2:s mått
på överlapp mellan yrken, R_a + R_b − d_ab, är cirkelöverlappet; individens
konkurrenskraft i ett jobb är dess mjuka form.

### Cirkeln

Varje cirkel k har centrum (x_k, y_k), radie ρ_k, massa m_k och en nyckel:
det yrke eller den utbildning den kommer från. En individ har högst ett tiotal
cirklar; tolv är taket, och den med minst massa faller bort om det nås.

| Ursprung | Centrum | Radie | Massa |
|---|---|---|---|
| Grundskola | origo | 1 (hela skivan) | låg, lika för alla |
| Gymnasium | programmets riktning | bred | måttlig |
| Högskola | programmets riktning | smalare | högre |
| Arbete i yrke o | yrkets centroid + personlig avvikelse | r_o | växer med tid i yrket |

Grundskolan är ett golv: ingen riktning, låg massa överallt. Den som föds kan
bli vad som helst och är ingenting än. Programriktningar för gymnasium och
högskola kräver att utbildningar positioneras i skivan, vilket är samma
projektionsproblem som för yrken; tills det är gjort används yrkets riktning
som proxy.

Den personliga avvikelsen vid inträde i ett yrke är r_o/√k, där k är antalet
uppgifter i yrket: individen utför en delmängd av dem, och hennes centroid
avviker därefter. Det ersätter den hårdkodade jitterparametern med en
härledning som skalar med yrket.

### Dynamiken

Tre processer, med tre parametrar som var och en har en tidsskala.

**Exponering.** Arbete i yrke o lägger massa på o:s cirkel med takten a per
år; finns ingen sådan cirkel skapas den. Avslutad utbildning lägger till en
cirkel med programmets position och massa lika med studietiden gånger a.

**Läckage.** All massa avtar med takten λ: dm/dt = −λm. Halveringstiden är
decennier. Läckaget gör två saker med en parameter: det gallrar det gamla, och
det **mättar** massan under aktivitet, eftersom dm/dt = a − λm går mot a/λ.
Utan läckage skulle en stor massa göra diffusionen verkningslös — en snickare
med fyrtio år bakom sig skulle vara fullt konkurrenskraftig efter trettio års
uppehåll, eftersom massan äter upp utspridningen.

**Diffusion.** En cirkel som inte används sprids: dρ²/dt = 2D. Toppen faller
som 1/(ρ₀² + 2Dt) — brant först, sedan flackt, aldrig noll. Det är glömska
som du beskrev den: spetsen förloras där man inte verkar, men allt finns kvar,
alltmer diffust. Med D ≈ 0,015 per år är en cirkel som börjat vid r_o ≈ 0,27
halvt så skarp efter fem år och utspridd över hela skivan efter trettio.

**Skärpning.** En cirkel som används dras tillbaka mot sin egen radie med
tidskonstanten τ_s, i månader: dρ²/dt = (r_o² − ρ²)/τ_s. Den som återvänder
till sitt gamla yrke har massan kvar men behöver några månader för att återfå
skärpan.

Samma D och λ för alla cirklar, oavsett ursprung.

| Parameter | Betydelse | Skala |
|---|---|---|
| a | exponeringstakt | 1 per år (enhet) |
| λ | läckage; ger mättnad a/λ | halveringstid ~15 år |
| D | diffusion | spets halverad efter ~5 år |
| τ_s | skärpning vid återupptagen aktivitet | ~6 månader |
| m_ref | massa som ger nästan full konkurrenskraft | ~2 år |

### Konkurrenskraften

Individens konkurrenskraft i jobb j är summan av cirklarnas bidrag:

    q_ij = min(1, Σ_k  (1 − e^{−m_k/m_ref}) · [2r_o² / (ρ_k² + r_o²)] · exp(−d_kj² / 2γ²(ρ_k² + r_o²)))

Tre faktorer per cirkel. **Massan**, mättande: skillnaden mellan noll och två
års erfarenhet är stor, mellan tio och tjugo liten. **Skärpan**: ett när
cirkeln är lika skarp som jobbets egen radie, mot noll när den diffunderat.
**Avståndet**: samma kärna som förut, med cirkelns radie i stället för r_i.

Den mogna arbetaren vid sitt eget jobb: massa över referens, ρ = r_o, d = 0,
q = 1. **Kalibreringen mot 1,03 task-radier står**, eftersom den handlar om
erfarna som byter. Samma person efter tjugo år borta: skärpan ≈ 0,15 — hon
känns igen men är inte den hon var. Nybörjaren med grundskola: q ≈ 0,05
överallt. Advokaten vid diskbänken: lite från juridikcirkeln, lite från
golvet, och en diskcirkel som växer från första månaden.

### Vad detta ersätter

Positionen som tillståndsvariabel, bredden r_i som tillväxtregel,
`initial_r`, `switch_cost_kappa` och `breadth_from_move`. Omorientering
urholkar av sig själv: den gamla cirkeln diffunderar medan den nya byggs.

Sammanfattande mått — centroid, χ̄, ξ̄, riktningskonsekvens, spridning —
härleds ur cirklarna för loggning och validering. De är inte tillstånd.

### Kopplingen till teknikfälten

Technology fields beskriver en teknik som ett fält över samma skiva, φ_K(r).
Individen och tekniken har därmed samma form. En chock är att teknikens massa
stiger i ett område; de arbetare vars cirklar ligger där förlorar sitt värde,
de vars cirklar ligger bredvid eller är spridda klarar sig. **Utsattheten för
en chock är ett överlapp mellan två fält**, beräkningsbart per individ i
sluten form för gaussiska kärnor. Det är den koppling mellan papper 3 och
simuleringen som saknats.

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

    P(anställning) = q_ij^α(zon) · p_nivå(ℓ − zon, tryck)

**Passformen** är konkurrenskraften q_ij ur avsnitt 2: summan av hennes
cirklars bidrag vid jobbet. För en mogen arbetare med en cirkel reduceras
den till exp(−d²/2γ²(r_o² + ρ²)), och γ = 0,875 ger Rayleigh-median 1,03
task-radier, papper 2:s observerade värde.

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

    w = w_res + β · (q·Π − w_res − k_vakans)

**Arbetarens värde i jobbet** är q·Π: fältet gånger konkurrenskraft. Den
växer med tenure eftersom q gör det, vilket ger löneprofiler över karriären
ur modellen. Den erfarna
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

1. **Kompetenscirklarna.** Cirkeltabellen, exponering, läckage, diffusion,
   skärpning, konkurrenskraften q. Härledd inträdesposition. `initial_r`,
   `switch_cost_kappa` och `breadth_from_move` utgår. Allt annat vilar på
   detta. Kontroll: t = 0-matchningen ger samma antal ±2 % som före, eftersom
   betydelsen ändrats men inte beteendet.
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
- Programriktningar för gymnasium och högskola: kräver att utbildningar
  positioneras i skivan. Yrkets riktning är proxy tills dess.
- Ålder finns inte på individerna; tenure dras ur en fördelning. Kohortinträde
  och åldersstruktur är ett senare demografiskt steg.
- Om en spretig karriär är ett signalproblem i sig, utöver vad cirklarnas
  överlapp ger. Parkerad.
