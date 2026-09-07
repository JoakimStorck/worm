# Utbildning i WORM — designutkast

Detta är ett utkast, inte en specifikation. Det beskriver hur ett
utbildningssystem med nivåer, förkunskaper och geografiskt utbud skulle kunna
integreras, vilka data som krävs, och vilka avvägningar som måste avgöras
först. Det bygger på individmodellen i `individmodell.md`, som ska läsas
först.

En förenklad mekanism, som bygger enbart på befintliga delar, beskrivs sist och
är införd.

---

## Vad utbildning gör

Två skilda saker, som den ursprungliga modellen blandade ihop.

**Exponering för uppgiftsinnehåll.** Att gå en kurs är att tillägna sig en
uppgiftsbunt utan att ha ett jobb. Effekten är av samma slag som
arbetserfarenhet: en cirkel läggs till individens samling, med kursens
position, nivåns radie och massa lika med studietiden. Detta är
**omskolning**. Se `individmodell.md`, avsnitt 2.

**Höjd kvalifikationsnivå.** Att ta en examen höjer ℓ och öppnar jobb som
kräver den. Det rör inte geometrin. Detta är **formell utbildning**.

En yrkesutbildning gör båda. En akademisk examen gör mest det andra. En intern
kurs gör mest det första. Distinktionen är mätbar i data.

Utbildning ger **ingen egen löneeffekt**. Nivån öppnar jobb; att de betalar
mer är prisfältets sak. Omskolning flyttar mot bättre betalda jobb; att de
betalar mer är också fältets sak. Detta tar bort en parameter och gör
grindvaktsfrågan nedan skarpare.

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
ska besvaras innan steg 4 i individmodellens byggordning.

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

**Svensk motsvarighet saknas som yrkesattribut.** SCB har utbildningsnivå per
person (SUN) och yrke per person i yrkesregistret. Kravnivån per SSYK måste
**skattas** som den observerade fördelningen av utbildningsnivå bland dem som
har yrket. Det ger en fördelning i stället för ett tröskelvärde — kravet blir
en sannolikhet, vilket passar den mjuka spärren.

### Utbildningsutbud per kommun

UHR och Skolverket har programutbud per lärosäte och ort. Myndigheten för
yrkeshögskolan har YH-utbildningar per kommun. Båda är öppna.

Det som behövs är en tabell `education_supply(municipal_code, level, field,
seats)` där `field` är kopplad till en position i uppgiftsrummet — samma
projektionsproblem som papper 4:s huvudspår löser för yrken. Utbildningar kan
positioneras med samma metod, ur kursbeskrivningar, i samma frysta bas. En
sådan projektion vore ett resultat i sig: den placerar utbildningsutbudet och
arbetsmarknaden i samma rum och gör avståndet mellan dem mätbart.

### Individens nivå

Finns redan: `education_level` ur SCB:s utbildningsnivåer, koderna 1–7.
Fältet **används ingenstans** i dag. Det kopplas in i steg 4 i
individmodellens byggordning. Nyckeln SUN ↔ Job Zone är öppen.

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

Bygger enbart på befintliga delar: geometrin, vakanserna och pendlingskostnaden.
Ingen ny data, inga nivåer, ingen förkunskapskedja.

**Riktad omskolning.** Den som ger upp på sin position riktar sin omskolning
mot där de nåbara, välbetalda vakanserna finns: målpunkten är en
överskottsviktad tyngdpunkt av tillgängliga positioner, och arbetaren flyttar
en bestämd andel av vägen dit. I en tät kommun ligger tyngdpunkten nära; i en
gles ligger den långt bort, eller saknas — och då sker ingen omskolning.

**Varaktighet efter avstånd.** Omställningstiden blir ett utfall i stället för
en konstant, och längre i tunna marknader.

**Kompetensen uppdateras vid slutet**, inte vid inskrivningen.

**Utbildning utesluter anställning.**

Vad mekanismen medvetet inte innehåller: nivåer, förkunskaper, utbildningsutbud
per kommun, kostnader, avhopp.

**Vad som ändras när individmodellen är byggd.** Den förenklade mekanismen
flyttade en fri punkt. Med kompetenscirklarna (steg 1) blir omskolningen en
cirkel: kursens position, en bred radie, och massa lika med studietiden.
Riktningen mot vakansernas tyngdpunkt behålls; effekten blir principiell i
stället för en godtycklig andel av vägen. Formell utbildning tillkommer i
steg 4.
