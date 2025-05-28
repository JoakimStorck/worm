# TODO – WORM-projektet

## Grundläggande mål
- [x] Skapa en arbetsmarknadsmodell med individer, yrken och regioner
- [x] Använda O*NET och SCB:s statistik
- [x] Implementera grundläggande datainsamling från SCB:s API

## Datainsamling och lagring
- [x] Hämta data om antal arbetsställen och anställda per SNI-kod och kommun (2020)
- [ ] Demo: Läs in och visa antal kommuner och variabler från SCB-data
- [ ] Hämta kompletterande data om demografi, utbildningsnivå och kommunstorlek (SCB)
- [ ] Demo: Läs in och visa befolkning, areal och utbildningsnivå per kommun
- [x] Använd SQLite som databas för lokal lagring
- [ ] Bygg databasstruktur för att lagra SCB-data, O*NET-transformationer och metainformation
- [ ] Demo: Spara och ladda data till/från SQLite – visa innehållet som DataFrame
- [ ] Spara transformerade O*NET-data till SQLite
- [ ] Länka SCB:s data till kommungruppsindelning (SCB:s kommuntyp)

## Modellering av geografi och struktur
- [x] Definiera YAML-baserad struktur för att beskriva kommuner, tätorter, småorter och regioner
- [x] Skapa motsvarande Python-klasser: Land, Region, Kommun, Zon
- [ ] Demo: Ladda YAML med en kommun och visa dess struktur (exempel: Falun)
- [ ] Implementera inläsning och utskrift till/från YAML
- [ ] Demo: Skapa och spara en region som kombinerar flera kommuner
- [ ] Möjliggör modellering på flera geografiska nivåer (ex: nation, region, kommun, tätort)
- [ ] Implementera flexibel granularitet – tillåt detaljerad eller övergripande modell

## Generering av typkommuner och regioner
- [ ] Demo: Ladda YAML med typkommun och hämta dess nyckelattribut
- [ ] Träna KNN-modell baserat på kommundata för att generera nya, syntetiska kommuner
- [ ] Demo: Kör KNN och visa de närmaste kommunerna till en given profil
- [ ] Definiera typkommuner (ex: ”industrikommun i inlandet, 30 000 inv.”)
- [ ] Demo: Generera syntetisk kommunprofil via KNN från YAML-specifikation
- [ ] Skapa semantiska profiler i YAML för olika typer av kommuner
- [ ] Generera regioner genom att kombinera flera syntetiska kommuner

## Matchning och simulering
- [ ] Modellera matchning mellan arbetare och yrken baserat på O*NET-positioner
- [ ] Demo: Simulera en enkel arbetsmarknadsmatchning i en kommun
- [ ] Implementera funktion för att simulera pendlingsmönster mellan kommuner
- [ ] Demo: Visa pendlingsflöden mellan två kommuner/regioner
- [ ] Tillåt överlapp mellan arbetskraft och bostadsort (pendling)

## Visualisering och analys
- [ ] Demo: Visualisera kommunfördelning och arbetsmarknadsstruktur med matplotlib/seaborn
- [ ] Skapa verktyg för att visualisera simulerade arbetsmarknader och pendlingsflöden
- [ ] Demo: Exportera data till GeoJSON/CSV och visa exempel på extern analys
- [ ] Utveckla metoder för att mäta entropi, klustring och matchningskvalitet i simuleringar

---

Senast uppdaterad: 2025-05-28
