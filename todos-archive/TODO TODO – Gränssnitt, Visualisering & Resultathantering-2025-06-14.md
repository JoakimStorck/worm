Här följer en **uppdaterad TODO** som binder ihop *allt* vi har diskuterat:

* **Huvuduppgifter** i prioriterad och logisk ordning
* **Replay och eventlogg** inbyggt i arbetsflödet
* **Tydlig koppling till idébank** där designbeslut, förbättringsförslag och påminnelser samlas
* **Sektion för “Att gå igenom”** högst upp

---

# TODO – Gränssnitt, Visualisering & Resultathantering

---

## Att gå igenom inför varje sprint eller större utvecklingscykel

* [ ] Läs igenom **Idébanken** nedan: Finns något där som nu bör lyftas till aktiv TODO?
* [ ] Saknas någon diskuterad idé eller lärdom i projektplanen?
* [ ] Har alla designbeslut (se Idébanken) tagits om hand i respektive delavsnitt?

---

## 1. Pipeline och grundstruktur

* [x] ScenarioResult-API: Gemensamt API för åtkomst av individ-, jobb- och arbetsgivardata.
* [x] Simuleringspipeline: Flöde från scenario/config → world-byggnad → simulering → snapshot/Result.
* [x] Dashboard-ramverk: Samla alla paneler (occupation space, karta, filter, statistik, diagram) i en gemensam vy, där allt bygger på samma datamodell och selection state.

---

## 2. Organisation och hantering av simuleringsresultat (runs)

* [x] Standardiserad katalogstruktur för runs:
  Varje simulering sparas i egen katalog med alla utdatafiler (`individuals.csv`, `jobs.csv`, `employers.csv`, `eventlog.csv`, `meta.yaml`).
* [x] Metadatafil för varje run:
  Alla runs har en meta-fil med scenario, parametrar, timestamp, beskrivning.
* [x] Central index/register:
  Indexfil (t.ex. `results/index.csv`) med info om alla runs för urval i gränssnittet.
* [x] Automatisk uppdatering av index vid varje ny körning.

---

## 3. Replay och statehantering

* [x] Replay-mekanism:
  Eventloggen används för att återskapa hela simuleringen – antingen till slutläge eller valfri tidpunkt/steg. All analys och visualisering ska utgå från återspelat tillstånd.
* [ ] UI-komponent för replay:
  Tidslinje/slider + knappar (\[<<], \[<], \[Play/Pause], \[>], \[>>]), snabbhopp till event/steg, och visning av aktuell status.
* [ ] Teknik för effektiv replay:

  * In-memory state och sekventiell replay
  * Snapshots/checkpoints för snabbhopp
  * Indexering och batched replay vid stora loggar
  * Visuell återkoppling (progress, aktuell status)
* [ ] Alla paneler bygger på det aktuella replayade state\:t.

---

## 4. Gränssnittspanel för urval av simulering/resultat

* [x] Panel för val av indata/config:
  Användare kan ladda/skriva in scenariofil och starta ny simulering.
* [x] Panel för urval av tidigare runs:
  Lista/dropdown över tillgängliga runs, med namn, scenario, tidpunkt, beskrivning.
* [x] Laddning av run till dashboard:
  Vid val av run laddas data + eventlogg, replayas och alla paneler uppdateras.
* [x] All analys, visualisering, filtrering och export bygger alltid på *faktiskt state* efter replay – inte bara initialdata.

---

## 5. Utforskning och visualisering av resultat

* [ ] Occupation Space-panel:
  Visualisering och interaktivitet enligt tidigare TODO, styrd av replayat state.
* [ ] Kommun-/kartpanel:
  Visualisering av individer/arbetsgivare, styrd av replayat state.
* [ ] Filterpanel:
  Alla filter gäller på det aktuella state\:t.
* [ ] Statistikpanel:
  All statistik baseras på det aktuella replayade läget.
* [ ] Diagram-/fördelningspanel:
  Histogram, stapeldiagram och fördelningar uppdateras alltid vid replay/urval.
* [ ] Eventloggpanel:
  Möjliggör visualisering/utforskning av händelser/event – på individ- och systemnivå, samt se eventhistorik vid urval.

---

## 6. Sammanhållen integration och API

* [ ] Central state/data-vy:
  All filtrering, selection, paneldata och replay bygger på ett ScenarioResult/state-objekt som uppdateras vid byte av run, replay eller filter.
* [ ] Enhetligt API för paneler:
  Paneler och kontroller ska använda och lyssna på state, alltid vara synkroniserade.
* [ ] Elegant återkoppling mellan urval och visualisering:
  Alla urval (ny run, replay, filter, selection) påverkar dashboarden och alla aggregerade vyer.

---

## 7. Export, användarstöd och dokumentation

* [ ] Export:
  Möjlighet att spara urval, bilder och underliggande data för alla paneler, vid valfritt tillstånd.
* [ ] Användarhjälp och onboarding:
  Beskriva hur man bläddrar/laddar/analyserar runs.
* [ ] Tydlig dokumentation av filstruktur och arbetsflöde.

---

## Idébank / Exploratory (för vidareutveckling, referens & påminnelser)

* Replay-mekanik krävs för att alla resultat/visualiseringar ska stämma (diskuterat 2025-06-13).
* UI-komponent: Slider + knappar för replay, med aktuell eventinfo (disk 2025-06-14).
* Snapshots/checkpoints i eventlogg för snabb replay och hopp vid stora runs.
* Central register/index över alla runs för enkel val/laddning i GUI.
* Möjlighet att visa individens eventhistorik på urval.
* Exportfunktioner för både plottar och urvalsdata.
* Filter och selection-paneler ska alltid spegla nuvarande state.
* Event-hantering mellan paneler: gemensamt observer/subscribe-mönster.
* **Review/Sync-punkt:** Vid varje sprint, läs igenom idébank och TODO och synka in det som ska realiseras.

---

Vill du ha denna i fil, eller vill du börja strukturera upp den i ett projektverktyg/ärendehantering direkt?
