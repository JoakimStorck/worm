# Utbildning i WORM — designutkast

Detta är ett utkast, inte en specifikation. Det beskriver hur ett
utbildningssystem med nivåer, förkunskaper och geografiskt utbud skulle kunna
integreras, vilka data som krävs, och vilka avvägningar som måste avgöras
först. Ingenting av detta är byggt.

En förenklad mekanism, som bygger enbart på befintliga delar, beskrivs sist och
är införd.

---

## Varför frågan är svår

Geometrin är konstruerad **enbart ur uppgiftsinnehåll** — inbäddningar av
O\*NET:s task statements. Utbildningskrav ingår inte i konstruktionen. Att de
ändå organiseras systematiskt av (χ, ξ) är en *oberoende validering* i papper 1,
och det är den valideringens styrka att de aldrig såg konstruktionen.

Det innebär att geometrin **förutsäger** utbildningskrav utan att innehålla
dem. Sambandet är empiriskt, inte en identitet — och ett starkt samband kan
lämna betydande variation kvar. Den variationen är precis vad en
utbildningsdimension skulle kunna bära: två yrken kan ligga på samma punkt i
planet men kräva olika formell behörighet, vilket är en verklig restriktion som
geometrin varken innehåller eller förutsäger.

Invändningen är därför inte principiell utan empirisk, och den går att avgöra
innan något byggs:

> **Grindvaktsfråga.** Hur mycket av variationen i kravnivå förklaras av
> (χ, ξ), och hur mycket återstår?
>
> *Mäts:* Regression av O\*NET Job Zone på χ, ξ och deras interaktion, över
> samtliga yrken. Residualvariansens storlek och om den är systematisk
> (klustrad på yrkesfamilj, licensierade yrken, offentlig sektor).
>
> *Slutsats:* Är residualen liten tillför en nivådimension lite utöver
> geometrin. Är den stor och systematisk finns något eget att modellera, och
> mönstret i residualen visar vad.

Frågan kostar en eftermiddag och kräver bara O\*NET-data som redan hämtas. Den
bör besvaras först, av samma skäl som fråga 1 i frågeställningarna besvaras
före simuleringsarbetet.

Oavsett utfall är två delar av förslaget genuina tillskott, eftersom de inte är
nivådimensionen i sig utan restriktioner ovanpå den.

---

## Vad som är ett tillskott

### Kedjan av förkunskaper

Att en nivå förutsätter den föregående är en **diskret restriktion som
geometrin inte innehåller**. Två yrken kan ligga nära varandra i planet medan
det ena kräver en examen som det andra inte ger. Avståndet i planet säger
ingenting om att vägen dit går via tre års studier.

Detta gör omställningskostnaden icke-monoton i avstånd: ett kort hopp kan vara
dyrare än ett långt, om det korta korsar en nivågräns. Det är ett verkligt
tillskott till modellen och ett som går att pröva.

### Utbildningens geografi

Detta är den starkaste idén. Om omskolning kräver att man pendlar eller flyttar
dit utbildningen ges, får glesbygdsarbetaren en **dubbel nackdel**: tunt
uppgiftsrum och ingen lokal väg ut ur det.

Mekanismen finns inte i litteraturen om thick labor markets, den är mätbar, och
den knyter ihop modellens två anpassningskanaler — pendling och omskolning —
som i dag är oberoende. En kommun kan vara tunn i uppgiftsrummet men ha ett
lärosäte, eller tät men sakna utbildningsutbud. Korsningen av de två är ny.

### Vad som är osäkert

Att jobb kräver en viss nivå, och att individer har en nivå, i sig. Värdet av
det beror på grindvaktsfrågans svar: förklaras kravnivån väl av (χ, ξ) tillför
dimensionen mest brus, medan en stor och systematisk residual gör den
meningsfull. Nivåerna är däremot en förutsättning för de två tillskotten ovan,
som båda kräver att nivåer finns för att kunna uttryckas.

---

## Data

### Kravnivå per yrke

**O\*NET** har Job Zones (1–5) och modulen Education, Training and Experience.
Båda ligger i den ZIP som `scripts/fetch_data.py` redan hämtar; det är en
inläsning, inte en insamling.

**Svensk motsvarighet saknas som yrkesattribut.** SCB har utbildningsnivå per
person (SUN) och yrke per person i yrkesregistret. Kravnivån per SSYK måste
därför **skattas** som den observerade fördelningen av utbildningsnivå bland
dem som har yrket.

Det är sämre än ett normativt krav men i en mening bättre: det ger en
fördelning i stället för ett tröskelvärde, och kravet blir en sannolikhet
snarare än ett ja eller nej. En arbetare under den vanligaste nivån kan få
jobbet, bara mer sällan. Det passar dessutom modellens övriga logik, där
anställning redan avgörs av en sannolikhet.

### Utbildningsutbud per kommun

UHR och Skolverket har programutbud per lärosäte och ort. Myndigheten för
yrkeshögskolan har YH-utbildningar per kommun. Båda är öppna.

Det som behövs är en tabell `education_supply(municipal_code, level, field,
seats)` där `field` är kopplad till en position i uppgiftsrummet — vilket är
samma projektionsproblem som papper 4:s huvudspår löser för yrken. Utbildningar
kan positioneras med samma metod som yrken, ur kursbeskrivningar, och i samma
frysta bas. Det är värt att notera att en sådan projektion vore ett resultat i
sig: den placerar utbildningsutbudet och arbetsmarknaden i samma rum och gör
avståndet mellan dem mätbart.

### Individens nivå

Finns redan. `education_level` sätts per individ ur SCB:s utbildningsnivåer
(tabellen `education_level_municipality`, koderna 1–7). Fältet **används dock
ingenstans** i matchning eller dynamik. Det bör antingen kopplas in eller tas
bort; att bära ett fält som inte gör något är en felkälla när resultat ska
tolkas.

---

## Designfrågor som måste avgöras

**Hur förhåller sig nivå till χ?** Antingen är nivån en oberoende restriktion
ovanpå geometrin, eller så är den en observerbar konsekvens av χ. Det första
riskerar dubbelräkning, det andra gör nivån överflödig. En medelväg: nivån
begränsar bara *rörelser* (vilka omskolningar som är möjliga), inte
matchningen, som får fortsätta styras av geometrin. Då tillför nivån något utan
att konkurrera med χ.

**Ska utbildning kunna misslyckas?** Nej — beslutat. Onödig detaljeringsgrad.

**Kostar en nivåhöjning tid eller pengar?** Tid finns redan i modellen
(varaktighet). Pengar skulle kräva en förmögenhetsdimension som modellen inte
har, och som skulle behöva införas konsekvent även på andra ställen.

**Flytt kontra pendling till studier.** Modellen har i dag ingen flytt: individens
bostad är fast. Att införa flytt är en stor förändring som påverkar
pendlingsstatistiken, kommuntillhörigheten och populationens fördelning. En
mindre variant är att låta utbildning pendlas till med en högre
avståndskostnad än arbete, vilket fångar merparten av effekten utan att
införa migration.

**Vad händer med den som studerar och blir erbjuden jobb?** Avgjort i den
förenklade mekanismen nedan: utbildning utesluter anställning under studietiden.

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
jämförbara. Simuleringen bör därför redan i dag logga, för varje utbildning:
individens position före och efter, förflyttningens längd, varaktigheten, och
kommunen. Utan det går vinterns körningar inte att ställa mot de senare.

Detta är infört i den förenklade mekanismen.

---

## Den förenklade mekanismen (införd)

Bygger enbart på befintliga delar: geometrin, vakanserna och pendlingskostnaden.
Ingen ny data, inga nivåer, ingen förkunskapskedja.

**Riktad omorientering.** Den som ger upp på sin position riktar sin omskolning
mot där de nåbara vakanserna faktiskt finns: målpunkten är en
överskottsviktad tyngdpunkt av tillgängliga positioner, och arbetaren flyttar
en bestämd andel av vägen dit.

Detta ger tunnhetsmekanismen utan ny data. I en tät kommun ligger tyngdpunkten
nära, omskolningen blir kort. I en gles ligger den långt bort, eller saknas
helt — och då sker ingen omskolning, vilket i sig är resultatet.

**Varaktighet efter avstånd.** Att flytta en kort sträcka i planet är en kurs;
att flytta långt är en utbildning. Omställningstiden blir därmed ett utfall i
stället för en konstant, och längre i tunna marknader.

**Kompetensen uppdateras vid slutet**, inte vid inskrivningen. Under studietiden
står arbetaren kvar på sin gamla position.

**Utbildning utesluter anställning.** Den som börjar studera släpper sitt
utlovade jobb tillbaka till marknaden.

Vad mekanismen medvetet inte innehåller: nivåer, förkunskaper, utbildningsutbud
per kommun, kostnader, avhopp. Allt detta hör till designen ovan och kräver
data som ännu inte finns.
