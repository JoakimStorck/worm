# TODO – WORM Project

## Project Goals (summary)

* Build a synthetic, agent-based labor market model with individuals, occupations, and regions
* Integrate SCB and O\*NET data for both real and synthetic geographies
* Enable flexible modeling at multiple geographical scales (nation, region, municipality, zone)
* Store all data and results in a local SQLite database for reproducibility
* Provide tools for matching, commuting, and analysis of labor market dynamics
* Support scenario testing and stepwise demos for each core function
* All modellering och simulering utformas så att 1e5–1e6 agenter kan hanteras effektivt med pandas/numpy och event queue.
* Händelsedriven simulering bygger på ID-baserade länkar och batchbearbetning.


---

## **Arbetspaket, nivåer, milstolpar och demo**

---

## **AP1. Database & Data Collection**

Här kommer ett färdigt block anpassat för din TODO-struktur, med checkboxar. Du kan enkelt klistra in det – och jag har bockat av det som, utifrån tidigare samtal och din tidigare TODO, verkar vara klart. Du kan såklart justera det vidare efter din faktiska status!

---

## **AP1. Database & Data Collection**

### **a) Grund**

* [x] Skapa och dokumentera SQLite-struktur (kommuner, DeSO, tätorter, småorter, verksamhetsområden)
* [x] Importera SCB\:s tabeller för befolkning, arbetsplatser, utbildning, yta
* [x] Lagra och länka polygoner/geometrier för alla geografiska nivåer
* [x] Lägg till arbetsmarknadsdata per SNI på kommun och DeSO
* [x] Lagra O\*NET–SCB transformationer och cluster-data
* [x] Länka samtliga tabeller med relevanta nycklar
* [x] **Demo:** Läs in och visa antal kommuner, tätorter, population mm från SQLite; samkör befolknings- och arbetsmarknadsdata, visa SQL-join/exempel

---

### **b) Utbyggnad**

* [ ] Lägg till indexering av viktiga nycklar och tabeller för prestanda
* [ ] Skapa vyer och aggregerade tabeller för typiska analyser (t.ex. arbetskraft per region/yrke/utbildning/SNI)
* [ ] Implementera flexibla queries/parametriserade urval (kommun, DeSO, yrke etc.)
* [ ] Integrera fler kodlistor/mapping-tabeller (ex. SSYK/SNI/O\*NET)
* [ ] Förbered datastruktur för agentbaserade simuleringar (ex. agents, initialstatus, seeds)
* [ ] Koppla till externa datakällor för löpande/periodiska uppdateringar
* [ ] **Demo:** Visa exempel på typisk analys (t.ex. arbetskraft per utbildningsnivå i region X, eller matchande jobb för viss kompetensprofil)

---

### **c) Full synk/metadata och kvalitet**

* [ ] Fullständig datavalidering (test av constraints, integritetsregler, foreign keys etc.)
* [ ] Automatiska scripts för uppdatering och kontroll av databasens innehåll
* [ ] Skapa/uppdatera system för dataversionering (spårbarhet över tid)
* [ ] Dokumentera all tabellstruktur och förändringar i kod/metadatafiler
* [ ] **Demo:** Visa automatisk integritetskontroll och visualisering av tabellstruktur samt exempel på versionshistorik eller datalogg

---

## **AP2. Geography Modeling and Structure**

### **a) Grund**

* [x] Ersätt rutnät med verklig geografi på alla nivåer: kommun, DeSO, tätort, småort, verksamhetsområde
* [x] Definiera klasser/SQL-schema för samtliga entiteter (med polygon/centroid)
* [x] Läs in och visualisera polygoner från SCB för Falun
* [x] **Demo:** Plot overlay av alla geografier i Falun (kommun, DeSO, urban area, workplace area)

### **b) Utbyggnad**

* [ ] Implementera Place-klass: unikt id, (x, y), länkar till överordnad geografi
* [ ] Optimera platser, *Place*, för effektiv simulering genom vektorisering och ID-länkning.
* [ ] Slumpa/placera punkter för bostad/jobb inom polygon via point-in-polygon
* [ ] Koppla jobb till verksamhetsområden efter SNI om möjligt
* [ ] **Demo:** Visualisera samtliga Place-objekt (punkter) för en kommun och deras kopplingar

### **c) Skala & flexibel struktur**

* [ ] Möjliggör variabel zonindelning (1–N per kommun)
* [ ] Skapa möjligheter att kombinera och dela regioner dynamiskt
* [ ] **Demo:** Visualisera och spara en användardefinierad region (flera kommuner) och dess platser

---

Absolut! Här är en **uppdaterad och mer detaljerad TODO för AP3a – Visualisering** med konkreta delmoment och demos, utifrån var du står nu:

---


---

## **AP3. Visualization & GUI**

### **a) Grund – Steg-för-steg**

1. **Slumpa och placera platser inom kommunpolygon**

   * [x] Slumpa och placera *Residence* och *Workplace* inom vald kommuns polygon (ex: Falun) med hjälp av GeoPandas/Shapely.
   * [x] Visualisera dessa punkter ovanpå kommunpolygonen (matplotlib).
   * [x] Demo: *Plotta kommunpolygon + bostäder + arbetsplatser.*

2. **Generera och koppla agenter och jobb**

   * [x] Skapa *Workers* kopplade till Residence.
   * [x] Skapa *Jobs* kopplade till Workplace.
   * [x] Matcha (exempelvis 1:1) Workers till Jobs, koppla genom ID.
   * [x] Demo: *Plotta karta med pendlingslinjer (bostad → arbetsplats).*

3. **Utveckla fler lager och kartlager**

   * [ ] Lägg till andra lager: urban\_areas, business\_zones, tätorter osv.
   * [ ] Visualisera overlay av flera geografiska lager tillsammans med punkter och linjer.
   * [ ] Demo: *Plotta flera lager samtidigt med tydliga färger och labels.*

4. **Utbyggnad och interaktivitet**

   * [ ] Lägg till interaktivitet: filtrering på agenttyp, hover med info, färgkoder för olika occupation clusters.
   * [ ] Skapa wrapper-funktion så att hela kedjan går att återanvända för andra kommuner/scenarier.

5. **Analys och statistik**

   * [ ] Räkna och visualisera statistik: antal pendlare per arbetsplats, arbetslöshet, geografisk klustring m.m.
   * [ ] Demo: *Visa enklare diagram/kartor med summeringar.*

### **b) Flexibel visualisering**

* [ ] Implementera occupation space polar plots för valda zoner/områden
* [ ] Utveckla plattform-oberoende plot-interface: stöd för karta/nätverk/polar vy
* [ ] **Demo:** Byt vy mellan karta, nätverk och occupation polar plot för valfritt urval

### **c) Dashboard och export**

* [ ] Bygg GUI/web-app med interaktiv vyväxling (Dash/Streamlit/Panel)
* [ ] Exportera resultat och bilder till PNG, SVG, GeoJSON, CSV
* [ ] **Demo:** Byt vy “live”, spara och ladda urval/resultat från GUI

---

## **AP4. Generation of Typmunicipalities and Regions**

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

## **AP5. Allocation of Workplaces and Residences**

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

## **AP6. Spatial Query & Efficient Search**

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

## **AP7. Matchning & Statisk Simulering**

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

## **AP8. Dynamisk Simulering (Event-driven)**

### **a) Infrastruktur & grundläggande events**

* [ ] Implementera enkel event loop/simulationsmotor (SimPy eller egen)
* [ ] Alla agent- och företagstillstånd hanteras primärt i DataFrame/tabell
* [ ] Agentobjekt skapas endast “on demand” för event. 
* [ ] Event queue är ID-baserad och minimerar objektpersistens i minnet.
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

## **AP9. Commuting & Flows**

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

## **AP10. Simulation Infrastructure & Scalability**

### **a) Datamodell och agenthantering**
- [ ] Utforma agent-tillstånd för att kunna lagras i DataFrame/tabell (alla agenter har unik ID, tillstånd i kolumner)
- [ ] Designa Place-tabell och indexering för snabb access
- [ ] Säkerställ att alla relationer mellan agenter, företag, platser och event är ID-baserade (inte direkta objektlänkar)

### **b) Händelsehantering**
- [ ] Implementera event queue som heap/priority queue
- [ ] Definiera datastruktur för event: (tid, agent_id/org_id, eventtyp, metadata)
- [ ] Benchmarka exekveringstid för 1e4, 1e5, 1e6 events i testmiljö

### **c) Prestanda och minne**
- [ ] Testa minnesfotavtryck och bearbetningstid för 1e5 och 1e6 agenter med numpy/pandas
- [ ] Definiera och dokumentera checkpoints och lagring (Parquet/HDF5)
- [ ] Lägg till stöd för batchvis eller partiell laddning vid riktigt stora populationer

### **d) Parallellisering och distribuerad körning**
- [ ] Förbered kodbasen för möjlig delning av agenter mellan flera trådar/processer
- [ ] Utforska möjligheter till enklare parallellsimulering på batch-nivå (t.ex. per kommun)
- [ ] Dokumentera vilka delar som kan optimeras vidare för multiprocess/stor skala

### **e) Skalbarhet: Demo och stresstest**
- [ ] **Demo:** Skapa och exekvera simulering med 100 000 agenter, logga tid/minnesanvändning
- [ ] **Demo:** Visa exempelflöde för större simulering (t.ex. alla individer i tre kommuner)

---


**Tips:**

* Markera \[x] när något är klart.
* Lägg gärna till / ändra på delmål eller demos under utveckling!
* Vid behov: komplettera med ytterligare “nivåer” (d, e, ...).

---

**Senast uppdaterad: 2025-06-02**

