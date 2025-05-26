# TODO – WORM (Worker-Occupation-Region Model)

## Översikt
Denna TODO innehåller planerade utvecklingssteg för modellens nästa fas, särskilt fokus på att skala upp till simulerade lokala arbetsmarknader med geografi, arbetsgivare och arbetstagare. Syftet är att strukturera och stegvis bygga ut modellen utan att behöva skriva om grunden.

---

## 1. Grundläggande funktioner (pågående / klara)
- [x] Transformerad O*NET-data till occupation space (PCA)
- [x] Klustring av yrken
- [x] Visualisering av occupation space (polär form, matplotlib)
- [x] Automatisk klusternamn baserat på representativa yrken
- [x] Smidig caching av transformerad data med dynamiskt filnamn
- [x] Separat funktion för att välja representativa yrken
- [x] Flexibel filhantering via `PROJECT_ROOT`

---

## 2. Modulär och skalbar design
- [x] Separata moduler: `occupational_profiles.py`, `occupational.py`
- [x] Visualisering av full occupation space med alla yrken
- [ ] Skapa undermappar: `worm/statistics`, `worm/geography`, `worm/employers`, `worm/workers`, `worm/matching`
- [ ] MatchEngine-klass med utbytbar strategi (brute force / index / parallel)
- [ ] Projektstruktur som stödjer simuleringar i olika skalor

---

## 3. Data och statistik
- [x] Hämtning av SCB-data för antal anställda och arbetsställen per kommun
- [x] Funktion för att omvandla SCB:s PX-API-svar till pandas DataFrame
- [ ] Koppling mellan SNI-koder och O*NET-yrken / kluster
- [ ] Modell för företagsstorlek och typ per region

---

## 4. Simulerade arbetsmarknader
- [ ] Skapa arbetsgivarpopulationer baserat på statistik
- [ ] Skapa arbetstagarpopulationer med slumpad kompetensprofil inom kluster
- [ ] Tilldela jobb till arbetsgivare, med variation inom samma arbetsplats
- [ ] Implementera geografiska positioner och distansfunktioner

---

## 5. Matchningslogik
- [x] Matchning baserat på överlappning i occupation space
- [ ] Lägg till geografiskt avstånd som tröskel eller vikt
- [ ] Protokoll/logg för varje matchningsomgång

---

## 6. Visualisering & analys
- [x] Visualisering av occupation space med klusternamn och polar layout
- [x] Parameterstyrd legend- och etikettplacering
- [ ] Visualisering av matchningsresultat
- [ ] Dynamisk och interaktiv plot med etiketter (ex. plotly)

---

## 7. Övrigt
- [x] README.md med instruktioner
- [x] TODO.md med roadmap och arbetsstruktur
- [ ] Tydliggör projektstruktur, beroenden, och exekvering i README
- [ ] Versionering av större modellsteg (mapp eller commit-konventioner)

---

## 8. Skalningsstrategi

**Fyra steg för kontrollerad uppskalning av modellen:**

1. **Miniatyrmarknad (syntetisk)**
   - 50 arbetsgivare och 500 arbetstagare
   - Placerade på ett syntetiskt rutnät
   - Syfte: testa logik, visualisering, identifiera flaskhalsar

2. **Småstad (semi-realistisk)**
   - Baserad på verkliga data från t.ex. Falun
   - 1000–2000 arbetsgivare och 10 000–20 000 arbetstagare
   - Placerade på förenklad geografisk yta
   - Syfte: validering mot känd arbetsmarknad

3. **Mellanstor region (realistisk)**
   - Ex: Dalarna eller Mellansverige
   - 10 000–50 000 arbetsgivare och >100 000 arbetstagare
   - Koppling till transportsystem, kommungränser etc.

4. **Nationell modell (ambitiös)**
   - Alla kommuner, full SCB-statistik, koppling till O*NET och SSYK
   - Parallellkörning eller molnbaserad infrastruktur
   - Syfte: analys av nationella policyfrågor och framtidsscenarier

---

## Externa datakällor

- SCB:s statistikdatabas (MI0815A): antal anställda + arbetsställen per kommun/SNI
- SSYK–SNI–O*NET-mappning (kräver metodutveckling)
- Befolkningsstatistik och arbetsmarknadsstatus per kommun (för arbetstagarmodell)

---

## Att diskutera
- Dokumentation av antaganden (förutsättningar i modellen)
- När och hur dynamik ska införas (arbetslöshet, rörlighet)
- Policyimplikationer och tänkbara användningsområden
