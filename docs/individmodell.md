> **Observera.** Avsnitten om matchning och lön (4–5) beskriver formler från
> före 0049 och 0061. Den gällande beskrivningen av matchning och
> lönebildning — hur de fungerar, vad som är prövat, och ordningen på det som
> återstår — finns i [`lonemodell.md`](lonemodell.md). Avsnitt 2 (kompetensen)
> och 7 (utbildningen) är aktuella; där koden ännu inte följer dem står det
> under *Läget i koden*. Avsnitt 10 bär arbetsreglerna.

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
händelse i karriären, och tillsammans bildar de ett fält över uppgiftsskivan.
Cirkeln är samma primitiv som papper 1 bygger yrken av — centroid plus radie —
så individen är gjord av samma delar som rummet hon rör sig i. Papper 2:s mått
på överlapp mellan yrken, R_a + R_b − d_ab, är cirkelöverlappet; individens
konkurrenskraft i ett jobb är dess mjuka form.

### Cirkeln

Varje cirkel k har centrum (x_k, y_k), radie ρ_k, massa m_k och en vilaradie
ρ_home som den skärps mot när den används. Storheterna definieras av vad de
gör i konkurrenskraften nedan: **centrum** är var toppen ligger, **radien**
avväger topp mot räckvidd, **massan** avgör hur mycket cirkeln räknas alls.

### En cirkel per händelse

**Varje händelse i en individs karriär, från grundskola till pension, ger en
egen cirkel.** Två anställningar i samma yrke är två cirklar, inte en som
vuxit. Historiken bevaras som den skedde. Att uppdelningen i sig inte blir en
premie är unionens sak (nedan), inte lagringens.

| Händelse | Centrum | Radie | Massa |
|---|---|---|---|
| Grundskola | origo | 1 (hela skivan) | låg, lika för alla |
| Allmän utbildning | origo | 1 | studietid × intensitet |
| Utbildning med inriktning | dragen yrkesposition | efter nivå: bred gymnasial, nära r_o eftergymnasial | studietid × intensitet |
| Anställning i yrke o | yrkets centroid + personlig avvikelse | r_o | växer under anställningen |
| Fortbildning | den pågående anställningens position | r_o | kursens tid × intensitet |
| Omskolning | dragen målposition | som utbildning | studietid × intensitet |

Hur utbildningarnas cirklar placeras, och varför, står i
`utbildningsmodell.md`. Kort: inriktningen ger positionen, nivån ger radie och
massa, och positionen **dras** ur det observerade yrkesutfallet i stället för
att tas som dess medelpunkt. Djup är radie och massa, inte χ (avsnitt 1).

Grundskolan är ett golv: ingen riktning, låg massa överallt. Den som föds kan
bli vad som helst och är ingenting än.

Den personliga avvikelsen vid en anställning är r_o/√k, där k är antalet
uppgifter i yrket: individen utför en delmängd av dem, och hennes centroid
avviker därefter.

*Läget i koden.* En cirkel per händelse är infört: `Circles.add` skapar
alltid en ny cirkel, nyckeln är kategorin (yrket, utbildningsnivån) och
platsen i raden är cirkelns identitet. Varje tillträde och varje fortbildning
ger en ny cirkel; fortbildningen läggs på den pågående anställningens
position och vilaradie. Ett undantag: **uppstartens anställning i det egna
startyrket fortsätter startcirkeln**, eftersom den redan är den pågående
anställningen med massa ur tjänstetiden. Det gällde 797 av 12 962
uppstartsanställningar i baslinjen. De övriga 12 165 hamnade i ett annat yrke
än startyrket, vilket i sig är värt att förstå.

Utbildningen är fortfarande en enda cirkel `EDU:ℓ` för den högsta nivån,
placerad på individens nuvarande yrke — en position som per konstruktion
inte kan förklara varför hon hamnade där. Det ändras i utbildningsstapeln.

### Dynamiken

Fyra processer, samma för alla cirklar oavsett ursprung.

**Exponering.** Den aktiva cirkeln — den pågående anställningens — får massa
med takten a per år.

**Läckage.** All massa avtar: dm/dt = −λm. Läckaget gör två saker med en
parameter: det gallrar det gamla, och det **mättar** massan under aktivitet,
eftersom dm/dt = a − λm går mot m\* = a/λ. Utan läckage skulle en stor massa
göra diffusionen verkningslös — en snickare med fyrtio år bakom sig skulle
vara fullt konkurrenskraftig efter trettio års uppehåll.

**Diffusion.** En cirkel som inte används sprids: dρ²/dt = 2D, upp till ett
tak på fyra gånger dess egen vilaradie i kvadrat. Det är glömska: spetsen
förloras där man inte verkar, men allt finns kvar, alltmer diffust. Taket
infördes när diffusionen gjorde arbetslöshet absorberande — cirkeln suddas, q
faller, hon blir inte anställd, och skärpning kräver just den anställning hon
inte får. Det är relativt och inte absolut, så att den som har en bred profil
från början inte straffas av samma gräns som den med en smal.

**Skärpning.** Den aktiva cirkeln dras mot sin vilaradie med tidskonstanten
τ_s: dρ²/dt = (ρ_home² − ρ²)/τ_s.

**Återkomsten till ett tidigare yrke** (avgjort). Med en cirkel per händelse
får den som återvänder en ny cirkel, medan den gamla ligger kvar med massan
men utan spets. Skärpningen gäller därför **alla cirklar i det yrke hon nu
arbetar i**, medan exponeringen — ny massa — bara går till den pågående
anställningens cirkel. Annars vore erfarenhet ingen fördel vid återkomst: så
länge cirklar slogs ihop på nyckel skärptes den gamla på sex månader, och det
beteendet behålls.

| Parameter | Betydelse | Värde |
|---|---|---|
| a | exponeringstakt | 1 per år (enhet) |
| λ | läckage | halveringstid 15 år; m\* = a/λ ≈ 21,6 |
| D | diffusion | 0,004 per år; tak 4·ρ_home² |
| τ_s | skärpning | 6 månader |
| m_ref | massa som ger nästan full konkurrenskraft | 2 år |

Vad det ger för en arbetare i ett yrke med r_o = 0,28, mätt vid hennes eget
jobb:

| Inlärning | 0,5 år | 1 år | 2 år | 5 år | 10 år | 20 år |
|---|---|---|---|---|---|---|
| q | 0,22 | 0,39 | 0,62 | 0,89 | 0,98 | 1,00 |

| Uppehåll efter 20 år | 5 år | 10 år | 20 år | 30 år |
|---|---|---|---|---|
| q | 0,79 | 0,65 | 0,46 | 0,32 |
| skärpa | 0,80 | 0,66 | 0,49 | 0,40 |

Massan efter tjugo år är 13,1, sex tiondelar av mättnaden; diffusionen når taket
efter knappt trettio år.

### Glömskan är läckaget — inget tak på antalet cirklar

Det finns ingen gräns för hur många cirklar en individ bär. Glömska är läckage
och diffusion, och det räcker: en cirkel som inte används förlorar massa och
skärpa, och dess bidrag krymper utan att den behöver tas bort.

Taket K = 12 som stod här kom från representationen, inte från modellen.
Cirklarna ligger i fyllda arrayer N × K, så att månadssteget blir några
vektoroperationer över hela populationen, och K måste då ha ett värde
(42aeb2a). Talet var inte härlett. Så länge cirklar med samma nyckel slogs
ihop slog det sällan till: ett tiotal är en rimlig övre gräns för hur många
*olika* saker en människa gör. Med en cirkel per händelse räknar det i stället
händelser och slår till mitt i karriären, och regeln "minst massa faller bort"
blir ett modellantagande gömt i lagringen. Det första som föll vore
grundskolan. Dess massa läcker från 1,0 till 0,63, 0,40 och 0,25 efter 10, 20
och 30 år, och den är den enda cirkel som ger något stöd i de delar av skivan
individen aldrig varit i.

Arrayerna växer därför när en rad blir full. Blir beräkningen dyr hoppas
cirklar vars största möjliga bidrag, (1 − e^{−m/m_ref})·skärpan, ligger under
en tröskel över i konkurrenskraften — de tas inte bort. Tröskeln bestäms av
vad som är mätbart i q, inte av hur många platser som råkar finnas.
Beräkningskostnad är ett verkligt skäl, men det ska inte bestämma vad
individen minns.

*Läget i koden.* Inget tak. Raden växer med fyra platser när någon behöver
fler (`Circles._grow`), och `circle_slots: 12` är bara startbredden. Tröskeln
som hoppar över obetydliga cirklar i konkurrenskraften är inte byggd; i
baslinjen har ingen fler än fjorton cirklar.

### Konkurrenskraften

Varje cirkel bidrar vid jobb j med radie r_o:

    c_k = (1 − e^{−m_k/m_ref}) · [2r_o²/(ρ_k² + r_o²)] · exp(−d_kj²/2γ²(ρ_k² + r_o²))

Tre faktorer, var och en i [0, 1]. **Massan**, mättande: skillnaden mellan noll
och två års erfarenhet är stor, mellan tio och tjugo liten. **Skärpan**: ett när
cirkeln är lika bred som jobbet, lägre när den är bredare. **Avståndet**: samma
kärna som för yrken, med cirkelns radie i bredden. Smal cirkel ger hög topp och
kort räckvidd, bred ger låg topp och lång.

Konkurrenskraften är **unionen av täckningen, inte summan** (0078). Cirklarna
tas i fallande bidragsordning, och var och en räknas bara till den del den
täcker något som de starkare inte redan täckte:

    q_ij = Σ_k c_k · Π_{l<k} (1 − O_lk · c_l)

där O_lk är Bhattacharyya-överlappet mellan cirklarna k och l, i sluten form ur
centrum och bredder. Det finns ingen min(1, ·). En mogen cirkel på jobbet ger
c ≈ 1, och det är en normering, inte ett tak (`lonemodell.md` 1.1).

**Unionen är det som bär en cirkel per händelse.** Som summa var uppdelningen
en premie: tjugo år delade på tre närliggande jobb gav 2,66, mot 1,00 för samma
tjugo år i ett, och modellen divergerade. Under unionen ger två identiska mogna
cirklar 1,00. Bredd lönar sig när en andra erfarenhet täcker uppgifter som den
första inte täckte, och bara då — i rörligheten, inte som en stapel på ett jobb
man redan behärskar.

**Platta cirklar staplas nästan som en summa.** Unionen drar av i proportion
till överlapp *gånger täckning*, och en cirkel med radie 1 täcker lite, så
nästan ingenting dras av trots att överlappet är fullständigt. Allmänna
cirklar i origo, massa 1 vardera, vid ett typiskt jobb:

| Antal | 1 | 2 | 3 | 5 | 10 | *en med massa 2* |
|---|---|---|---|---|---|---|
| q | 0,054 | 0,105 | 0,154 | 0,243 | 0,427 | *0,087* |

Varje allmän händelse höjer alltså golvet. Staplade cirklar når förbi vad en
enda cirkel med radie 1 kan nå oavsett massa, skärpan 2r_o²/(1 + r_o²) ≈ 0,145.
Det är avsett. Unionen läser två platta cirklar som täckning av olika
uppgifter, och gymnasiet lär ut annat än grundskolan även om geometrin inte kan
placera skillnaden. Två till tre allmänna steg per liv håller effekten liten.

**Avdraget görs mot varje starkare cirkel, inte i en kedja.** Koden drog
tidigare av cirkeln på plats k bara mot den på plats k − 1 och förde produkten
vidare. För två cirklar är det samma sak. Från tre är det fel: två identiska
anställningar och en cirkel åt annat håll gav 0,858 mot formelns 0,978,
eftersom cirkeln åt annat håll drogs av för täckning den inte delar. Med
dagens tre cirklar per startindivid var felet högst 0,009, men med en cirkel
per händelse är identiska cirklar regel. Rättat som steg 1 i byggordningen.

Den mogna arbetaren vid sitt eget jobb: massa över referens, ρ = r_o, d = 0,
q ≈ 1. **Kalibreringen mot 1,03 task-radier står**, eftersom den handlar om
erfarna som byter. Samma person efter tjugo år borta: skärpan 0,49 och q 0,46 —
hon känns igen men är inte den hon var. Nybörjaren med enbart grundskola:
q ≈ 0,05 överallt. Advokaten vid diskbänken: lite från juridikcirkeln, lite
från golvet, och en diskcirkel som växer från första månaden.

### Vad detta ersätter

Positionen som tillståndsvariabel, bredden r_i som tillväxtregel,
`initial_r`, `switch_cost_kappa` och `breadth_from_move`. Omorientering
urholkar av sig själv: den gamla cirkeln diffunderar medan den nya byggs.

Sammanfattande mått — centroid, χ̄, ξ̄, riktningskonsekvens, spridning —
härleds ur cirklarna för loggning och validering. De är inte tillstånd.

### Individens position

Cirklarna är samma sak som den gamla punkten med radie, men ackumulerad:
individen bygger ett utfall av erfarenheter, och var och en bidrar olika
mycket till konkurrenskraften i det jobb hon söker. Hon kan ha många.

**Individens position är hennes nuvarande eller senaste erfarenhets
position**: den pågående anställningens cirkel, annars den cirkel som senast
tillkom. **Hon har ingen egen radie.** Varje erfarenhet har sin.

Konstruktionens idé syns i golvet. Grundskolan och den allmänna utbildningen
har radie 1, och därför når den som bara har grundskola alla enkla jobb,
även diskaren som ligger en bit ut på skivan. Konkurrenskraften är låg men
aldrig noll. Den som når ett bättre betalt jobb väljer det. Positionen styr
inget av detta, eftersom q räknas ur cirklarna.

*Läget i koden.* `x_occ`, `y_occ`, `chi`, `xi`, `r_i` och `R` i
individtabellen är fortfarande `Circles.summarize`: ett medelvärde av alla
cirklars centrum viktat med massa/ρ², där grundskolecirkeln i origo ingår,
och r_i är cirklarnas genomsnittliga radie. Det är varken positionen ovan
eller en radie hon har. Medelvärdet styr ett enda beslut, omskolningens
startpunkt (steg 8 i byggordningen i `utbildningsmodell.md`). I övrigt läses
det av `d_task` och `u_R` vid tillträde, av statistiken och av
händelseloggen. Loggens kopia har varit fryst sedan 8cb9f83: `_KolumnCache` i
`core/log.py` byggs inte om när kolumnerna skrivs om. Visaren
(`scripts/export_viz.py`), som flyttar individerna med loggens fält, har
därför visat individer som står still.

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

### Arbetsställets yrken (avgjort 2026-09-18)

Jobbets yrke dras ur arbetsställets bransch och storleksklass
(`core/bransch.py`): yrkesregistrets P(SSYK3 | bransch, klass) gånger
crosswalken till O\*NET. En läkare anställs alltså inte på en bilverkstad.

**Blandningen av yrken är verklig och ska finnas kvar.** Chefer, kontor och
städ är 7–35 procent av varje bransch, och ett stort arbetsställe är inte
begränsat till en typ av yrke. Men arbetsstället har en riktning: det är inte
ett slumpurval ur hela branschen. I dag dras varje jobb oberoende, och ett
arbetsställe med minst 20 jobb blir nästan lika brett som kommunen: RMS-avstånd
till centroiden 0,33 mot 0,39 för Moras hela jobbstock, och 28 O\*NET-koder i
effektiv mening.

Bredden har tre källor, och de tas i ordningen:

- **a. Crosswalken.** En SSYK3-grupp sprids på i median 19 O\*NET-koder,
  med RMS 0,19 inom gruppen; städare (911) på 12 koder med RMS 0,33. Ett
  arbetsställe realiserar varje svenskt yrke som EN O\*NET-kod: dess
  mekaniker är samma yrke, inte 21. Ingen ny parameter, och fördelningen
  över befolkningen är oförändrad. **Gjort.** Uppmätt i Mora, arbetsställen
  med minst 20 jobb: antalet O\*NET-koder i effektiv mening föll från 28
  till 8, men RMS-spridningen bara från 0,333 till 0,327. Förutsägelsen att
  crosswalken bar det mesta av bredden var fel för det måttet. Ett
  arbetsställe har i median 20 SSYK3-grupper, och varje grupp realiseras
  som EN slumpmässig punkt, så gruppens avvikelse från sin centroid finns
  kvar mellan grupperna. Bredden i rummet sitter i blandningen av svenska
  yrken och ändras först av b. Jobbens och invånarnas yrkesfördelning har
  nu 0,65 av massan gemensamt i stället för 0,84: samma väntevärde, men
  jobben är klumpigare per kod.
- **c. Branschens grovhet.** G rymmer både bilverkstaden och butiken. Om SCB
  publicerar yrke gånger tvåsiffrig SNI för riket skiljs de åt med data.
- **b. Ett kärnyrke som sätter arbetsställets specialistprofil.** Kärnan
  dras ur branschen, och övriga yrken viktas mot den med avståndet, blandat
  med en andel stödyrken utan avståndsvikt så att blandningen finns kvar.
  Två parametrar, bredden och stödandelen. Vad de kalibreras mot är öppet;
  data om yrkessammansättning per arbetsställe saknas.

**Validering mot alla 290 kommuner** (`scripts/validera_yrken_per_kommun.py`,
TAB4436, SSYK3-nivå). Mekanismens förväntade yrkesfördelning i en kommun är
branschmixen gånger rikets P(yrke | bransch), alltså antagandet att yrke och
kommun är betingat oberoende givet bransch. Gemensam massa med den faktiska
fördelningen, p10 / median / p90:

| | p10 | median | p90 |
|---|---|---|---|
| mekanismen | 0,70 | 0,78 | 0,87 |
| rikets yrken utan bransch | 0,64 | 0,72 | 0,83 |
| länet utan kommunen, per bransch | 0,72 | 0,79 | 0,86 |
| brusgolv: urval av kommunens storlek ur den faktiska | 0,93 | 0,95 | 0,98 |

Branschmixen förklarar en del (0,72 → 0,78), men avståndet till brusgolvet är
stort, och det krymper med kommunens storlek (0,73 i den minsta kvartilen,
0,86 i den största). Länets fördelning utan kommunen själv tillför nästan
inget: avvikelsen är inte regional utan kommunens egen. De sämsta är bruks-
och industriorter med en dominerande arbetsgivare -- Oxelösund 0,58 (stål),
Olofström 0,63 (fordon), Karlsborg 0,64 (regemente), Gällivare 0,68 (gruva),
Hofors 0,67 (stål) -- där ett enda arbetsställe med egen profil styr
kommunens yrkesmix. Tyngdpunkten i uppgiftsrummet flyttar sig lite: 0,044 i
median, mot yrkesradien 0,27. Ovansiljan: Mora 0,87, Orsa 0,77, Älvdalen 0,75.

Det talar för b: avvikelsen är just arbetsställen med en specialistprofil
inom branschen. Men b med kärnor dragna ur riket återger kommunernas
KLUMPIGHET, inte deras faktiska profil -- Oxelösunds stålverk blir ett
slumpmässigt tillverkningsarbetsställe.

### Kommunens profil i arbetsställena (beslutat 2026-09-18, designutkast)

**Beslut.** Modellen bygger på befintliga kommuner och generaliserar ur
befintlig struktur, så kommunerna ska ha sin faktiska profil från start. En
kommun som domineras av en industri ska göra det i modellen, och en kommun
som domineras av turism likaså. Kommunens profil styr från vilka branscher
och från vilka yrken arbetsställena får sin profil, och ju spetsigare
kommunens profil är, desto smalare är arbetsställena avgränsade i
uppgiftsrummet.

Profilen är stabil nog att bygga på. Gemensam massa bransch × yrke mellan
2020 och 2024 i TAB4436: Oxelösund 0,86, Olofström 0,85, Mora 0,87,
Malung-Sälen 0,82, Åre 0,79, Älvdalen 0,79, Orsa 0,74. Rikets fördelning gav
Oxelösund 0,58.

**Utkast, att pröva före bygge:**

1. **En pool per kommun och bransch.** Kommunens jobb i bransch s får yrken ur
   kommunens egen P_k(ssyk | s) i TAB4436, i heltal (största rest). Summan
   över arbetsställena är då kommunens profil exakt, inte bara i väntevärde.
2. **Kärnan först, störst först.** Arbetsställena i branschen tas i fallande
   storlek. Vart och ett drar ett kärnyrke ur det som återstår i poolen, med
   antalet som vikt. Det största arbetsstället får alltså troligast det
   dominerande yrket: stålverket får metallarbetarna.
3. **Profilyrkena viktas mot kärnan.** Arbetsställets övriga jobb tas ur
   poolen med vikten antal · exp(−d² / 2 r_c²), där d är avståndet mellan
   SSYK-gruppernas tyngdpunkter i uppgiftsrummet och r_c kärnans task-radie.
   Bredden är alltså kärnyrkets egen radie, ingen fri parameter. Spetsigheten
   följer av poolen: i en kommun där branschens jobb ligger tätt finns bara
   närliggande yrken att ta, och arbetsställena blir smala av sig själva.
4. **Stödyrkena utan avståndsvikt.** Chefer (SSYK 1), administration (4) och
   städ (91) -- 16,9 procent i riket, 7–35 procent per bransch -- fördelas ur
   poolen utan avståndsvikt. Blandningen finns kvar, och stödandelen kommer
   ur data i stället för att vara en parameter.
5. **O\*NET-realiseringen per arbetsställe** (a) är oförändrad.
6. **Nya jobb under körningen** följer arbetsställets profil: kärnan sparas
   på jobben (core_ssyk), och ett nytt jobb dras ur P_k(ssyk | s) med samma
   avståndsvikt mot kärnan, stödyrkena utan. Aggregatet bevaras då bara i
   väntevärde; driften mäts under körningen.
7. **Storleksklassens inverkan på yrket släpps.** TAB4436 saknar storlek.
   Arbetsställenas storlek dras fortfarande givet branschen.

**Prövningen.** Mot 2024 är valideringen inte längre oberoende, eftersom
poolen ÄR 2024. Oberoende: bygg poolen ur 2020 och jämför med 2024, med
kommunens egen stabilitet 2020→2024 som måttstock. Arbetsställenas bredd
mäts som förut (RMS mot centroiden, effektivt antal yrken) och ska bli
smalare i spetsiga kommuner.

**Öppet.** Kommunens jobbmål kommer från jobbandelar och skiljer sig från
TAB4436:s anställda (Mora 9 948 mot 10 223); med en pool ur TAB4436 ligger
det nära till hands att ta målet därifrån också.

---

## 4. Matchning: två frågor med olika ägare

För varje par (individ, jobb) ställs två frågor.

### Kan hon få det — arbetsgivarens fråga

    möte:       med sannolikhet q_ij                          (passform)
    värde:      p_ij = q_ij^(k·r_j)                            (produktivitet)
    affär:      p_ij·Π_j ≥ max(w_res, φΠ_j)                    (deltagande)
    nivåspärr:  p_nivå(ℓ − zon, tryck)                         (steg 4)

**Passformen** är konkurrenskraften q_ij ur avsnitt 2: unionen av hennes
cirklars täckning vid jobbet. För en mogen arbetare med en cirkel reduceras
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

## 5. Lönen: förankrad i fältet, individen förhandlar

Fältet Π är den observerade genomsnittslönen i yrket. Den individuella lönen
förhandlas fram enligt Nash, men med ett villkor som binder nivån:

    w / Π = (1 − β) · max(w_res, φΠ)/Π + β · p        affär om p·Π ≥ max(w_res, φΠ)

**Ankaret.** Referensarbetaren — fullt produktiv, p = 1, med reservationslön
lika med yrkets egen lön — måste få exakt Π. Annars är Π inte vad vi säger att
det är. Löser man Nash-formeln för det villkoret försvinner både
produktionsskalan och vakanskostnaden, och kvar blir ett viktat medel av vad
hon kräver och vad hon är värd. I jämvikt, när reservationslönen är den egna
lönen, konvergerar w mot p·Π: lönen anpassar sig till produktiviteten, och
full produktivitet ger fältlönen.

*Varför det behövdes.* Utan ankaret drev lönerna åt båda hållen samtidigt:
23 procent av yrkena fick sin median exakt på avtalsgolvet och 37 procent låg
över fältlönen, lagerarbetare på 1,28 gånger. En global produktionsskala kan
inte respektera att Π är ett genomsnitt.

**Produktiviteten** p är inte konkurrenskraften q utan q^(k·r_j), där r_j är
jobbets kravintensitet ur kapabilitetsfältet (Technology fields). Samma q ger
motsatta produktiviteter: den okvalificerade producerar 0,007 av en läkare
och fullt som diskare. Se avsnitt 4.

**Golvet är en fallback, inte ett klipp.** Avtalslönen φΠ är vad arbetaren
vet att hon minst kan få, så hennes effektiva reservation är max(w_res, φΠ).
Utfallet ligger *över* golvet och varierar med p; ingen massa hamnar exakt
på det. Arbetsgivarens deltagande, p·Π ≥ effektiv reservation, är hennes
vinstvillkor: kan arbetaren inte producera tarifens värde finns ingen affär.
**Kompetenströskeln följer av att avtalslön möter produktivitet**,
q^(k·r) ≥ φ, och är strängare ju mer jobbet kräver — kirurgen kräver q ≥ 0,81,
diskaren ingenting.

**Två roller för passformen.** q styr *om mötet leder någonstans*:
arbetsgivaren föredrar den erfarna diskaren fast vem som helst kan diska, och
arbetaren söker sig till det hon känner till. Det är vad Rayleigh-kalibreringen
mot 0,70 task-radier bygger på. p styr *vad hon är värd*. Att låta p styra
mötet tog bort lokaliteten för halva marknaden och gav median u_R 1,20.

Två parametrar: β och φ. Arbetsgivarens alternativ som funktion av lokalt
tryck tillkommer i steg 3, som en justering av β snarare än som en egen term.

Utbildning ger **ingen egen löneeffekt**. Nivån öppnar jobb; att de betalar
mer är fältets sak.

Inga motbud från befintlig arbetsgivare i denna version.

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

*Läget efter 0088.* Sökningen från anställning finns sedan 0049; sedan 0088
äger individen sin nästa söktidpunkt (`next_search_time`, en per person),
med rampen `on_the_job_search_ramp_days` vid varje tillträde. Rampen är ett
MODELLVAL, inte en kalibrering: empiriskt är separationsrisken som högst
under det första året (Farber, Jovanovic), men WORM har ingen inlärning av
matchkvalitet, och rampen hindrar att den nyanställde byter igen av samma
skäl som hon nyss bytte. Puckeln ovan förutsätter inlärning och väntar.
`on_the_job_search_factor` kalibreras mot ~10 procent ARBETSGIVARBYTEN per
år (SCB: 10--12 i högkonjunktur, 6--8 i lågkonjunktur); den implicerade
sökfrekvensen per anställd läses av mot AKU:s ombytessökande som
överidentifierande test.

### Interna byten: notisen

En tredjedel av jobbytena i AKU är byte av yrke inom nuvarande
arbetsgivare. Arbetsgivare gör det på två sätt -- söker internt först och
annonserar bara om ingen tar positionen, eller annonserar externt och låter
interna och externa söka samtidigt -- och ingetdera är konsekvent. Det
gemensamma är att de egna anställda får veta att positionen finns. Det
modelleras som en NOTIS, inte som en policy:

- När en position postas hos arbetsgivare E får varje anställd hos E ett
  extra sökdrag mot just den positionen vid t + `internal_notice_lead_days`.
  Draget rör inte hennes `next_search_time`.
- Mötessannolikheten i draget är 1 (det är vad en notis är), pendlings-
  kostnaden noll. Reservation, överskott och bytesfriktion är hennes vanliga.
- Ansökan går i samma kö och samma urval (högst q bland behöriga) som
  externa. Försprånget `internal_notice_lead_days` är parametern: noll ger
  "annonsera externt, alla söker"; längre än tiden till första externa
  ansökan ger "sök internt först".

Två utfall är TEST, inte parametrar: andelen interna byten av alla byten
ska hamna kring en tredjedel, och de ska koncentreras till stora
arbetsgivare -- små har sällan en position att gå till, och arbetsgivarens
positioner ligger i olika yrken så att q sällan räcker. Båda mäts med AKU:s
definition (byte av SSYK4 inom arbetsgivare) ur loggen. Träffas inte
tredjedelen med försprång noll kalibreras försprånget, som då är tolkbart:
hur länge arbetsgivare tittar internt innan de annonserar.

Ordning: efter att stegen är kalibrerad (0089) och v/u_min rättade (0090).
Läggs notisen in före det flyttar en del av de externa bytena in i
företaget och faktorn måste sättas om.

`quit_job` (borttagen 0085), `internal_job_change` och
`start_internal_training` ersätts av denna enda mekanism plus notisen. Ofrivilliga separationer kvarstår som jobbförstörelse.
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

Specificerad i `utbildningsmodell.md`. Det väsentliga:

**Varje avslutad utbildning är en händelse och ger en cirkel**, även den
allmänna. Utbildningen gör två saker som modellen håller isär: exponering för
uppgiftsinnehåll, alltså cirkeln, och formell kvalifikation, alltså nivån ℓ,
som stegvis och med förkunskapskrav öppnar jobb genom den mjuka spärren i
avsnitt 4. En yrkesutbildning gör båda. En högskoleförberedande gör mest det
andra.

**SUN klassar utbildning på två dimensioner, och de blir cirkelns storheter.**
Inriktningen ger positionen. Nivån ger radien och massan. Djup är radie och
massa, inte χ.

**Trappan.** Grundskolan saknar inriktning. Gymnasiets yrkesprogram har
inriktning, medan de högskoleförberedande klassas som allmänna. Eftergymnasial
utbildning har nästan alltid inriktning. Allmän utbildning, på vilken nivå som
helst, blir en cirkel i origo med radie 1, ovanpå grundskolans.

**Positionen dras.** En inriktning är en fördelning över yrken, inte en plats.
Dess medelpunkt hamnar mellan yrkena och ger en cirkel utan topp. Individen
drar i stället ett yrke ur P(yrke | inriktning, nivå, ålder, kön) och får sin
cirkel där. Spridningen ligger i populationen, inte i individens cirkel.

**Omskolning** flyttar mot där välbetalda, nåbara jobb finns, med varaktighet
efter sträckan. Målet ska dras bland de nåbara vakanserna. I dag är det deras
överskottsviktade tyngdpunkt, vilket har samma fel som inriktningens
medelpunkt.

Utbildning och omskolning uppdaterar historiken vid *slutet*, genom en ny
cirkel. Båda utesluter anställning under tiden: den som börjar studera släpper sitt utlovade jobb.

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

## 8b. Ålder och arbetslivets längd

Individen bär en ålder. Den dras vid uppstarten ur SCB:s folkmängd per
ettårsklass för kommunen (`population_by_age`, BE0101), ökar med ett år vid
varje årsskifte, och bestämmer tre saker.

**Arbetslivets längd.** L = ålder − inträdesålder, där inträdesåldern följer
utbildningsnivån (19, 20 respektive 24 år). Tenure i nuvarande yrke kan inte
överstiga L. Utan den gränsen drogs tenure exponentiellt med medel åtta år
oberoende av allt annat, och eftersom cirkelns massa är
m_mättnad·(1 − e^(−λ·tenure)) startade tjugofemåringar mättade.

**Utträdet.** Den som når riktåldern (67) lämnar arbetskraften. Satt hon på en
position blir den **vakant, inte förstörd**: arbetsgivaren ska tillsätta den
igen. Ersättningsrekryteringen är det dominerande rekryteringsflödet i en
kommun som inte växer, och den fanns inte i modellen så länge ingen lämnade av
åldersskäl.

**Vad åldern ännu inte gör.** Inget inträde sker, så arbetskraften krymper med
avgångarna. Deltagandet behandlas som platt över arbetsför ålder, vilket är
fel i känd riktning: de yngsta och de äldsta deltar mindre. Massan följer
fortfarande tenure i nuvarande yrke och inte hela arbetslivet — den som bytt
yrke har byggt massa i det tidigare, och de cirklarna finns inte i
startpopulationen. Sökintensitet, arbetslöshetens varaktighet och lön beror
inte på ålder.

---

## 9. Validering

Representationen är en teori, inte en design, om den kan vara fel. Den är
validerad om simulerade individer reproducerar **papper 2:s fyra stiliserade
fakta utan att de kodats in**:

| Faktum | Värde | Väntad mekanism | Status |
|---|---|---|---|
| Rörligheten är lokal | inom delsystem median ~0,7; globalt 1,03 | passformens kärna, kalibrerad | primärt mål |
| Två delsystem | 73 % inom, 27 % över | geometri och prisfält | prövas utan chefsyrken |
| Centripetala fält | flöden böjer mot delsystemens kärnor | vakansernas täthet: folk rör sig dit jobben är många | prövas utan chefsyrken |
| Asymmetri | 35 % fysiskt → kognitivt, 20 % omvänt | **befordran** — se nedan | utanför modellen |

**Om tvärövergångarna.** De 27 procent som korsar delsystemgränsen i CPS är
nästan uteslutande övergångar till eller från chefsyrken. Chefsyrken för alla
branscher klustrar på den kognitiv-mänskliga sidan, medan de som får
uppdragen kommer från alla yrken. Tvärflödet och dess asymmetri är därmed i
första hand **befordran** — en intern karriärstege i Doeringer–Piores mening —
inte uppgiftsbaserad rörlighet. Det är den interna arbetsmarknadens signatur;
geometrin fångar den externa.

Modellen har ingen befordran och ska inte bedömas på det fjärde faktumet.
Valideringen utesluter övergångar där käll- eller målyrke är chefsyrke
(SOC 11-xxxx) och jämför mot inom-delsystem-värdet 0,70, som är målet för den
uppgiftsbaserade matchningen. Chefsövergångarna rapporteras separat.

Skulle befordran införas senare finns en billig form: en vakant chefsposition
tillsätts inifrån, av den med längst tjänstgöring hos arbetsgivaren,
oberoende av geometri. Det skulle reproducera tvärflödet av rätt skäl med en
enda regel. Det är inte prioriterat: det är ett eget lager, och det är inte
centralt för glesbygdsfrågan.

Målet 1,03 är en blandning av inom- och tvärövergångar. En gles kommun med få
kognitiva jobb bör ha få tvärövergångar och därmed en lägre global median. Att
jaga 1,03 vore att kalibrera bort den skillnad som ska mätas. Kompletterande
empiri visar dessutom att de flesta övergångar är kortare än det globala
måttet antyder.

Därtill: bokföringen sluten, och vakansstocken enligt Littles lag mot svensk
vakansgrad.

De två första faktumen är de skarpa testen för den uppgiftsbaserade
matchningen. Det tredje prövas när sökning från anställning finns.

---

## 10. Arbetsregler

Byggordningen som stod här är genomförd (0036–0080). Ordningen på det som
återstår finns i [`lonemodell.md`](lonemodell.md) avsnitt 5.

Kvar står de regler som visat sig kosta att bryta. Varje rad nedan har ett
pris betalt i felsökning.

**En ström, sådd ur fröet.** `sample_points` utan `rng` läser systementropi
och struntar i `np.random.seed`: arbetsgivarnas och individernas koordinater
drogs på nytt varje körning, och två körningar på samma commit och frö gav
1 376 mot 1 364 arbetslösa år ett (0109). Fröspannet i rapporten mätte
därmed frö PLUS koordinatbrus, och "samma frö ger samma körning" var ett
antagande vi aldrig prövat. Allt slumpmässigt går genom `self.rng` respektive
världens generator, och varje nytt bibliotek prövas mot att två anrop med
samma frö ger samma tal innan det används.

**Invariantkontrollen skrivs före mekanismen.** U = L − J + V höll genom hela
jobbytesfallet i 0079 därför att testet fanns först. De två fel som låg nära —
att frigöra den gamla positionen vid erbjudandet i stället för vid tillträdet,
och att sätta innehavaren på det nya jobbet under uppsägningstiden — hade båda
gett en tyst läcka i bokföringen.

**En kodväg per sak.** Sex fel i serien var två vägar som gjorde samma sak och
glidit isär: `r_req` ur SELECT:en, `n_applicants` ur `transitions_table`,
`theta` ur en vitlista, `eta` ur ett `hasattr`, `w_neg` som saknade producent,
och `u_R` mot `u_R_occ` i figur mot rapport. Uppstarten anropar därför samma
funktioner som körningen (0069), och argumenten byggs på ett ställe
(`search_config`).

**Inga tysta vakter.** `if x in df.columns` och `except Exception` gjorde att
beståndsmåttet och lönerevisionen var avstängda under fem hela körningar utan
att något larmade. Saknas något som ska finnas är det ett fel som ska kastas,
inte en gren som tar en annan väg. Ett `hasattr`-fallback som alltid slår till
ser ut som ett medvetet val.

**Mät, gissa inte.** Lönerevisionen som jag var säker på var flaskhalsen
kostade en sekund per körning; booleska skanningar av jobbtabellen kostade
fyrtio. Och unionsberäkningen var trettiosju gånger för långsam därför att
testvärlden har 240 jobb och den riktiga 10 754 — ett prestandatest mot
realistisk storlek hade fångat det.

**Rätt population, rätt kolumn.** `u_R` mäter från individens position,
`u_R_occ` mellan yrkena; flödet är inte beståndet; uppstartens anställningar är
inte mobilitet. Flera tolkningar byggde på fel kolumn innan 0074, däribland
hela resonemanget om bottenkvartilens U-form.

**Fröspannet är tröskeln.** Nu 0,007 för u_R och 0,4 procentenheter för u. En
modelländring som ger mindre än så har inte visat något.

**Formen ska falla ut, inte antas.** Lognormaliteten i lönefördelningen kom ur
att q är en summa av produkter, inte ur en anpassning — och den blev synlig
först när taket `min(1, q)` togs bort. En degenererad fördelning, en atom eller
en vägg, är ett besked om att en tillståndsvariabel slutat bära information.

---

## 11. Öppna frågor

- Bytesfriktionens storlek. Finns som `switching_cost_share` sedan 0079,
  satt till 0,05 som storleksordning; ska kalibreras mot andelen jobbyten per
  år (lonemodell.md 5).
- Om k_vakans ska bero på tunnhet i uppgiftsrummet.
- Arbetsgivarens avvisningskostnad: om den ska bero på hur tunn poolen är, och
  om den är samma sak som k_vakans sett från andra hållet.
- Nyckeln SUN ↔ Job Zone.
- Form och skala för α(zon).
- Utbildningscirklarna. Positionen dras ur P(yrke | inriktning, nivå), radien
  per nivå kalibreras mot rörligheten, massan är studietid × intensitet
  (`utbildningsmodell.md`). Inget av det är byggt; byggordningen står där.
- Inträdet på arbetsmarknaden. Åldern finns sedan 0155 och utträdet med den,
  men ingen kommer in. Befolkningsbanan per kommun (historik plus
  framskrivning) och kohortinträdet är nästa demografiska steg, och med det
  blir arbetskraftsdeltagandet ett utfall i stället för en parameter.
  Inträdarens cirkel *är* utbildningens: hon kommer in med sin
  utbildningsstapel och utan anställning. Därför byggs inträdet efter
  utbildningscirklarna.
- Startpopulationens tidigare cirklar. Massan ur hela arbetslivet kräver
  tidigare yrken; i dag bär individen bara sitt nuvarande. De lägre
  utbildningsstegen saknas av samma skäl: SCB registrerar bara den högsta
  utbildningen. Avgjort 2026-09-18: ingen fullständig historik byggs.
  Primingen lägger arbetscirkeln på jobbets yrke och drar utbildningen
  givet yrket (`utbildningsmodell.md`, "Två situationer").
- Om en spretig karriär är ett signalproblem i sig, utöver vad cirklarnas
  överlapp ger. Parkerad.
- Städningen av punktmodellen (avsnitt 2, "Individens position").
  Medelvärdet i `Circles.summarize` ersätts av positionen ur nuvarande eller
  senaste erfarenhet, eller tas bort. Samtidigt försvinner det som hänger på
  punkten: reservgrenarna för q utan cirklar i `search_once` och
  `matching_core`, `u_R` och `d_task` mätta från medelpunkten, r_i i loggen
  och visaren, `initial_r` i `configreader`, samt `chi_add`, `r_add`,
  `xi_add`, `_occ_prob`, `apply_capability_update_LEGACY` och
  `compute_utility_matrix` i `core/occupations/utils.py`. Den sista anropar
  `compute_surplus_matrix`, som inte längre finns. Loggrättelsen görs
  oavsett.
