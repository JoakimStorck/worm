# Inträdet: de unga på väg in (6b och 6c)

Plan, inte specifikation. Utarbetad 2026-09-19 efter spår C
(`stockarna.md`) och steg 4 och 6a (`utbildningsmodell.md`). Besluten står
sist; de fyra förslagen godtogs.

## Varför nu

**Utan inträde krymper arbetskraften.** Med demografin på gick den från
17 356 till 12 489 på nio år (O5-körningen): pensionsavgångarna ersätts inte.
Varje körning med demografi mäter därför en region som tömts, och prövningar
av arbetslöshet, pendling och vakanser görs i dag med demografin avstängd.

**Vakanserna väntar där de unga skulle ha arbetat.** Modellens längsta
rekryteringstid är i hotell och restaurang (121 dagar mot SCB:s 12), och
jobben står tomma för att de betalar under de erfarna arbetslösas anspråk
(`stockarna.md`, "Rekryteringstiden per bransch"). I TAB4359 är 15,1 procent
av de anställda 16–24 år butikspersonal, 8,6 procent i snabbmat och kök och
3,4 procent servitörer -- tre till fyra gånger deras andel bland alla.

## Vad som finns i modellen i dag

Befolkningen är hela pyramiden, 0–100 år (34 273 invånare i Ovansiljan). De
som ska komma in under en tioårskörning finns alltså redan: 4 860 barn under
15, och omkring 1 000 unga 16–29 utanför arbetskraften. Men ingen övergång
leder in: den som är utanför arbetskraften stannar där, och barnen blir äldre
utan att någonsin söka jobb.

Deltagandet i Ovansiljan (BAS, `labour_force_by_age`): 40 procent vid
16–19, 81 vid 20–24, 86 vid 25–29, 88–92 vid 30–54. Vid 16–19 är det till
stor del studerande med extrajobb (6c).

## Data

**TAB3731** (riket, ettårsklasser 15–29, BAS): studiedeltagande, nivå och
förvärvsarbete. Den bär både inträdesåldern och de studerandes arbete.

| ålder | studerar | i gymnasiet | i högskolan | studerande som förvärvsarbetar | ej studerande som förvärvsarbetar |
|---|---|---|---|---|---|
| 16 | 96 % | 92 % | 0 % | 11 % | 5 % |
| 17 | 95 % | 94 % | 0 % | 21 % | 9 % |
| 18 | 93 % | 91 % | 1 % | 36 % | 25 % |
| 19 | 38 % | 13 % | 13 % | 38 % | 67 % |
| 22 | 47 % | 0 % | 32 % | 44 % | 77 % |
| 25 | 31 % | 0 % | 19 % | 52 % | 81 % |
| 29 | 18 % | 0 % | 9 % | 59 % | 84 % |

Nivån bland dem som slutat studera: vid 19 har 83 procent treårigt
gymnasium; lång eftergymnasial utbildning (nivå 6) syns från 22 och når 32
procent vid 29. Förgymnasial nivå ligger kring 10 procent från 19.

**TAB6928** (per kommun, utbildningsflöden per år, 18–69 år): åldersinträden,
inflyttare, utflyttare, examinerade och vidareutbildade, per utbildningsnivå
och åldersklass. Ovansiljan 2023–2024: 413 fyller 18; bland 18–24 flyttar
359 ut och 231 in (netto −128), och bland 25–34 är flyttningarna nästan i
balans. Tabellen ger också 25–34-åringarnas nivåfördelning per kommun, alltså
det lager som blir kvar efter studieflyttningen.

**TAB655** (riket, nivå × inriktning per tioårsklass), rakingen P(yrke, nivå,
inriktning | ålder) (steg 4b) och **TAB6666** (per kommun, sysselsatta och
arbetslösa per nivå) finns redan.

## Modellen

### Livsloppet

Varje ung invånare går igenom samma led:

1. **Under 16:** åldras, inget annat.
2. **16 år:** får en **utbildningsplan** -- slutlig nivå och inriktning --
   och status `in_education`. Planen dras ur de unga vuxnas fördelning i
   hennes kommun (nedan).
3. **Studietiden:** till planens avslutningsålder. Förgymnasial nivå
   avslutas 16–18 (avhopp), gymnasial vid 19, kort eftergymnasial 21–23,
   lång eftergymnasial 22–26, forskarnivå omkring 30; spridningen tas ur
   TAB3731:s ettårsklasser.
4. **Inträdet:** utbildningens cirklar läggs (grundskolan; allmän
   utbildning i origo; annars på ett yrke draget ur P(yrke | nivå,
   inriktning) för 25–29 -- samma dragning som 6a-ii), och hon blir
   arbetslös och söker. Det första jobbet är ett utfall av matchningen.
5. **Aldrig in:** en andel går aldrig in i arbetskraften, så att deltagandet
   planar ut vid profilens nivå (86–90 procent), inte vid 100.

Planen avgör alltså både nivån och när hon kommer in. Deltagandet per ålder
blir ett **utfall** som prövas mot BAS-profilen, inte en indata.

### Planens fördelning per kommun

Dras ur 25–34-åringarnas nivåfördelning **i kommunen** (TAB6928), inte ur
rikets. Det är lagret efter studieflyttningen: den som flyttade för att
studera och inte kom tillbaka syns inte där. Utan flyttningar i modellen är
det rätt mål för dem som stannar. Inriktningen dras givet nivån ur TAB655.

### Startpopulationen, 16–29 år utanför arbetskraften

Delas enligt TAB3731 per ålder i studerande (med en plan, som i led 2–3)
och utanför arbetskraften (aldrig in, eller senare). De i arbetskraften har
redan fått utbildningen givet yrket (6a-ii).

### Anspråket vid första jobbet

Den som aldrig haft ett jobb har ingen senaste lön, och anspråkets
uppdatering hoppar i dag över henne (`_uppdatera_reservation` återvänder
när `w_last` saknas). Hon behöver ett uttryckligt startanspråk: en percentil
i sin relevansfördelning, och därifrån samma sänkning med arbetslöshetens
längd som alla andra.

### 6c: studerande med extrajobb

Byggs efter 6b (avgjort 2026-09-18, `utbildningsmodell.md`). En studerande
kan ha ett jobb: lågt anspråk, smal sökning (nära hemmet, låga krav), och
aldrig arbetslös -- utan jobb är hon studerande. Andelen som arbetar per
ålder ur TAB3731: 11 procent vid 16, 36 vid 18, 40–48 bland 19–24.

### Utanför: flyttningarna

Ovansiljan förlorar netto omkring 130 unga om året i 18–24 (TAB6928).
Utan flyttningar stannar alla i modellen, och ungdomskullarna blir större än
verklighetens. Planens fördelning ur kommunens 25–34-åringar ger dem ändå
rätt nivå; det är antalet som blir för stort. Flyttningarna hör till
omgivningen (`omgivning.md`, "Flyttningar") och byggs som eget steg.

## Byggordning

1. ~~**6b-1 Data.**~~ Gjort: `population_study_education` (TAB3731, 2024,
   barnens ålder summerad) och `education_flows_municipality` (TAB6928,
   2023–2024, nivågrupper 02–05, 09 och alla, åldersklasser, kommunerna och
   riket). Befolkningen år 2 är år 1 plus nettot i alla celler; komponenterna
   summerar inte till nettot (dödsfall och ändrade uppgifter saknas) och
   prövas inte. Gymnasial nivå är en grupp i TAB6928; uppdelningen på två
   och tre år tas ur TAB655.
2. **6b-2 Planen och inträdet.** Utbildningsplanen vid 16, studietiden,
   inträdeshändelsen med utbildningens cirklar, andelen som aldrig går in,
   och startanspråket.
3. **6b-3 Startpopulationen 16–29** utanför arbetskraften: studerande med
   plan eller utanför.
4. **6b-4 Prövning** med demografin på, tio år.
5. **6c** Studerande med extrajobb.
6. **Flyttningar** genom omgivningen, per ålder och utbildning ur TAB6928.

## Prövning

- Arbetskraftens storlek över tio år, mot vad pyramidens åldrande och
  deltagandeprofilen ger.
- Deltagandet per ålder 16–34 mot BAS-profilen.
- Andelen förvärvsarbetande bland dem som slutat studera, per ålder, mot
  TAB3731 (67 procent vid 19, 84 vid 29).
- De ungas yrken, 16–24 och 25–29, mot TAB4359 (validering, inte indata).
- 25–34-åringarnas nivåer per kommun mot TAB6928.
- Rekryteringstiden i hotell och restaurang och korrelationen per bransch mot
  TAB4307 (väntas flytta mest med 6c).

## Beslut (dialog 2026-09-19: alla fyra förslag godtagna)

1. **Flyttningarna nu eller senare.** Förslag: senare, som eget steg efter
   6c; kullarna blir för stora under tiden, och det står i prövningen.
2. **Planens fördelning ur kommunens 25–34-åringar** (TAB6928) i stället för
   rikets. Förslag: ja.
3. **Startanspråket vid första jobbet**: vilken percentil i
   relevansfördelningen. Förslag: medianen, och sänkningen därifrån som för
   alla; ingångslönens rabatt får då komma ur att de unga har låg
   konkurrenskraft och tar det som bjuds. Kalibreras mot andelen
   förvärvsarbetande bland dem som slutat studera (TAB3731).
4. **Andelen som aldrig går in**: ur deltagandeprofilens platå (86–90
   procent), eller ur TAB3731:s icke förvärvsarbetande icke studerande (16
   procent vid 29). Förslag: profilen, som redan bär utträdet, så att in
   och ut räknas ur samma kurva.
