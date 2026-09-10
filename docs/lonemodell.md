# Lönebildning och kompetens i WORM

Status per patch 0078. Dokumentet beskriver hur modellen **fungerar** i
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

## 4. Öppna nivåfrågor

- **u 14 procent mot 7,5 och vakanstid 59 dagar mot 30–40.** Samma tal två
  gånger: u = u_min + V/L exakt. u_min ≈ 6 procent är strukturellt; resten
  är vakansstocken.
- **Konvergens.** Tioårskörningen visade divergens före 0078. Ska köras om.
- **Femårshorisonten.** Övergångarna växte år för år; huruvida modellen når
  jämvikt på fem år avgörs av omkörningen.

---

## 5. Läsanvisning för utfall

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
