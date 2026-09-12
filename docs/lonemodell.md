# Lönebildning och kompetens i WORM

Status per patch 0081. Dokumentet beskriver hur modellen **fungerar** i
koden, vad som är **prövat** mot data, och vad som **återstår**. Det ersätter
avsnitt 4 (matchning och lön) i `individmodell.md`, som beskrev formler från
före 0049 och 0061.

Grundregeln för allt nedan: **ingen form påtvingas utfallet.** Mekanismerna
motiveras var för sig, och fördelningarna som faller ut är förutsägelser som
ska kunna slås ut. En degenererad fördelning -- en atom, en vägg, en enda
frihetsgrad -- är inte ett fel mot ett mål utan ett besked om att en
tillståndsvariabel slutat bära information.

---

## 1. Kompetens

Individen är en samling **cirklar** i skivan, en per erfarenhet:
grundskola i origo (radie 1), utbildning på yrkets riktning, och en
arbetscirkel per jobb hon haft. Varje cirkel har centrum, spridning ρ² och
massa m.

Dynamiken har fyra tidsskalor, alla i `core/occupations/competence.py`:

| | parameter | verkan |
|---|---|---|
| exponering | a | massan i den aktiva cirkeln växer |
| läckage | λ, halveringstid 15 år | all massa gallras |
| diffusion | D | inaktiva cirklar breddas, spetsen förloras |
| skärpning | τ_s, 6 månader | den aktiva cirkeln återfår sin spets |

**Massan är bunden.** Jämvikten mellan exponering och läckage är
m\* = a/λ ≈ 13. Det är balansen mellan tillväxt och glömska, och den finns
redan: en ensam cirkel kan inte växa obegränsat.

### 1.1 Konkurrenskraft q

q_ij är hur väl individ i täcker jobb j. Jobbet är ett moln av uppgifter med
radie r_o. Varje cirkel bidrar med

    c_k = (1 − e^{−m_k/m_ref}) · 2r_o²/(ρ_k²+r_o²) · e^{−d_k²/2γ²(ρ_k²+r_o²)}

massa (mättande), skärpa (matchar cirkelns bredd mot jobbets), avstånd.
Varje faktor ligger i [0, 1]. En ensam mogen cirkel exakt på jobbet ger
c ≈ 1: det är **normeringen**, inte ett tak.

**q är unionen av täckning, inte summan** (0078). Cirklarna tas i fallande
bidragsordning och varje ny räknas bara till den del den täcker något de
starkare inte redan täckte:

    q = Σ_k c_k · Π_{l<k} (1 − O_lk · c_l)

O_lk är Bhattacharyya-överlappet mellan cirklarna, sluten form ur centrum
och bredder. Två identiska mogna cirklar ger 1,00 och inte 2,00; tjugo år
delade på tre närliggande jobb ger 1,00 och inte 2,66.

Skälet: bredd lönar sig **när en andra erfarenhet täcker uppgifter i jobbet
som den första inte täckte, och bara då.** Man kan inte täcka mer än hela
jobbet, så q har en övre gräns i geometrin. Bredd i vanlig mening --
erfarenhet från flera trakter av skivan -- lönar sig inte som en stapel på
ett jobb man redan behärskar utan i **rörligheten**: fler jobb inom räckhåll
och bättre position vid nästa byte. Att flytta till en helt ny trakt är att
börja om; avståndskärnan släcker de gamla cirklarna och grundskolan i origo
är enda stödet.

Före 0078 var q summan, och summan hade ingen gräns. Över tio år gav det en
premie på fragmentering: median q vid anställning 1,21, 67 procent över ett,
andelen av beståndet över Π stigande till 80 procent, vakansstocken
tredubblad. Modellen divergerade.

### 1.2 Produktivitet p

    p_ij = q_ij^{k·r_j},   k = 2

r_j är jobbets kravintensitet ur kapabilitetsfältet (läkare 0,84, diskare
0,00). Vid r_j = 0 är p = 1 för alla: kompetens höjer inte produktionen i ett
diskjobb. Vid r_j = 0,84 är p = q^{1,68}: kirurgen måste passa.

q och p är olika storheter med olika roller. q avgör om mötet leder någonstans
(mötessannolikhet, arbetsgivarens urval); p avgör vad hon är värd.

### 1.3 Vad som återstår i kompetensen

- **Inlärningstiden är densamma för alla jobb.** m_ref = 2 år. Data säger att
  bilglasmontörer når 53 procent av produktivitetsvinsten på åtta månader
  (Lazear & Shaw) medan lärare når full produktivitet först efter flera år.
  m_ref ska vara en funktion av r_j. Modellen har r_j på varje jobb, så det
  kostar ingen ny data; det kräver kalibrering mot två ändar.
- **Överlappet mäts mellan cirklarna, inte via jobbet.** Rätt storhet är hur
  mycket av *det här jobbet* cirkel k täcker som l inte täckte -- en
  trippelprodukt. Nuvarande approximation är pairwise Bhattacharyya.
- **Normeringen.** "En mogen cirkel på jobbet ger 1" bör bli "medianinnehavaren
  täcker 1", eftersom Π är medianlönen bland innehavare och ingen täcker sitt
  jobb fullt. Skillnaden avgör hur mycket utrymme som finns över ett.

---

## 2. Matchning

En kodväg, `core/matching_core.py`, delad av uppstart och körning (0069).

1. **Möte.** Arbetaren ser en vakans med sannolikhet min(1, q). Tolkas som
   informationsfriktion: hon känner inte till alla.
2. **Val.** Bland dem hon möter väljer hon på förväntat överskott
   S = (w − c·km − w_res) / (1 + n), där n är antalet som redan sökt jobbet
   (0057). Kön i nämnaren är riktad sökning i Moens mening och kostar ingen
   parameter. Utan den samlades 806 ansökningar på ett jobb medan nio tusen
   positioner aldrig sågs.
3. **Ansökan.** Hon ansöker och fortsätter söka; flera ansökningar kan ligga
   ute (0058). Annonsen stänger efter `application_window_days` = 40.
4. **Urval.** Arbetsgivaren väljer högst **q** bland behöriga (0055). Inte p:
   vid r_j ≈ 0 är p identiskt ett och kan inte rangordna någon. Motivet är
   upplärningskostnad och risk, inte produktion. Prisfrågan saknas: lönen är
   en funktion av p, så bäst kvalificerad och bäst per krona ger samma ordning.
5. **Tillträde** efter `hiring_decision_days` = 10, plus
   `notice_period_days` = 30 för den som lämnar en anställning (noll för
   arbetslösa). Bara annons och beslut hör till vakansen som SCB:s KV mäter.

Uppstarten är samma sak i slumpmässiga omgångar med
`bootstrap_applicants_per_vacancy` = 2,4 sökande per ledig vakans, härlett ur
körningens tightness (0069, 0072). Inte geografiskt partitionerad: det gav
startbeståndet en gradient efter körordning. Uppstartens anställningar är
märkta `is_bootstrap` och ligger utanför valideringsurvalet (0073).

**Lokaliteten mäts som u_R_occ** -- avståndet mellan käll- och måljobbets
yrken, normerat med källans radie -- på CPS-urvalet utan chefsövergångar,
återgångar och uppstart (0074). Det är vad CPS observerar. u_R, avståndet
från individens egen position, är en annan storhet och gav en U-form som
inte finns i det mått som gäller.

**Utfall per 0077:** median u_R_occ 0,70–0,72 mot papper 2:s 0,70, spann
över frön 0,007. Kvartilerna i r_req 0,79 / 0,74 / 0,79 / 0,60: lokaliteten
är bäst där kraven är högst, och där är det grinden som lokaliserar, inte
urvalet. Sökandegradienten är 9 / 7 / 3 / 3.

---

## 3. Lönebildning

### 3.1 Ingångslönen

    w = Π_j · p^θ,   nedåt begränsad av avtalslönen φ·Π_j
    affär om   p·Π_j/λ ≥ w

- **Π_j = Π_o · e^{η_j}** är jobbets normallön: yrkets fältlön ur
  prisfältet gånger en arbetsgivareffekt (0061, 0063). η bär storlekspremie
  och en residual per arbetsgivare, `employer_size_premium` och
  `employer_wage_sd`. Pris, inte position: jobben ligger kvar på centroiden.
- **θ = 0,5** är graden av individuell lönesättning. θ = 0 ger alla exakt Π,
  θ = 1 var och en sin produktivitet. Dimensionen som skiljer avtalsområden
  åt och är observerbar per bransch.
- **λ = 0,65** är löneandelen. Utan den vore arbetsgivarens villkor p ≥ 1 och
  ingen under medianen skulle anställas. Grinden blir p ≥ λ^{1/(1−θ)} = 0,42.
- **φ = 0,70** är avtalsgolvet, som golv och inte som halva formeln.
- **Reservationslönen** avgör om hon tackar ja, inte vad hon är värd. Den
  sätts till den förhandlade lönen vid anställning och faller vid avslag.

Ankaret överlever: p = 1 ger Π. Men medianen ligger också där, eftersom
median p ≈ 1, och det är vad definitionen kräver.

**Varför inte Nash.** Den tidigare formeln w = (1−β)·max(w_res, φΠ) + β·p·Π
såg ut att ha två frihetsgrader men hade en: reservationen låg under golvet
för alla efter första arbetslöshetsperioden, första termen var konstant 0,35,
och medianen satt låst vid 0,85. 87,5 procent av anställningarna följde
w/Π = 0,35 + 0,5p på tre decimaler. Ett golv som bär trettiofem procent av
lönen för var och en är inget golv.

### 3.2 Årlig revision

    g = märke + β_q · (Δlog q − medel Δlog q),   g ≥ 0
    w ← w · (1+g)/(1+märke)

Procent på befintlig lön, prestation som spridning kring märket (0067). Den
individuella delen är tillväxt i konkurrenskraft **relativt kollegorna**
(0075): mot noll blev den ensidig, eftersom q växer för nästan alla, och
beståndet drev. Centrerad är medelpåslaget exakt märket, den reala nivån
stationär, och fördelningen tvåsidig. Nominella löner sänks aldrig; reala
kan falla. Märket faller ut ur alla kvoter eftersom både löner och Π mäts
realt.

Anropas från `handle_new_year` **efter** beståndets tvärsnitt, så att
revisionen är en observerbar hoppfunktion mellan två tvärsnitt.

### 3.3 Vad som är prövat

| storhet | modell | referens |
|---|---|---|
| form inom yrke | P90/P50 = 1,24, P50/P10 = 1,25 | lika om lognormal |
| spridning mot kravnivå | σ² = σ_η² + (θkσ_q)²r², men σ_q faller med r | prövas mot SCB per SSYK |
| arbetsgivarandel av variansen | 11 % | AKM 10–20 % |
| global P90/P10, flöde | 2,36 | lönestruktur 2,20 (bestånd) |
| andel av beståndet över Π_o | 0,53 stabilt i tre år, sedan drift | 0,50 om Π är median |

Lognormaliteten är inte antagen: q är en summa av produkter, alltså
approximativt lognormal, och p = q^{kr} bevarar det. Den föll ut när taket
`min(1, q)` togs bort (0060).

Spridningen växer med kravnivån men långsammare än den enkla formeln säger,
eftersom σ_q faller från 0,93 till 0,25 över kvartilerna: urvalet och grinden
gör de anställda homogena där kraven är höga (0066). Det är ett resultat, och
det gör att regressionen mot SCB ska pröva den reducerade förutsägelsen --
monoton tillväxt -- inte lutningen.

### 3.4 Vad som återstår i lönebildningen

- **Stock mot flöde.** Beståndet är fortfarande smalare än inflödet,
  sd(log w) 0,31 mot 0,34. Karriärvidgningen finns inte än; revisionens
  spridning är 2,5 procentenheter mellan p10 och p90. β_q ska kalibreras mot
  observerad spridning i löneutveckling, inte gissas uppåt.
- **Bytare mot stannare.** Den som byter arbetsgivare inom samma yrke får i
  data bättre löneutveckling än den som stannar. Modellen förutsäger det --
  bytaren omvärderas till formeln, stannaren släpar med sin
  revisionshistorik, och bara den som tjänar på det byter eftersom
  reservationen är nuvarande lön -- men måttet finns inte. Det ska läggas
  till och läsas av, inte byggas in.
- **Lokalt tryck.** En vakans utan sökande blir inte dyrare. θ endogent i
  kön är Moens riktade sökning på lönesidan; kön i överskottet är samma sak
  på söksidan och finns.
- **Reservationen framåtblickande.** Den faller med historik. Värdet av
  faktiska alternativ kan inte kollapsa, och i Mora är den låg för att det
  finns lite att gå till -- glesbygdspåståendet som utfall.

---

## 4. Varför modellen inte konvergerar

Över tio år växer vakansstocken från 614 till 1 368 och arbetslösheten från
1 362 till 2 163, medan andelen av beståndet över Π hoppar till 0,93. Sökning
från anställning (0079) gav dubbelt så många sökande per vakans men stoppade
inte tillväxten. Tre saker verkar samtidigt, och de ska skiljas åt innan något
byggs.

### 4.1 Stegen är för snabb

I Burdett–Mortensen är beståndets lönefördelning

    G(w) = F(w) / (1 + κ(1−F(w))),   κ = λ₁/δ

alltså kvoten mellan hur ofta anställda får erbjudanden och hur ofta de kastas
tillbaka till arbetslöshet. Med `on_the_job_search_factor` = 5 söker den
anställde var 140:e dag, λ₁ ≈ 2,6 per år mot δ = 0,1: **κ ≈ 26** mot empiriska
skattningar kring 2–5. Praktiskt taget hela beståndet hamnar i toppen av
erbjudandefördelningen, vilket är vad 0,93 över Π betyder. Spridningen
kollapsar först, 0,30 → 0,22, därför att alla samlas vid samma tak, och
återhämtar sig sedan långsamt genom revisionen.

### 4.2 Restpoolen tränger undan -- INTE BELAGT (0086)

Diagnosen löd: arbetsgivaren väljer högst q, anställda har mogna cirklar och
vinner, arbetslösa ackumuleras. Den vilade på måttet "100 procent av
tillsättningarna till anställda", som var en konstant ur bool("False")
(0086). Rätt mätt går 46 procent till anställda och 54 till arbetslösa,
trots median q 0.79 mot 0.59: 23 procent av vakanserna har en enda sökande,
och den är då oftast arbetslös. Arbetslösheten växte inte av
undanträngning utan av den exogena avgången (0085). Skillnaden i q kvarstår
som observation; Becsis restpool är fortfarande rätt begrepp för den, men
den är inte orsaken till nivån i u. Stycket nedan behålls som bakgrund.

Becsi (2026) formaliserar precis det: arbetsgivaren möter inte arbetskraften
utan **restpoolen**, de som ännu inte matchats, och typer utanför
acceptansmängden lämnar bara genom egen sökning. I hans räknade exempel ligger
96 procent av poolmassan under tröskeln. Det är Blanchard–Diamonds
rankningsmodell, och den är verklig — men här utan motkraft.

### 4.3 Arbetsgivaren betalar inget för att avvisa

Becsis bidrag är att skilja **sökkostnaden**, priset för att titta, från
**avvisningskostnaden**, priset för att titta bort. Med k = 0 är arbetsgivaren
maximalt selektiv, och hans Proposition 3 säger att det ger sämst
genomströmning: när det är dyrt att gå ifrån en upptäckt sänker man sina krav.

WORM har kostnaden fysiskt — fyrtio dagar till om ingen anställs — men
arbetsgivaren väger den inte i urvalet.

### 4.4 Vakanser avvecklas aldrig

Positioner postas mot ett storleksmål oavsett om de går att fylla, och en
vakans som inte fylls står kvar för evigt. Det är en strukturell orsak till att
stocken bara kan växa. Becsis fria inträde är motstycket: där ger firman upp
när det inte längre lönar sig att söka.

### 4.5 Om Becsi som källa

Relevant för begreppen, och för papper 4:s placering i litteraturen — det han
härleder analytiskt räknar WORM fram numeriskt, med heterogenitet i två
dimensioner i stället för en. Men det är ett ogranskat preprint med starka
existensvillkor och ett stiliserat räknat exempel, så talen (78 procents
välfärdsgap) är interna för leksaksmodellen. Och hans modell är stationär utan
separationer: den beskriver fixpunkten vi vill nå, inte vägen dit.

### 4.5b Den exogena avgången fanns kvar (0085)

Genomgången efter 0084 visade att `handle_start_job` fortfarande schemalade
en `quit_job` normalfördelad kring sju år vid varje tillträde -- också
uppstartens, som sedan 0069 går genom samma funktion. 0079 tog bort den ur
`_init_events` och testade bara `_init_events`. 84 procent av
startbeståndet lämnade därför sina jobb utan orsak inom tio år, med topp
kring 1 300 per år vid år sju, in i en pool som aldrig vann ett urval.
Diagnoserna 4.1--4.4 ska läsas om efter att avgången är borta; det som står
kvar av divergensen efter 0085 är det som mekanismerna ska förklara.

Omskolningen (`start_education`) utlöstes enbart ur den exogena avgången
och har ingen utlösare nu. Den ska få en ur den torra sökningen, där
`propensity_start_education` redan växer, när frågan om nivå och inriktning
i utbildningen är avgjord.

Efter 0085 konvergerar modellen: vakansstocken toppar år två kring 850--900
och faller till ~630 vid år tio, arbetslösheten från ~2 000 till ~1 650, i
alla fem frön. Divergensen var den exogena avgången. Måtten i avsnitt 4.2
(100 procent av tillsättningarna till anställda) och i *Stegen* (byten per
år, vakansernas ålder) var dessutom felmätta i 0082--0085, se 0086:
restpoolens undanträngning är inte belagd, och byten per år är okänt tills
körningen efter 0086 finns.

### 4.5c Vakansernas ålder och vad v mäter (0087)

Rätt mätt är vakansåldern vid tillsättning median 80 dagar, p90 85:
fönstret 40 plus uppsägningstiden ~40. Nästan varje vakans får sin första
ansökan inom dagar. Varaktigheten är alltså inte söktid utan två
administrativa fördröjningar, och V/L = 5.6 procent följer ur dem. Därtill
räknar V positioner som är tillsatta men inte tillträdda (pending); SCB:s
vakansbegrepp gör det inte. En jämförelse med v = 2 procent kräver V utan
pending, som är ungefär hälften. Det är en rapporteringsfråga, inte en
mekanism.

### 4.5d Beslutet fattas vid erbjudandet (0092 diagnos, 0095 åtgärd)

Individkedjorna (0091) visade byten med NEGATIV lönevinst, upp till
-12 procent. Mönstret är detsamma varje gång: ansökan lämnas som arbetslös,
ett annat erbjudande kommer först, hon tillträder det -- och när det första
fönstret stängs tillträder hon ÄVEN det, till en lägre lön än den hon nu
har. `handle_close_vacancy` väljer vinnare bland buden och `handle_start_job`
kontrollerar bara att positionen finns kvar (`job_gone_before_start`); ingen
av dem jämför erbjudandet med hennes nuvarande situation. Buden är
utvärderade vid ansökningstillfället och binder henne i fyrtio dagar plus
uppsägningstid.

Det är precis den marginal Becsi (2026) gör till primitiv: att avslå ett
funnet alternativ ska vara ett val, inte en omöjlighet. 0095 ger henne
valet: arbetsgivaren går nedåt i q-ordning till den förste vars överskott
mot NUVARANDE läge är positivt, räknat med samma uttryck som sökningen
(`current_surplus`). Avslaget är gratis -- Becsis kostnader k (arbetsgivaren
avvisar en funnen kandidat) och m (arbetaren avvisar ett erbjudande) är en
egen mekanism och en egen fråga. Lönen omförhandlas inte vid erbjudandet;
det är ett modellval och gör avslagen försiktiga.

Måtten som säger hur stor kanalen är: `share_moves_wage_loss`,
`share_moves_applied_while_unemployed` och `share_moves_application_matched`.

Kedjorna visade också yrkeshopp långt utanför medianen -- u_R_occ 2.7, 2.0,
1.5 i enskilda övergångar, mot medianen 0.66. `u_R_occ_p90` och
`share_u_R_occ_above_1` rapporteras nu, eftersom en median inte säger något
om svansen och det är svansen som avgör om geometrin binder rörligheten.

### 4.6 Nivåfrågorna (uppdaterat efter 0098–0100)

u = u_min + V/L exakt, och efter 0098 är u 12,9 procent: u_min 8,8 och
V/L 4,1. Båda termerna var mekaniska, inte ekonomiska.

*u_min.* Konfigurationen säger 6,5 procent, men refyllnadstakten
`vacancy_fill_rate` 0,25 per månad mot δ = 0,1 per år lämnade ett stående
underskott på (δ/12)/(fill + δ/12) = 3,2 procent av jobbstocken, alltså 336
positioner som aldrig fanns. Det lades rakt på arbetslösheten. 0100 sätter
takten till 1,0 (underskott 0,8 procent) och u_min ska då landa kring 7,3.
Den fördröjning som verkligen hör hemma här — arbetsgivarens beslut att
ersätta en förlorad position — är inte modellerad och hör till arbetsgivaren
som agent.

*V/L.* Efter 0100 är u 10,8 = u_min 6,5 + V/L 4,3, och hela den kvarvarande
skillnaden mot referensens 7,5 ligger i vakansstocken. Varaktigheten är 117
dagar (Little) mot svenska 30–40, och vakansens ålder vid tillsättning är 80:
annonseringsfönstret 40, beslutet 10, uppsägningstiden 30. Skillnaden mellan
117 och 80 är de positioner ingen tar och som utlyses om.

Men jämförelsen var fel ställd. V räknar alla obesatta aktiva positioner,
också de UTLOVADE — någon har tackat ja, tillträdet är om en månad. SCB:s
vakans är en ledig befattning som rekryteringen ännu inte löst, och en
tillsatt befattning med tillträde om en månad är inte ledig. 0101 rapporterar
`v_open_pct` och `open_vacancy_days` vid sidan av; identiteten U = L − J + V
använder alla obesatta positioner och rörs inte. Fönstret på 40 dagar och
uppsägningstiden är modellval med egen empiri, och ska inte kalibreras mot en
felställd jämförelse.

---

## 5. Ordningen på det som återstår

**Mät först, ingen mekanikändring.** De tre måtten avgör vilken diagnos som
dominerar. Byten per år som andel av anställda och medianlönevinsten per byte,
ur `quit_job` med `to_job_id` sedan 0079: 30 procent per år med tjugo procents
vinst är κ, tio procent med fem procents vinst är Π-förankringen. Restpoolens
q-fördelning bland arbetslösa mot de anställda sökandes, per år. Och
vakansernas åldersfördelning — en växande svans säger att stocken består av
samma positioner, inte av flöde.

**Kalibrera κ.** `on_the_job_search_factor` mot 15–25 och
`switching_cost_share` mot 8–10 procent, tills andelen byten per år landar
kring tio procent som i svensk data. Ingen kod. Räcker det ensamt behövs inte
nästa två steg.

**Avvisningskostnad i urvalet.** Arbetsgivaren rangordnar på q minus värdet av
den tid positionen står tom om ingen anställs nu. En rad, en parameter, och en
verklig mekanism. Kontroll: `share_uncontested` och median q vid anställning
ska falla, och q-fördelningen bland arbetslösa sluta divergera från de
anställdas.

**Förankra Π i beståndet.** Ingångslönen blir Π·p^θ·ζ med ζ < 1 så att
beståndets median landar på Π efter klättringen. B-M ger ζ ur κ, så den är
härledd och inte anpassad. Görs **sist**: en ζ kalibrerad mot en okalibrerad
stege blir fel. Kontroll: `stock_share_above_pi` mot 0,50, stabilt över åren.

**Vakansavveckling.** Arbetsgivaren ger upp en position som inte gått att
fylla. Kräver en beslutsregel — värdet av att fortsätta söka mot värdet av att
lägga ned — inte bara en hazard. Hör till scenariomodellen och är
glesbygdsfrågans kärna: det är där arbetsgivare faktiskt slutar försöka.

### 5.1 Därefter

**Lokalt marknadstryck i förhandlingen.** θ endogent i kön: en vakans utan
sökande blir dyrare. Kön i överskottet gör redan motsvarande på söksidan.
Kräver att stegen och Π är kalibrerade.

**Job Zone, SUN-nyckel, mjuk spärr.** Nivån i utbildningsdimensionen.

**Utbildningen på de nya primitiverna.**

**m_ref(r_j)**, se 1.3. Ändrar inlärningstakten för alla jobb samtidigt och ska
inte blandas med annat.

**Överlappet via jobbet**, se 1.3.

**Bytespremien som mått.** Att den som byter arbetsgivare får bättre
löneutveckling än den som stannar är modellens egen förutsägelse — bytaren
omvärderas till formeln, stannaren släpar med sin revisionshistorik, och bara
den som tjänar på det byter eftersom reservationen är nuvarande lön. Den ska
läsas av, inte byggas in.

---

## 6. Läsanvisning för utfall

- `median_u_R` i rapporten är u_R_occ på CPS-urvalet. Figurer och skript ska
  mäta samma sak.
- `wage_ratio` är w/Π_o, mot **yrkets** lön. Mot jobbets försvinner η
  identiskt.
- `stock_share_above_pi` är definitionsvillkoret; flödets andel över Π är
  en annan storhet och ska ligga högre, eftersom den som just valts ut har
  högre passform än yrkets median.
- Spannet över frön är tröskeln. Det föll med en faktor tre när
  yrkesdragningen rättades (0053) och är nu 0,007 för u_R och 0,4
  procentenheter för u.
