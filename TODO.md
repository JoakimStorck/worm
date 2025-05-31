# TODO – WORM Project

## Project Goals (summary)

* Build a synthetic, agent-based labor market model with individuals, occupations, and regions
* Integrate SCB and O\*NET data for both real and synthetic geographies
* Enable flexible modeling at multiple geographical scales (nation, region, municipality, zone)
* Store all data and results in a local SQLite database for reproducibility
* Provide tools for matching, commuting, and analysis of labor market dynamics
* Support scenario testing and stepwise demos for each core function

---

## **Arbetspaket, nivåer, milstolpar och demo**

---

## **AP1. Database & Data Collection**

### **a) Grund**

* [ ] Skapa och dokumentera SQLite-struktur (kommuner, DeSO, tätorter, småorter, verksamhetsområden)
* [ ] Importera SCB\:s tabeller för befolkning, arbetsplatser, utbildning, yta
* [ ] Lagra och länka polygoner/geometrier för alla geografiska nivåer
* [ ] **Demo:** Läs in och visa antal kommuner, tätorter, population mm från SQLite

### **b) Utbyggnad**

* [ ] Lägg till arbetsmarknadsdata per SNI på kommun och DeSO
* [ ] Lagra O\*NET–SCB transformationer och cluster-data
* [ ] Länka samtliga tabeller med relevanta nycklar
* [ ] **Demo:** Samkör befolknings- och arbetsmarknadsdata, visa SQL-join/exempel

### **c) Full synk/metadata**

* [ ] Fullständig datavalidering, constraint-checks och automatiska uppdateringsscripts
* [ ] Skapa system för dataversionering och dokumentera tabellstruktur i kod
* [ ] **Demo:** Automatisk integritetskontroll och visualisering av tabellstruktur

---

## **AP2. Geography Modeling and Structure**

### **a) Grund**

* [ ] Ersätt rutnät med verklig geografi på alla nivåer: kommun, DeSO, tätort, småort, verksamhetsområde
* [ ] Definiera klasser/SQL-schema för samtliga entiteter (med polygon/centroid)
* [ ] Läs in och visualisera polygoner från SCB för Falun
* [ ] **Demo:** Plot overlay av alla geografier i Falun (kommun, DeSO, urban area, workplace area)

### **b) Utbyggnad**

* [ ] Implementera Place-klass: unikt id, (x, y), länkar till överordnad geografi
* [ ] Slumpa/placera punkter för bostad/jobb inom polygon via point-in-polygon
* [ ] Koppla jobb till verksamhetsområden efter SNI om möjligt
* [ ] **Demo:** Visualisera samtliga Place-objekt (punkter) för en kommun och deras kopplingar

### **c) Skala & flexibel struktur**

* [ ] Möjliggör variabel zonindelning (1–N per kommun)
* [ ] Skapa möjligheter att kombinera och dela regioner dynamiskt
* [ ] **Demo:** Visualisera och spara en användardefinierad region (flera kommuner) och dess platser

---

## **AP3. Generation of Typmunicipalities and Regions**

### **a) Grund**

* [ ] Läs YAML-profiler för typkommun/region
* [ ] Skapa semantiska profiler (storstad, landsbygd etc)
* [ ] **Demo:** Ladda en typkommun från YAML och visualisera grunddata/geodata

### **b) Utbyggnad**

* [ ] Bygg KNN-modell för att generera syntetiska kommunprofiler
* [ ] **Demo:** Jämför en syntetisk profil mot närmaste riktiga kommuner (KNN-visning)
* [ ] Skapa pipeline för att slumpa kombinerade regioner utifrån profil

### **c) Hög realism**

* [ ] Kombinera syntetisk zonindelning och profil med realistisk allokering
* [ ] **Demo:** Skapa och visualisera en syntetisk region genererad från YAML + KNN

---

## **AP4. Allocation of Workplaces and Residences**

### **a) Grund**

* [ ] Fördela arbetsplatser/bostäder slumpmässigt i varje zon (Dirichlet/random)
* [ ] **Demo:** Visa karta med slumpfördelade jobb/bostäder för Falun

### **b) Utbyggnad**

* [ ] Implementera regelbaserad allokering (viktning för CBD, industri, bostad etc)
* [ ] Tilldela arbetsplatser till verksamhetsområden efter SNI eller logik
* [ ] **Demo:** Visa skillnad mellan random och regelbaserad fördelning

### **c) KNN-baserad allokering**

* [ ] Samla statistik och skapa KNN-baserad metod för allokering till zoner/platser
* [ ] **Demo:** Visa och jämför KNN-allokering mot riktiga data eller profil

---

## **AP5. Spatial Query & Efficient Search**

### **a) Grund**

* [ ] Bygg spatialt index för alla Place-objekt (bostad/jobb) med GeoPandas/KDTree
* [ ] **Demo:** Visa sökning av alla jobb inom 10 km från en vald plats (punkter på karta)

### **b) Typbaserad sökning**

* [ ] Möjliggör queries för enbart jobb, bostäder eller båda
* [ ] **Demo:** Visa båda sökningar och pendlingsflöden för valfri region

### **c) Avancerad sök**

* [ ] Stöd för närmaste-n-grannar, dynamiska filter, tidsberoende sökning
* [ ] **Demo:** Visualisera pendlingsflöden över tid i animation eller stegvis

---

## **AP6. Matchning & Statisk Simulering**

### **a) Grund**

* [ ] Implementera grundläggande matching mellan arbetssökande och jobb på samma plats (statisk snapshot)
* [ ] **Demo:** Visa matchningsresultat för Falun (antal matchade/omatchade per plats)
* [ ] Lägg till egenskapsbaserad matchning (skills, occupation, preferenser – men statiskt)
* [ ] **Demo:** Visa egenskapsbaserad matchning för Falun, jämför olika algoritmer

### **b) Spatial & regional matching**

* [ ] Tillåt matchning över kommungränser (med pendlingsavstånd/regel)
* [ ] Analysera arbetslöshet/matchning över regioner
* [ ] **Demo:** Visualisera flöden av arbetspendling och regionbaserad matchning

### **c) Statisk scenarioanalys**

* [ ] Skapa snapshot-scenarier: olika arbetsmarknadsstruktur, policy, eller demografi
* [ ] **Demo:** Jämför flera statiska scenarier (ex. arbetslöshet före/efter policy eller chock)

---

## **AP7. Dynamisk Simulering (Event-driven)**

### **a) Infrastruktur & grundläggande events**

* [ ] Implementera enkel event loop/simulationsmotor (SimPy eller egen)
* [ ] Skapa loggning av alla events till fil/konsol (eventtyp, tid, agent/företag, plats)
* [ ] Definiera och implementera *individ-event*:

  * [ ] Slutar på jobb
  * [ ] Söker jobb
  * [ ] Börjar på jobb
  * [ ] Blir arbetslös
* [ ] **Demo:** Kör en jämviktssimulering (statistisk steady state) – visa logg av individbaserade events

### **b) Företagsevent och enkel chock**

* [ ] Lägg till *företagsevent*:

  * [ ] Annonserar nytt jobb
  * [ ] Säger upp personal
  * [ ] Lägger ned verksamhet
  * [ ] Startar nytt företag
* [ ] Skapa och logga events som sker på företagsnivå
* [ ] Simulera en enkel chock (ex. nedläggning av företag)
* [ ] **Demo:** Visa tidsserier för arbetslöshet och matchning före/efter chock, samt loggade events

### **c) Mer komplexa och dynamiska events**

* [ ] Lägg till individ-event:

  * [ ] Flyttar till annan kommun
  * [ ] Byter yrke/kompetens
  * [ ] Går utbildning/kurs
* [ ] Lägg till företag-event:

  * [ ] Expanderar till nya verksamhetsområden
  * [ ] Byter inriktning (ny SNI-kod)
  * [ ] Tar emot subvention/policyintervention
* [ ] Utveckla loggningsfunktioner för sammanfattande statistik (t.ex. arbetskraftsbalans, pendlingsstatistik, etc.)
* [ ] **Demo:** Simulera komplex scenario – analysera och visa sekvenser av events, gärna med visualisering av kedjor/flöden (t.ex. arbetslös agent → utbildning → ny anställning)

### **d) Policy och adaptivt beteende**

* [ ] Implementera möjligheter till policyintervention (utbildning, subvention, matchningshjälp etc)
* [ ] Modellera agenter/företag med adaptiv strategi (t.ex. lärande, preferensskifte)
* [ ] Lägg till händelser för policy-chock (ex. ny lag, global kris)
* [ ] **Demo:** Jämför scenario med/utan policy; visa logg och tidsserie av effekter (t.ex. snabbare återgång till sysselsättning)

---

## **AP8. Commuting & Flows**

### **a) Grund**

* [ ] Modellera pendlingsmöjlighet: tilldela individer jobb på annan plats inom avstånd (enkel radie-regel)
* [ ] **Demo:** Visa en enkel pendlingsmatris mellan två kommuner/regioner

### **b) Utbyggnad**

* [ ] Implementera realistisk commuting-logik (avstånd, region, tillgänglighet, preferenser)
* [ ] Skapa och visa pendlingsflöden på karta/nätverk
* [ ] **Demo:** Visualisera pendlingsflöden för valfritt scenario eller förändring

### **c) Avancerad flödesanalys**

* [ ] Modellera och analysera flöden över tid (animations, stepwise)
* [ ] Skapa mått för pendlingsbalans, segregationsindex, mm
* [ ] **Demo:** Visualisera och exportera dynamiska pendlingsflöden i tidsserie/film eller graf

---

## **AP9. Visualization & GUI**

### **a) Grund**

* [ ] Skapa visualiseringar: karta med platser, matchning, pendlingsflöden (matplotlib/plotly)
* [ ] **Demo:** Visa karta och enkel nätverksgraf för en kommun

### **b) Flexibel visualisering**

* [ ] Implementera occupation space polar plots för valda zoner/områden
* [ ] Utveckla plattform-oberoende plot-interface: stöd för karta/nätverk/polar vy
* [ ] **Demo:** Byt vy mellan karta, nätverk och occupation polar plot för valfritt urval

### **c) Dashboard och export**

* [ ] Bygg GUI/web-app med interaktiv vyväxling (Dash/Streamlit/Panel)
* [ ] Exportera resultat och bilder till PNG, SVG, GeoJSON, CSV
* [ ] **Demo:** Byt vy “live”, spara och ladda urval/resultat från GUI

---

**Tips:**

* Markera \[x] när något är klart.
* Lägg gärna till / ändra på delmål eller demos under utveckling!
* Vid behov: komplettera med ytterligare “nivåer” (d, e, ...).

---

**Senast uppdaterad: 2025-05-31**

