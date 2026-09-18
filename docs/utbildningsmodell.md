# Utbildning i WORM — designutkast

Detta är ett utkast, inte en specifikation. Det beskriver hur utbildning bygger
individens kompetens, hur utbildningar representeras och vilka data som bär
representationen. Det bygger på individmodellen i `individmodell.md`, avsnitt
2, som ska läsas först: individen är en samling cirklar, en per händelse i
karriären, och konkurrenskraften är unionen av deras täckning.

Vad som är avgjort och vad som är öppet står utskrivet. Den förenklade
omskolningsmekanismen, som är införd, beskrivs sist, tillsammans med
byggordningen för resten.

Tre påståenden i tidigare versioner är överspelade och ska inte byggas på: att
en inriktning placeras i medelpunkten av de yrken dess utexaminerade arbetar i,
att SCB korsar yrke med tresiffrig inriktning, och att massan är studietiden
rakt av. Varför står under "Utbildningen som cirkel".

---

## Vad utbildning gör

Två skilda saker, som den ursprungliga modellen blandade ihop.

**Exponering för uppgiftsinnehåll.** Att gå en utbildning är att tillägna sig
en uppgiftsbunt utan att ha ett jobb. Effekten är av samma slag som
arbetserfarenhet: en cirkel läggs till individens samling, med en position ur
inriktningen och en radie och massa ur nivån. Detta är **omskolning** när det
sker mitt i arbetslivet. Se `individmodell.md`, avsnitt 2.

**Höjd kvalifikationsnivå.** Att ta en examen höjer ℓ och öppnar jobb som
kräver den. Detta är **formell utbildning**.

En yrkesutbildning gör båda. En högskoleförberedande utbildning gör mest det
andra. En intern kurs gör mest det första. Distinktionen är mätbar i data.

**Varje avslutad utbildning är en händelse och ger en egen cirkel**, även den
allmänna, i enlighet med individmodellens regel om en cirkel per händelse.

Utbildning ger **ingen egen löneeffekt**. Nivån öppnar jobb; att de betalar
mer är prisfältets sak. Omskolning flyttar mot bättre betalda jobb; att de
betalar mer är också fältets sak. Detta tar bort en parameter och gör
grindvaktsfrågan nedan skarpare.

---

## Utbildningen som cirkel

Cirkelns tre storheter har operativa betydelser i konkurrenskraften
(`individmodell.md`, avsnitt 2), och det är därifrån de ska definieras. Varje
cirkel bidrar vid ett jobb med

    c_k = (1 − e^{−m_k/m_ref}) · [2r_o²/(ρ_k² + r_o²)] · exp(−d_kj²/2γ²(ρ_k² + r_o²))

och bidragen kombineras som en union, inte en summa. **Positionen** är var
toppen ligger; avståndet d mäts därifrån. **Radien** ρ är en avvägning och inte
ett kvalitetsmått: skärpan är ett när cirkeln är lika bred som jobbets egen
uppgiftsradie r_o och faller när den är bredare, medan avståndsfaktorn räcker
längre ju bredare cirkeln är. Smal cirkel ger hög topp och kort räckvidd, bred
ger låg topp och lång. **Massan** avgör hur mycket cirkeln räknas alls,
mättande vid m_ref ≈ 2 år.

### SUN har två dimensioner

SCB:s utbildningsnomenklatur SUN 2020 klassar varje utbildning på två
dimensioner, och modellen använder dem rakt av, utan översättningsled.

**Nivån** har sju steg i den publicerade statistiken:

| Nivå | |
|---|---|
| 1–2 | förgymnasial, kortare än 9 år respektive 9 (10) år |
| 3–4 | gymnasial, högst 2 år respektive 3 år |
| 5–6 | eftergymnasial, kortare än 3 år respektive 3 år eller mer |
| 7 | forskarutbildning |

Det är samma skala som individens `education_level`. Den fullständiga
nivåkoden har tre positioner — grov nivå, teoretisk längd och typ, där typen
skiljer yrkesinriktad från generell utbildning — men de publicerade tabellerna
bär bara de sju stegen.

**Inriktningen** har 9 huvudinriktningar (plus 0 *allmän utbildning* och 9
*okänd*), 25 på tvåsiffernivå och 117 ämnesinriktningar. **Korsad med yrke
publiceras bara den ensiffriga nivån**: TAB4359 och TAB4446 har tio värden. Den
finare indelningen finns i andra tabeller men aldrig korsad med yrke.

SCB publicerar dessutom *utbildningsgrupper* som kombinerar nivå och
inriktning i en kod, till exempel `53B` byggutbildning, gymnasial, och `35E`
ekonomutbildning, eftergymnasial minst 3 år. De finns i matchningstabellerna
TAB6356 och TAB6929, men dessa har ingen yrkesdimension.

### Trappan

Nivå och inriktning hänger ihop, och sambandet är modellens trappa:
inriktningen uppstår med nivån. Befolkningen 25–34 år 2024 (TAB655), i procent
av varje nivå:

| Nivå | allmän (0) | med inriktning (1–8) |
|---|---|---|
| 1–2 förgymnasial | 100 | 0 |
| 3–4 gymnasial | 20 | 77–78 |
| 5–6 eftergymnasial | 0–1 | 97–99 |

Resten är okänd inriktning.

**Grundskolan** saknar inriktning helt. **Gymnasiet** delar sig. Yrkesprogrammen
har inriktning, de högskoleförberedande har det inte: på nivå 4 har bara 400
personer inriktningen naturvetenskap, så naturvetenskapsprogrammet är klassat
som allmän utbildning. För SUN — och för geometrin — är det en längre
grundskola. **Eftergymnasial utbildning** har nästan alltid inriktning.

Att en femtedel av de anställda saknar inriktning — 16 procent allmän och 3,5
procent okänd i TAB4359 — är alltså ingen brist i datan. Det är de som stannat
på de breda trappstegen.

### Djup är inte χ

Bilden av utbildning som "inriktning och djup" översätts till cirkelns
storheter:

- **Inriktningen** är **positionen**: var cirkeln ligger.
- **Djupet** är **radien** — hur smal cirkeln är — och **massan** — hur mycket
  den räknas.

Djupet ska inte läggas i χ. Diskaren ligger på 0,54, advokaten på 0,39 (se
"Vad χ är och inte är" nedan). En djup utbildning flyttar ingen utåt i skivan;
den ger en smalare och tyngre cirkel på den plats som inriktningen pekar ut.

### Stapeln

Varje avslutat steg ger en egen cirkel, och cirklarna läggs på varandra:

| Steg | Position | Radie | Massa |
|---|---|---|---|
| Grundskola | origo | 1 | låg, lika för alla |
| Allmän utbildning, oavsett nivå | origo | 1 | studietid × intensitet |
| Gymnasial med inriktning | dragen ur P(yrke \| inriktning, gymnasial) | bred | studietid × intensitet |
| Eftergymnasial | dragen ur P(yrke \| inriktning, eftergymnasial) | nära r_o | studietid × intensitet |
| Forskarutbildning | dragen ur P(yrke \| inriktning, forskarnivå) | nära r_o | studietid × intensitet |

Den allmänna utbildningen får en egen cirkel ovanpå grundskolans, lika bred och
på samma plats. Unionen staplar sådana cirklar nästan som en summa, eftersom en
cirkel med radie 1 täcker lite: grundskola och ett högskoleförberedande
gymnasium ger ungefär dubbelt så högt golv som grundskolan ensam, 0,105 mot
0,054 vid ett typiskt jobb. Golvet stiger, men ingen topp uppstår — det är vad
"allmän" betyder geometriskt (`individmodell.md`, avsnitt 2).

### Positionen: dra, inte medelvärde

Tidigare versioner placerade inriktningen i den viktade medelpunkten av de
yrken dess utexaminerade arbetar i, och tog radien ur spridningen kring den.
Uppmätt för 25–29-åringarna i TAB4359, med yrkena placerade genom
`ssyk3_onet_crosswalk`:

| | |
|---|---|
| inriktningarnas avstånd från origo | 0,10–0,38 |
| medianavstånd mellan två inriktningar | 0,197 |
| inriktningens radie ρ | median 0,385 |
| ett yrkes radie r_o | 0,281 |

Två inriktningar ligger närmare varandra än ett yrke är brett, och varje
inriktning är bredare än ett yrke. En inriktningscirkel ger skärpan 0,70 vid
sitt eget centrum, och vid medianavståndet följer 89 procent av den med till en
annan inriktning. Vad man har läst avgör ungefär en tiondel av
konkurrenskraften.

Felet ligger inte i den ensiffriga indelningen. En finare indelning hade
troligen krympt det men inte löst det, eftersom felet sitter i operationen.
**En inriktning är inte en plats utan en fördelning över yrken**, och
fördelningen har flera toppar. Hälso- och sjukvårdsutbildade 25–29 år blir
undersköterskor (15 procent), sjuksköterskor (14) och personliga assistenter
(10). Medelpunkten hamnar mellan yrkena, och en radie som täcker alla tre har
ingen skärpa kvar. Pedagogiken bekräftar detta från andra hållet: en topp, 55
procent lärare, och den medelpunkt som ligger längst ut av alla.

Individen **drar** därför ett yrke ur P(yrke | inriktning, nivå, ålder, kön)
och får sin utbildningscirkel där. Spridningen ligger i populationen, inte i
individens cirkel. Tre saker följer:

1. **Varje individ är skarp någonstans**, och populationen återger
   yrkesutfallet per konstruktion. Frågan om utbildning kan skärpa, och inte
   bara flytta, får svaret ja för varje individ.
2. **Den grova inriktningen räcker.** Grovheten avgör bara vilken fördelning
   man drar ur; ingen position går förlorad. Den ensiffriga fördelningen täcker
   fortfarande 146 yrken med observerade vikter.
3. **Utbildning och arbete ligger i samma rum.** Den som drar sjuksköterska och
   anställs som sjuksköterska får en arbetscirkel ovanpå utbildningens. Den som
   anställs som undersköterska får den på ett annat ställe, och
   utbildningscirkeln diffunderar. Det är mismatch, uttryckt i befintlig
   mekanik.

Nivån måste med i dragningen. Utan den blandas undersköterskor och
sjuksköterskor i samma inriktning 7; med den separeras de, och de ligger
dessutom på olika platser i skivan.

### Radien: individens bredd, inte populationens spridning

Yrkesutfallet mäter var *olika personer* hamnar. Radien ska beskriva hur många
jobb *en person* kan göra. Dragningen tar hand om det första. Det andra är en
parameter per nivå — bred för gymnasial, nära yrkets egen r_o för
eftergymnasial — som kalibreras mot rörligheten: hur långt personer på varje
nivå byter yrke utan att förlora konkurrenskraft. Det blir tre–fyra tal, inte
117.

Att ta radien ur dragningsfördelningens spridning vore att göra om
medelpunktsfelet: populationens spridning lagd i individens cirkel.

`EDU_RADIUS2` i `core/occupations/competence.py` är redan en tabell per nivå,
men gissad.

### Massan är inte studietiden

Studietid rakt av ger fel svar. Fem års civilingenjörsutbildning med m = 5 ger
massfaktorn 0,92 — en nyexaminerad vore nästan lika konkurrenskraftig som
någon med fem års yrkeserfarenhet. Massan mäter exponering för uppgifterna,
och studier ger mindre av det per år än arbete.

Alltså m = studietid × intensitet, där intensiteten är under ett och skiljer
sig mellan yrkesinriktad och generell utbildning. Som storleksordning ger
intensitet 0,5 för yrkesinriktad ett treårigt vård- och omsorgsprogram 0,53 och
en femårig civilingenjör 0,71; intensitet 0,3 för generell ger ett treårigt
naturvetenskapligt program 0,36.

**Talen 0,5 och 0,3 är inte avgjorda.** De ska kalibreras, inte gissas.
Nivåkodens tredje position, som bär skillnaden mellan yrkesinriktad och
generell, finns inte i de publicerade tabellerna; den allmänna inriktningen
fångar en del av den.

*Läget i koden.* `EDU_MASS` ger nivå 6 massan 3,5 och därmed massfaktorn 0,83 —
nästan en erfaren arbetares. Med intensiteten 0,3 och tre år blir den 0,36.

### Data för dragningen

P(yrke | inriktning, nivå, ålder, kön) publiceras inte. Tre tabeller ger var
sin tvåvägsmarginal av den, inom ålder och kön:

| Tabell | Korsning | Population |
|---|---|---|
| TAB4359 | yrke × inriktning | anställda, 2020–2024 |
| TAB4360 | yrke × nivå | anställda, 2020–2024 |
| TAB655 | nivå × inriktning | befolkningen 16–74 år, 2019–2025, tioårsklasser |

Raking — iterativ proportionell anpassning — ger den simultana fördelning som
uppfyller alla tre marginalerna. Det enda den inte kan veta är
trevägssamspelet utöver marginalerna. Två kontroller finns: TAB4359 och
TAB4360 räknar samma anställda och måste ha identiska yrkestotaler, och
matchningstabellen TAB6356 ger andelen matchade per utbildningsgrupp, vilket är
ett oberoende facit. TAB655 avgränsar annorlunda än de två andra — hela
befolkningen och tioårsklasser — och det ska synas i läsaren, inte jämnas ut.

**TAB4359 är hämtad** (0172), år 2024: 149 yrken × 10 inriktningar × 10
åldersklasser × 2 kön, alltså 29 800 celler och 5 006 642 anställda. Den har
inga totalrader. `0002` (yrke okänt, 0,4 procent) och inriktning 9 (okänd, 3,5
procent) är restposter, så läsaren summerar. Det finns inget röjandeskydd:
cellerna är exakta heltal ned till 1.

Dragningen tas ur **25–29-åringarna**. De är nära examen och har inte hunnit
driva bort från sin utbildning, vilket är precis vad en inträdares cirkel ska
spegla. Alla åldrar är ändå hämtade, eftersom skillnaden mellan
åldersklasserna är själva driften bort från utbildningen. Den syns:
pedagogikens effektiva antal yrken går från 3,1 vid 25–29 till 5,7 vid 65–69,
samhällsvetenskapens från 22 till 31. Att 16–24 är skarpare än 25–29 är
sammansättning, inte drift: de högutbildade har inte kommit ut än.

### Bara den högsta utbildningen syns

SCB registrerar individens *högsta* utbildning. En universitetsutbildads
gymnasieprogram finns inte i någon av tabellerna.

För **inträdare** som går igenom trappan i modellen uppstår inget problem,
eftersom stapeln byggs steg för steg. För **startpopulationen** måste de lägre
stegen imputeras. Det som lindrar är att de flesta som läser vidare kommer från
högskoleförberedande program, som är allmänna: det osynliga steget är oftast
just det som bara lägger en cirkel i origo. Det sista bygger på kännedom om
svensk utbildning, inte på tabellerna.

### Startpopulationen och inträdaren

**Inträdaren** har ännu inget yrke. Hon drar inriktning och nivå, drar
positionerna för sina utbildningscirklar och söker jobb med den stapeln.
Inträdarens cirkel *är* utbildningens, och det är där dragningen gör skillnad.
Därför byggs inträdet på arbetsmarknaden efter utbildningscirklarna.

**Startpopulationen** har redan ett yrke och en nivå, men ingen inriktning.
Inriktningen dras ur P(inriktning | yrke, nivå, ålder, kön), alltså samma
fördelning läst åt andra hållet. Var hennes utbildningscirkel ska ligga är
svårare. Ett nytt drag ur P(yrke | inriktning, nivå) bortser från att hennes
nuvarande yrke och hennes utbildning hänger ihop, och P(utbildningens yrke |
nuvarande yrke) publiceras inte. Att lägga cirkeln vid hennes nuvarande yrke,
som koden gör i dag, är cirkulärt men går att försvara som ett
stationaritetsantagande — utbildningen är den som ledde henne dit. Det
underskattar mismatchen i startpopulationen.

### Två situationer: priming och inträde (avgjort 2026-09-18)

Modellen har två slags individer, och de byggs åt motsatta håll ur samma
tabeller.

**Priming.** Startpopulationen ska se ut som en befintlig arbetskraft i
sysselsättning under startåret, utan en inkörningsperiod där alla börjar
från noll. Kriteriet är att startårets tvärsnitt är körningens eget
jämviktsläge. Primingen ska bli bra, men den kan inte vara perfekt, och
någon fullständig historik byggs inte för varje individ.

- **Jobben först, sedan historiken.** De sysselsatta placeras i jobb, och
  arbetscirkeln läggs på *jobbets* yrke med massa ur tjänstetiden. I dag
  dras ett startyrke oberoende av jobben, och tjänstetiden byggs på det.
  Uppstartsmatchningen placerar sedan 94 procent i ett annat yrke än
  startyrket (12 165 av 12 962 i baslinjens frö 1, median 0,74 r_o bort).
  Erfarenheten ligger alltså där hon inte arbetar och suddas ut, medan en tom
  cirkel byggs där hon arbetar. Det är en inkörningsperiod. Den syns i
  baslinjen, men går inte att skilja från den krympande arbetskraften: q vid
  anställning är 0,84 vid uppstarten mot 0,95 under körningen, och andelen
  över Π stiger 15 procent mellan körningens halvor.
- **Utbildningen dras givet yrket**: nivån ur TAB4360 och inriktningen ur
  TAB4359, givet yrke, ålder och kön. Det är samma tabeller som inträdaren
  använder, lästa åt andra hållet. Var cirkeln ska ligga är öppet beslut 5
  nedan.
- **Ingen tidigare yrkeshistorik** för startpopulationen. Den nuvarande
  arbetscirkeln och utbildningen räcker. Utan tidigare yrken underskattas
  bredden hos dem med långt arbetsliv, men det ger ingen inkörningsperiod.
- **De arbetslösa vid start** får ett senaste yrke och en
  arbetslöshetstid. Arbetscirkeln suddas ut i proportion till den tiden.
- **Prövningen:** en körning utan åldrande och utan inträde ska ha platta
  serier från år 0.
- **6a-i gjort** (`core/priming.py`, avgjord ordning 2026-09-18). Startyrkets
  cirkel guidar uppstartsmatchningen; efter placeringen får den anställda
  jobbets cirkel med tjänstetidens massa och vilaradien, och startyrkets
  cirkel tas bort. Den arbetslösa behåller startyrket som senaste yrke,
  läckt och utsuddat efter en arbetslöshetstid dragen exponentiellt med
  medel 115 dagar (baslinjens median 80 som exponentialfördelning), och
  arbetslöshetens klocka ställs bakåt lika mycket. Uppstartens
  fortsättningsregel från steg 3 är borttagen. Utbildningen givet yrket är
  6a-ii, efter steg 4. **Prövningen, fem år utan åldrande och inträde, frö
  1: serierna är inte platta.** Primingen flackar av q vid anställning
  något (0,748 → 0,937 mot 0,735 → 0,972 utan), men arbetslösheten
  halveras på fyra år (2 272 → 1 327) och pendlingen växer. Den dominerande
  inkörningen sitter i arbetsmarknadens stockar: uppstartsmatchningen lämnar
  marknaden långt från körningens jämviktsläge.
- **Uppstartens ordning** (dialog 2026-09-18): svag, stark, mitten --
  femtedelar efter konkurrenskraften i det egna startyrket, tre omgångar per
  grupp -- och högst tre erbjudanden utifrån per person. Prövat mot alla på en
  gång, svagast först i strikt ordning och ett sänkt anspråk i svansen (grenen
  `experiment/svagast-forst`). Ordningen ger lägre stockar vid start och en
  nästan platt lönespridning; resten av inkörningen, arbetslösheten ned
  omkring 40 procent på fyra år utan demografi, nås inte med ordningen. Det
  är inte relaxation genom jobbens omsättning, som skrevs först: vakanserna
  sätter sig på två år, och sedan bär pendlingens stockar fallet
  (`stockarna.md`). En tidsförkortad
  sökning (grenen `experiment/tidsforkortad-uppstart`) konvergerade först
  efter 4,5 virtuella år och tömde vakanserna, eftersom jobbflödena saknades.

**Inträdet.** De oskrivna bladen är de unga som kommer in i arbetskraften.
De får en utbildningshistorik, inte ett yrke. Grundskola, sedan
yrkesprogram, högskoleförberedande program eller ingen fullständig
gymnasieutbildning, därefter arbete eller eftergymnasial utbildning med
inriktning. Åldern vid inträdet följer nivån. Det första yrket är ett
**utfall av matchningen** med utbildningsstapeln, och TAB4359 för 25–29-åringar
blir därmed en validering, inte indata.

- **Valen dras ur kohortandelarna** i TAB655, kalibrerade så att modellens
  25–34-åringar återger tabellen. Val som svarar på den lokala
  arbetsmarknaden, genom lön och vakanser, är ett alternativ som ska utredas
  senare som en egen mekanism. Byggs det in från början finns inget att
  validera det mot.
- **Studieorten parkeras, och får en väg genom omgivningen**
  (`omgivning.md`, "Flyttningar"): studieflyttningen byggs med inträdet som
  utflyttning till omgivningen och återkomst därifrån. Gymnasium och högre utbildning finns inte i
  alla kommuner. Den som utbildar sig måste flytta eller pendla, och vissa
  kommer inte tillbaka. Det är ett för stort steg nu. Den kända följden är
  att alla som utbildar sig i modellen stannar, så att det lokala utbudet
  av högutbildade överskattas i kommuner som Ovansiljans. Mekanismen hör
  ihop med "Utbildningens geografi" nedan.

### Öppna beslut

1. **Vad intensiteten kalibreras mot.** Förslag: kvoten ingångslön mot
   medianlön per yrke ur SCB:s lönestatistik. Den mäter vad marknaden faktiskt
   betalar en nyexaminerad jämfört med en mogen arbetare, vilket är samma
   storhet som massfaktorn uttrycker.

2. **Kvalifikationsnivåns omfattning.** Antingen en binär grind per yrke,
   skattad ur andelen anställda med nivån, eller enbart legitimationsyrkena
   (SUN 721, 723, 724, 726, 727, 380, 861a). Papper 1 förklarar redan 61
   procent av variationen i utbildningskrav med geometrin, så en generell
   kravskala ovanpå den dubbelräknar. Grinden bör därför definieras snävt: ett
   formellt krav som INTE följer av uppgiftsinnehållet.

3. **Ett drag eller flera.** En civilingenjör har inte ett enda utfall. Ett drag
   ger en skarp cirkel; flera med delad massa ger en bredare individ. Förslag:
   ett — stapeln växer ändå när hon börjar arbeta.

4. **Okänd nivå och inriktning.** 62 000 personer 25–34 år saknar båda i TAB655,
   troligen med utländsk utbildning som inte registrerats. Får de bara
   grundskola underskattas de systematiskt.

5. **Startpopulationens utbildningsposition**, enligt ovan: vid nuvarande yrke
   som stationaritetsantagande, eller dragen.

---

## Vad χ är och inte är

Den ursprungliga modellen behandlade radiell förflyttning som fördjupning och
antydde att djup är nivå. Det är fel, och papper 1 visar hur fel.

χ mäter **hur skarpt orienterat uppgiftsinnehållet är mot sin riktning** — en
strukturell egenskap hos arbetet, inte ett mått på hur krävande det är.
Diskare har χ = 0,54 och ligger längre ut än servitörer på 0,49. Advokater
har 0,39 och ligger närmare origo än kemiingenjörer på 0,52.

Inom sektorer förutsäger χ högre utbildningskrav i norr (β = +3,55) och
nordost (+8,45) men **lägre** i väster (−2,48) och sydväst (−4,93). Att öka
χ innebär högre krav i norr och lägre i väster. χ och nivå är alltså inte
samma sak, och sambandet mellan dem byter tecken med riktningen.

Konsekvens för modellen: **utbildning ska inte höja χ.** Omskolning flyttar
individens position mot där jobben finns, vilket kan öka eller minska χ̄
beroende på var de ligger. Formell utbildning rör inte χ alls. Och
"specialisering" i betydelsen skärpt profil sker genom att *arbeta*
koncentrerat, inte genom att studera — diskaren blir inte diskare av en kurs.

---

## Varför nivån inte är överflödig

Geometrin är konstruerad **enbart ur uppgiftsinnehåll**. Utbildningskrav ingår
inte. Att de ändå organiseras systematiskt av (χ, ξ) är en oberoende
validering i papper 1.

Det innebär att geometrin *förutsäger* krav utan att innehålla dem. Men
sambandet byter tecken med riktningen, så residualen efter (χ, ξ) lär vara
både stor och systematisk. Frågan är empirisk:

> **Grindvaktsfråga.** Hur mycket av variationen i kravnivå förklaras av
> (χ, ξ), och hur mycket återstår?
>
> *Mäts:* Regression av O\*NET Job Zone på χ, ξ och deras interaktion, över
> samtliga yrken. Residualvariansens storlek och om den är systematisk
> (klustrad på yrkesfamilj, licensierade yrken, offentlig sektor).
>
> *Slutsats:* Är residualen liten tillför nivån lite. Är den stor och
> systematisk — vilket papper 1:s sektortabell antyder — finns något eget att
> modellera, och mönstret visar vad.

Frågan kostar en eftermiddag och kräver bara O\*NET-data som redan hämtas. Den
ska besvaras innan spärren byggs (steg 7 i byggordningen sist i detta
dokument).

Nivån har två roller som ska hållas isär. I **dragningen** avgör den var
utbildningscirkeln hamnar — sjuksköterska eller undersköterska — och det är
geometri, inte krav. I **spärren** avgör den vilka jobb som öppnas.
Grindvaktsfrågan gäller bara spärren: hur mycket kravnivå som återstår att
modellera när geometrin, med utbildningscirklar placerade efter nivå, har
förklarat det den kan.

---

## Varför nivån behövs från *fel* ände

Argumentet för nivån brukar vara att spärra svåra jobb. Diskaren visar att den
behövs lika mycket för att **öppna enkla**.

Den geometriska passformen är symmetrisk: en advokat är lika långt från
diskaren som diskaren från advokaten. Men kraven är inte symmetriska.
Advokaten kan diska; diskaren kan inte försvara i rätten. Utan en
kravdimension låtsas kärnan att diskning ligger utom räckhåll för alla som
arbetat med något annat.

Svaret är att passformens vikt ska följa kravet: irrelevant på zon 1,
avgörande på zon 5. Vem som helst kan få ett zon 1-jobb; frågan blir vem som
vill, och det avgörs av lönekravet. Det ger en mekanism för nedåtgående
rörlighet som geometrin ensam saknar.

---

## Vad som är ett tillskott

### Kedjan av förkunskaper

Att en nivå förutsätter den föregående är en **diskret restriktion som
geometrin inte innehåller**. Två yrken kan ligga nära varandra i planet medan
det ena kräver en examen som det andra inte ger. Omställningskostnaden blir
icke-monoton i avstånd: ett kort hopp kan vara dyrare än ett långt om det
korsar en nivågräns.

### Utbildningens geografi

Den starkaste idén. Om omskolning kräver att man pendlar eller flyttar dit
utbildningen ges, får glesbygdsarbetaren en **dubbel nackdel**: tunt
uppgiftsrum och ingen lokal väg ut ur det.

Mekanismen finns inte i litteraturen om thick labor markets, den är mätbar,
och den knyter ihop modellens två anpassningskanaler — pendling och omskolning.
En kommun kan vara tunn i uppgiftsrummet men ha ett lärosäte, eller tät men
sakna utbildningsutbud. Korsningen av de två är ny.

### Den mjuka spärren som tunnhetsmekanism

Individmodellen gör nivåspärren mjuk och låter dess lutning mjukna med lågt
lokalt marknadstryck. Arbetsgivare sänker krav när sökande är få (Modestino,
Shoag & Ballance). Det ger en motkraft i tunna marknader: brist på
kvalificerade gör att kraven mjuknar lokalt, vilket delvis kompenserar. Om det
stämmer är det en av mekanismerna bakom att glesbygden fungerar bättre än en
naiv modell förutsäger.

---

## Data

### Kravnivå per yrke

**O\*NET** har Job Zones (1–5) och modulen Education, Training and Experience.
Båda ligger i den ZIP som `scripts/fetch_data.py` redan hämtar; det är en
inläsning, inte en insamling.

**Den svenska motsvarigheten finns som fördelning, inte som yrkesattribut.**
TAB4360 ger utbildningsnivåns fördelning bland de anställda i varje yrke, och
det är den observerade fördelning som kravnivån per SSYK ska skattas som.
Kravet blir en sannolikhet i stället för ett tröskelvärde, vilket passar den
mjuka spärren.

### Utbildningsutbud per kommun

UHR och Skolverket har programutbud per lärosäte och ort. Myndigheten för
yrkeshögskolan har YH-utbildningar per kommun. Båda är öppna.

Det som behövs är en tabell `education_supply(municipal_code, level, field,
seats)` där `field` är en SUN-inriktning. Positionen behöver ingen egen
projektion: den dras ur yrkesutfallet enligt "Positionen: dra, inte
medelvärde". Det som återstår för utbudet är antalet platser per kommun, nivå
och inriktning. Kopplingen mellan utbildningsutbudet och arbetsmarknaden i
samma rum följer då direkt.

### Individens nivå och inriktning

Finns: `education_level` ur SCB:s utbildningsnivåer, koderna 1–7.

Fältet nådde länge ingenstans. `get_education_props` slog ihop skalan till tre
klasser och skrev strängarna "low", "medium" och "high" i individtabellen,
medan `init_competence` gör `int(float(e))` och fångar felet med nivå noll.
INGEN individ i startpopulationen fick därför sin utbildningscirkel — alla bar
bara grundskolan vid origo. Rättat: nivåerna 1–7 dras direkt och skrivs som
heltal.

Saknas: inriktningen. Den dras för startpopulationen ur P(inriktning | yrke,
nivå, ålder, kön).

Nyckeln SUN ↔ Job Zone är öppen.

---

## Designfrågor

**Hård eller mjuk spärr?** Mjuk — avgjort. En straffaktor per nivå under
kravet, med lutning som beror på marknadstryck.

**Ska utbildning kunna misslyckas?** Nej — avgjort. Onödig detaljeringsgrad.

**Kostar en nivåhöjning tid eller pengar?** Tid finns i modellen. Pengar
skulle kräva en förmögenhetsdimension som inte finns.

**Flytt kontra pendling till studier.** Modellen har ingen flytt. En mindre
variant är att låta utbildning pendlas till med högre avståndskostnad än
arbete, vilket fångar merparten utan att införa migration.

**Vad händer med den som studerar och blir erbjuden jobb?** Avgjort:
utbildning utesluter anställning under studietiden. Den som börjar studera
släpper sitt utlovade jobb tillbaka till marknaden.

**Ska formell utbildning också exponera?** Troligen ja, med en position som
motsvarar utbildningens innehåll. En läkarexamen är inte bara en nivå utan
också tre års exponering för medicinskt innehåll. Öppet hur vikten sätts.

---

## Konsekvenser för frågeställningarna

Om utbildningens geografi införs tillkommer en fråga i samma form som de sju
befintliga:

> **Fråga 8. Är utbildningsutbudets geografi en självständig
> omställningsbarriär?**
>
> *Hävdar:* Omställningskostnaden efter en chock stiger med avståndet till
> närmaste relevanta utbildning, även efter kontroll för uppgiftsrummets
> täckning. Kommuner som är tunna *och* saknar lokalt utbildningsutbud
> absorberar sämst.
>
> *Mäts:* Avstånd till närmaste utbildning inom den riktning chocken tvingar,
> per kommun. Regression av omställningskostnad på både täckning och
> utbildningsavstånd.
>
> *Motbevisas om:* utbildningsavståndet inte förklarar något utöver täckning,
> eller om de två är så korrelerade att de inte går att skilja åt.

Den sista falsifieringsgrunden är den verkliga risken: lärosäten ligger i stora
kommuner, som också har tät täckning. Identifikationen kräver kommuner som
skiljer sig i den ena dimensionen men inte den andra.

---

## Vad som måste loggas redan nu

Om systemet ska införas senare måste körningar som görs dessförinnan vara
jämförbara. Simuleringen loggar därför för varje utbildning: position före och
efter, förflyttningens längd, varaktigheten, och kommunen. Detta är infört.

---

## Den förenklade mekanismen (införd)

Bygger enbart på befintliga delar: geometrin, vakanserna och
pendlingskostnaden. Ingen ny data, inga nivåer, ingen förkunskapskedja.

**Riktad omskolning.** Den som ger upp på sin position riktar sin omskolning
mot där de nåbara, välbetalda vakanserna finns: målpunkten är en
överskottsviktad tyngdpunkt av tillgängliga positioner, och arbetaren flyttar
en bestämd andel av vägen dit. I en tät kommun ligger tyngdpunkten nära; i en
gles ligger den långt bort, eller saknas — och då sker ingen omskolning.

**Varaktighet efter avstånd.** Omställningstiden blir ett utfall i stället för
en konstant, och längre i tunna marknader.

**Kompetensen uppdateras vid slutet**, inte vid inskrivningen.

**Utbildning utesluter anställning.**

Vad mekanismen medvetet inte innehåller: nivåer, förkunskaper,
utbildningsutbud per kommun, kostnader, avhopp.

**Vad som ändras när individmodellen är byggd.** Den förenklade mekanismen
flyttade en fri punkt. Med kompetenscirklarna blir omskolningen en cirkel med
kursens position, radie och massa.

**Målet har samma fel som inriktningens medelpunkt.** `retraining_target`
(`core/occupations/utils.py`) tar den överskottsviktade tyngdpunkten av upp
till 50 nåbara vakanser. Ligger de åt två håll hamnar målet mellan dem, och
individen omskolas mot en punkt där inget jobb finns. Målet ska dras bland
vakanserna med överskottet som vikt. Riktningen mot där jobben finns behålls;
det är medelvärdet som ska bort. Andelen av vägen (`retraining_share`) blir
då överflödig: cirkeln läggs på målet, och hur mycket den räknas bestäms av
massan.

Radien var här beskriven som bred, vilket var ett antagande:
`retraining_radius2` är i dag 0,25, alltså r = 0,5, lika trubbigt som en
cirkel som diffunderat bort sin spets. En sådan cirkel ger massa på ny position
men ingen topp. Radien ska följa nivån, som för all utbildning.

Massan var här beskriven som studietiden, vilket ger en nyexaminerad nästan
full konkurrenskraft. Den ska vara studietid × intensitet.

---

## Byggordning

Varje steg är en egen mekanism och en egen commit. Steg som ändrar körningar
jämförs mot en baslinje med fem frön.

0. ~~**Baslinje**~~ — körd 2026-09-18: fem frön med
   `SCENARIO=scenarios/ovansiljan_3_kommuner.yml bash kor_0077.sh` på
   0b23237, som har samma kod som f4d2c03. Körningarna ligger i
   `output/run_20260918_031900` … `_033613`. Förra baslinjen, 68aa372,
   ligger i `output/arkiv/run_20260917_150334` … `_151823`. Mellan dem
   finns tre kodändringar, 23a53ef, 5df814b och f4d2c03, och de isoleras
   inte från varandra. Inget frö överlappar det andra paketets spann:

   | mått | 68aa372 | 0b23237 | fröspann |
   |---|---|---|---|
   | median q vid anställning | 0,909 | 0,950 | 0,002 |
   | andel q > 1 | 32 % | 40 % | 0,5 pp |
   | andel q < 0,40 | 8,6 % | 7,3 % | 0,1 pp |
   | median u_R_occ (mål 0,70) | 0,699 | 0,726 | 0,006 |
   | lönekvot w/Π vid anställning, p50 | 1,040 | 1,059 | 0,003 |
   | beståndet över Π, sista året | 71 % | 75 % | 0,7 pp |
   | anställda vid start | 12 738 | 12 923 | |

   Utbildningscirkeln ger fler en användbar cirkel från början. Därför
   matchas fler vid uppstarten och q vid anställning stiger. Men u_R_occ
   flyttar sig bort från målet med fyra gånger fröspannet: tillsättningarna
   sker längre bort i uppgiftsrummet mellan yrken när en bred cirkel bär
   kompetensen. Andelen av beståndet över Π rör sig åt fel håll, bort från
   de 50 procent som definitionen kräver.

   Slutläget är detsamma i båda baslinjerna: omkring 10 700 anställda, 450
   arbetslösa och 4 280 vakanser (vakansgrad 29 %). Pensionsavgångarna
   saknar inträde, så de anställda faller från 12 900 till 10 700 på tio år.
   Andelen över Π stiger 15–16 procent mellan körningens första och andra
   halva, i alla fem fröna. Vakansmått, bytesfrekvens och lönespridningens
   nivå går därför inte att kalibrera mot före steg 6.

   **Taket nås redan.** Cirkelnycklarna är yrken (O*NET), utbildningsnivåer
   och omskolningar. Räknat ur transitionerna har 13–17 individer per frö
   precis 12 cirklar, och 2–4 har haft fler och tappat den med minst massa.
   Det gäller omkring 20 av de 15 400 som förekommer i transitionerna, så
   steg 2 ensamt ska inte ge någon mätbar effekt. Gör det ändå det är något
   annat fel. Med en cirkel per händelse (steg 3) blir medianen omkring sex
   cirklar och maxvärdet 16, och 0,4 procent skulle gå över tolv.
   Uppskattningen räknar uppstartsmatchningen både som arbetscirkel och som
   tillträde och är därför något för hög.
1. ~~**`_union` följer sin formel**~~ — gjort. Avdraget görs mot varje
   starkare cirkel i stället för i en kedja (`individmodell.md`, avsnitt 2).
2. ~~**Inget tak på antalet cirklar.**~~ — gjort. Arrayerna växer med fyra
   platser när en rad blir full, och `max_circles` avvisas med besked.
   Antalet cirklar och radens bredd står på årsraden (`circles_*`) och i
   slutlägets `n_circles`.
3. ~~**En cirkel per händelse.**~~ — gjort. `Circles.add` slår inte längre
   ihop på nyckel; varje tillträde och varje fortbildning ger en ny cirkel.
   Skärpningen gäller alla cirklar i det yrke hon arbetar i, exponeringen
   bara den pågående anställningens (`individmodell.md`, avsnitt 2).
   Uppstartens anställning i det egna startyrket fortsätter startcirkeln.
   Fem frön på 7654248, mot baslinjen: median u_R_occ 0,725 → 0,733, med
   spann som inte överlappar (0,723–0,729 mot 0,730–0,736). Allt annat
   ligger inom fröspannet: q vid anställning 0,950 → 0,953, andel q > 1
   40 → 41 %, lönekvot p50, slutlägets arbetslösa och vakanser. Uppstarten
   är identisk frö för frö (samma antal anställda vid start). Bland de
   sysselsatta i slutläget är medianen 6 cirklar, p90 9 och max 19–21.
   Omkring 55 individer har fler än tolv, och radens bredd blir 20–24.
   Simuleringstiden är 214–217 s mot baslinjens 211, så tröskeln för
   obetydliga cirklar behövs inte.
4. **Läsare för TAB4359, TAB4360 och TAB655**, och rakingen till P(yrke |
   inriktning, nivå, ålder, kön), med kontrollerna ovan.
   - **Läsarna är gjorda** (`core/database/load_utbildning.py`), år 2024, till
     `employment_occupation_field`, `employment_occupation_level` och
     `population_level_field`. Kontroll 1 håller exakt: de två
     anställdatabellerna har samma 5 006 642 anställda och identiska
     yrkestotaler i alla 2 980 celler av yrke, ålder och kön; databasbygget
     kastar annars.
   - Vad datan visar (dialog 2026-09-18). I TAB655 för 25–34 år är
     förgymnasial nivå alltid allmän inriktning, och uppgift saknas på nivå
     sammanfaller med okänd inriktning (4,4 procent). De anställda 16–24 år
     (515 547) arbetar framför allt som butikspersonal (15,1 procent mot 5,0
     för alla åldrar), i snabbmat och kök (8,6 mot 2,1) och som servitörer
     (3,4 mot 0,8) -- de lågbetalda jobb som står tomma i modellen
     (`stockarna.md`, "Rekryteringstiden per bransch").
   - **Rakingen är gjord** (`core/utbildningsfordelning.py`, 4b). Den tredje
     marginalen, nivå × inriktning, tas ur TAB655 som FORM: tabellen anpassas
     först med tvådimensionell IPF till de anställdas nivå- och
     inriktningstotaler, som de två andra tabellerna redan bestämmer, så att
     bara sambandet -- oddskvoterna och de strukturella nollorna -- följer
     med. Som marginal hade den motsagt de andra, och IPF hade pendlat.
     Femårsklassen får tioårsklassen som innehåller den (25–29 och 30–34 får
     25–34). Alla 20 klasser av ålder och kön konvergerar mot alla tre
     marginalerna, på 1,3 sekunder. Rimlighet, 25–29 år:

     | utbildning | vanligaste yrkena |
     |---|---|
     | eftergymnasial ≥ 3 år, vård (kvinnor) | sjuksköterskor 31 %, 266 16 %, läkare 13 % |
     | gymnasial 3 år, vård (kvinnor) | undersköterskor 31 %, personliga assistenter 15 %, barnskötare 12 % |
     | gymnasial 3 år, teknik (män) | byggnadshantverkare 12 %, 741 9 %, mekaniker 7 % |
     | eftergymnasial ≥ 3 år, teknik (män) | ingenjörer 22 %, mjukvaruutvecklare 18 %, 311 14 % |
     | gymnasial 3 år, allmän (män) | butik 15 %, lager 6 % |

     16–24 år med förgymnasial utbildning: snabbmat och kök 18 %, butik 12 %,
     vårdbiträden 7 %, servering 5 %.
5. **Massan:** `EDU_MASS` blir studietid × intensitet.
6. **Priming och inträde** ("Två situationer" ovan). Först rättas
   startens yrkeskälla. Scenariot anger `occupation_source: register`, men
   `_register_profile` (`core/scenariobuilder.py`) frågar efter en kolumn
   `year` som `occupation_weights_by_municipality` saknar. Felet sväljs, och
   startens individer och jobb dras ur SNI. Nya jobb under körningen dras
   däremot ur registret via `World._occupation_profile`. Start och körning
   har därmed olika yrkesstruktur. Det är en tyst reserv. **Rättat:**
   frågan läser bara de kolumner som finns, och en tabell eller kommun som
   saknas ger ett fel med besked. För Mora har register- och SNI-profilen
   26 procent av massan gemensamt. Registret ger undersköterskor överst,
   SNI-vägen lagerarbetare. Kräver en ny baslinje.
   - **6a. Priming.** Jobben först, och arbetscirkeln på jobbets yrke.
     Utbildningen dras givet yrket. De arbetslösa får ett senaste yrke och
     en arbetslöshetstid. Uppstartens fortsättningsregel från steg 3 blir
     då överflödig.
   - **6b. Inträdet.** Utbildningshistorik ur kohortandelarna, och det
     första yrket som ett utfall av matchningen.
   - **6c. Studerande med extrajobb** (avgjort 2026-09-18). Gymnasieelever
     och studenter arbetar i regel en eller två kvällar i veckan eller på
     lördagar. BAS räknar den som arbetat en timme i november som
     sysselsatt, och sysselsättning går före studier, så deras positioner
     ingår i jobbmålet och de själva i arbetskraften. I modellen blir de
     vanliga 16–24-åringar med vuxnas anspråk, och butiks-, köks- och
     serveringsjobben står tomma (`stockarna.md`, "Rekryteringstiden per
     bransch": hotell och restaurang 121 dagar mot SCB:s 12). AKU (TAB3026,
     2024): 174 000 sysselsatta 15–24 år studerar, 157 000 på heltid,
     omkring en tredjedel av de sysselsatta i åldern; i BAS sannolikt fler.
     Byggs som antal, inte timmar: lågt anspråk, smal sökning (nära hemmet,
     låga krav), och aldrig arbetslös -- utan jobb är hon studerande, inte
     arbetslös, och går in och ut ur arbetskraften med jobbet. En andel av
     startens 16–24-åringar i arbetskraften blir studerande med extrajobb;
     hur AKU:s andel översätts till BAS avgörs då. Prövningen:
     rekryteringstiden i hotell och restaurang faller, och korrelationen per
     bransch mot TAB4307 (i dag −0,55) vänder. De som börjar arbeta direkt
     efter grundskolan är vanliga inträdare med förgymnasial nivå (6b).
7. **Grindvaktsfrågan**, och därefter spärren.
8. **Omskolningens mål dras** i stället för att medelvärdesbildas.
   Startpunkten försvinner samtidigt. `handle_start_education` räknar
   `x0` ur `x_occ` och lägger cirkeln `retraining_share` av vägen mot
   målet. Raden är kvar från 1b23138, när positionen var ett tillstånd och
   omskolningen flyttade punkten. I 42aeb2a blev slutet av omskolningen en
   cirkel, men början rördes inte, och sedan dess läser `x0` medelvärdet
   av alla cirklar. Det är det enda beslut i simuleringen som medelvärdet
   styr. Cirkeln läggs på målet, och `x0` och `retraining_share` tas bort.
