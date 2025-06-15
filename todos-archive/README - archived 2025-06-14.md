Här är en **analys och förslag på uppdatering** av din README.md, så den bättre speglar projektets **faktiska nuläge, nya struktur och dashboard-/replay-orientering**.
Jag utgår från den senaste TODO\:n och vad som verkligen är byggt eller pågår, samtidigt som dokumentationen fortfarande är inbjudande för nya användare och tydlig för kollegor.

---

## **1. Huvudförändringar att införa**

* Lyft fram att WORM nu bygger på **eventdriven simulering och replay** där all analys/visualisering kan återskapas från eventlogg.
* Tydliggör att ett centralt “dashboard”-gränssnitt nu är den huvudsakliga plattformen för analys och visuell interaktion (och vad som ingår där).
* Skilj tydligare mellan det gamla batchscript-/demo-flödet och det nya replay- och GUI-flödet.
* Lägg till ett avsnitt “Hur reproducera en simulering/run och utforska resultat” – med fokus på eventlogg och scenariohantering.
* Fokusera på vad användaren kan göra “end-to-end” i dag, och vilka stora block som kommer/saknas (t.ex. interaktiv replay och resultatexport).

---

## **2. Förslag till ny/uppdaterad README.md (med utgångspunkt från originalet)**

---

# WORM – Worker-Occupation-Region Model

WORM är en öppen, modulär Python-plattform för **agentbaserad simulering och analys av arbetsmarknader, pendling och regionala system**. Plattformen integrerar statistik, geografi och händelsedriven simulering för att stödja forskning och beslutsfattande på kommunal, regional och nationell nivå.

---

## 🌟 Vision

Att tillhandahålla en transparent, skalbar och återspelningsbar simuleringsmiljö för att studera svensk arbetsmarknad, kompetensdynamik och pendlingsmönster – med stöd för både forskningsmässig reproducerbarhet och interaktiv utforskning.

---

## 🚦 Huvudflöde och “dashboard-first”-design

WORM är nu organiserat för att **allt ska kunna simuleras, återspelas och analyseras i en central dashboard**:

* **Kör nya scenarier** (t.ex. Falun-baseline, egna YAML-filer) – simulera hela arbetsmarknaden och generera eventlogg/resultatfiler.
* **Välj och ladda tidigare simuleringar** (“runs”) – replay eventloggen för att återskapa och utforska valfritt tillstånd.
* **Utforska och analysera resultatet interaktivt**:

  * Occupation space, karta, statistik, fördelningsdiagram, eventtidslinje och filtrering – allt kopplat till aktuell replayad state.
* **Exportera statistik, bilder och urvalsdata** från valfritt steg i simuleringen.
* All kod, filstruktur och gränssnitt är byggt för att hantera även stora simuleringskörningar (>100 000 agenter).

---

## ⚡ Skalbarhet & prestandamål

Projektet är utformat för att hantera **100 000–1 000 000 agenter och >1 miljon events** på vanlig workstation/server.
Se [TODO.md](TODO.md) för detaljer kring minnesoptimering, batchning, replay-prestanda och framtida multiprocess-stöd.

---

## 📐 Scope & funktioner

* **Händelsedriven simulering med replay:**
  Allt från individers arbetsmarknadsstatus till pendlingsflöden återges och analyseras från eventlogg.
* **Dashboardgränssnitt:**
  Integrerar occupation space, karta, filterpanel, statistik, diagram och replay-tidslinje i ett interaktivt användarflöde.
* **Scenariohantering:**
  YAML-baserad modellering av kommuner, regioner, arbetsgivare och befolkning. Multi-kommun- och segmentstöd.
* **Dataimport och syntetisering:**
  SCB-mikrodata och O\*NET kopplas till syntetiska befolknings- och arbetsmarknadsmodeller.
* **Reproducerbarhet:**
  Varje simulering sparas med komplett eventlogg, metadata och snapshot, så resultat kan återskapas och valideras i efterhand.
* **Visualisering & export:**
  All analys, visualisering och statistik bygger på replayad state; exportmöjligheter finns för alla väsentliga data och bilder.
* **Öppen kod, dokumentation och test:**
  Tydlig API-dokumentation, demo-scripts och testsvit för kvalitet och vidareutveckling.

---

## 📦 Project Structure

*(Behåll gärna originalstrukturen – men komplettera gärna:)*

* `core/` – modulär kod (databas, geografi, simulering, visualisering)
* `data/` – SCB- och O\*NET-data, YAML, SQLite
* `results/` – alla simuleringar (“runs”) med full eventlogg och metadata
* `scripts/` – demo- och hjälpskript för snabb test/körning
* `dashboard/` – kod och resurser för GUI/dashboard (om du har en separat modul)
* `tests/` – unittester
* `docs/` – dokumentation, exempelfiler
* `TODO.md` – aktuell arbetslista, roadmap och arbetsflöde

---

## 🚀 Kom igång

```bash
git clone https://github.com/JoakimStorck/worm.git
cd worm
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

### **Exempel: Starta dashboarden**

```bash
python scripts/run_scenario_pipeline.py  # eller motsvarande dashboard-start
```

*(Lägg gärna till instruktion för att köra dashboard/GUI om du har separat script eller notebook!)*

---

### **Exempel: Kör ny simulering eller ladda tidigare resultat**

* **Ny simulering:**
  Starta med scenario-YAML, välj parametrar och kör – resultat och eventlogg sparas automatiskt.
* **Ladda tidigare run:**
  Starta dashboard, välj “Ladda simulering/resultat”, bläddra bland runs (indexeras automatiskt).

---

## 📊 Analys och export

* Alla grafer, tabeller och statistiksammanställningar bygger på replayat tillstånd.
* Exportera bilder (PNG/SVG), urvalsdata (CSV/Excel) eller aggregerad statistik direkt från GUI eller scripts.

---

## 📄 License

MIT License. Se [LICENSE](LICENSE) för detaljer.

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request.

---

## 📬 Contact

For questions or suggestions, contact [Joakim Storck](https://github.com/JoakimStorck).

---

*Senast uppdaterad: 2025-06-14. Se TODO.md för aktuell arbetslista, roadmap och detaljstatus.*

