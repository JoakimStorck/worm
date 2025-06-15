Jag har nu gått igenom de tre dokumenten och gör här en **uppdaterad huvud-TODO** som speglar nuläget, binder ihop de viktigaste styrkorna från tidigare listor och tar bort sådant som är överspelat. Den är avsedd att **ersätta den gamla övergripande TODO\:n**.

---

# TODO – Arbetsmarknadsmodell: Simulering, Visualisering & Plattform

---

## **Att alltid gå igenom inför sprint/utvecklingscykel**

* [ ] Läs igenom Idébanken (se nedan) – lyft in viktiga punkter i TODO eller planering.
* [ ] Kontrollera att inget från tidigare diskussioner/designbeslut fallit bort i plan eller kod.
* [ ] Uppdatera sektionerna nedan utifrån faktisk kodbas och senaste arbetsflöde.

---

## **1. Kärnmål och struktur**

* [x] Skapa och upprätthåll **ScenarioResult-API** som nav för all dataåtkomst (individer, jobb, arbetsgivare, eventlogg).
* [x] Modernisera **simuleringspipeline** (scenario-YAML → world → simulering → snapshot/eventlog).
* [ ] Samla hela arbetsflödet i en **modulär dashboard-ram** (occupation space, karta, filter, statistik, diagram, replay).
* [ ] Allt i pipelinen och gränssnittet måste kunna hantera och exponera >100 000 agenter effektivt.

---

## **2. Data, struktur och simulering**

* [x] Standardisera och dokumentera databasstruktur och kopplingar mellan tabeller (kommuner, DeSO, yrke, SNI/O\*NET, arbetsgivare, eventlogg).
* [x] Implementera scenariohantering med YAML och central konfiguration (stöd för multi-kommun, workforce ratio, m.m.).
* [x] Automatisera och robustgör generering av individer, jobb och arbetsgivare för valfritt scenario/region.
* [ ] Kontrollera att statistik (matchning, arbetslöshet, pendlingsavstånd m.m.) kan tas fram ur både startdata och replayade eventloggar.
* [ ] Fullborda stöd för eventdriven simulering där hela flödet kan spåras/loggas och reproduceras från eventlogg.

---

## **3. Resultat- och run-hantering**

* [ ] Varje simulering/run sparas i egen katalog (`results/{scenario}/{timestamp}/`) med:

  * `individuals.csv`, `jobs.csv`, `employers.csv`, `eventlog.csv`, `meta.yaml`
* [ ] Varje run har meta-data (scenario, parametrar, tidsstämpel, beskrivning).
* [ ] Håll en **central registerfil/index** (ex. `results/index.csv`):

  * Gör det lätt för gränssnitt och analys att lista, söka och ladda runs/resultat.
* [ ] Vid ny simulering, uppdatera index automatiskt.

---

## **4. Replay och statehantering**

* [ ] **Replay-mekanik:**

  * Simuleringsutfall kan återskapas fullt ut via eventlogg (start → valfritt steg → slut).
  * UI för att stega, scrubb’a och hoppa mellan events/steg (slider, knappar, status).
  * Snapshots/checkpoints för snabba hopp i stora loggar.
  * Paneler måste lyssna på replayat state – all visualisering sker alltid på det tillståndet.
  * All statistik, filtrering och export utgår från replay.

---

## **5. Dashboard/GUI och visualisering**

* [ ] **Dashboarden** samlar:

  * Occupation space-panel (interaktiv, synkad med state/filter)
  * Kommun/kartpanel (interaktiv, färgkodning, hover)
  * Filterpanel (dropdowns, sliders, search – alltid på replayat data)
  * Statistikpanel (tabeller, fördelningar, summary för urval)
  * Diagram-/fördelningspanel (histogram, pendlingsavstånd, matchningar etc – kopplade till state/urval)
  * Eventloggpanel (event-tidslinje, flöden per individ/system)
* [ ] All visualisering är **interaktiv och synkad** via central state, oavsett om data kommer från ny simulering eller uppladdad run.

---

## **6. Interaktiv analys och export**

* [ ] All filtrering och urval gäller för aktuell replay/visningsläge (inte bara initialtillstånd).
* [ ] Exportmöjlighet för bilder, data och urval – på valfritt steg i replay.
* [ ] Möjlighet att visa och exportera individers eventhistorik och flöden över tid.
* [ ] Paneler och kontroller har hjälprutor, onboarding och dokumentation.

---

## **7. Modellutveckling & API-framsteg**

* [x] Koppla O\*NET/SNI/SSYK och occupation space-data till arbetsgivare och individer.
* [x] Få multi-kommun-scenarier och workforce ratio att fungera sömlöst.
* [ ] Utveckla vidare:

  * Arbetsmarknadsstatus och matchningsalgoritmer (occupation space, geografiskt, preferensbaserat, pendlingsregel…)
  * Spatiala queries (pendlingsmatriser, närhetsregler, flöden)
  * Eventdriven logik och analys (chocker, policyinterventioner, arbetslivsbanor etc.)

---

## **8. Plattform, prestanda och automatisering**

* [x] Optimera för prestanda och minne (profilering, lazy loading, checkpoints, batchning).
* [ ] Testa och demonstrera pipeline + GUI på >100 000 agenter och lång eventlogg.
* [ ] Automatisera test, demo och validering – så varje nytt steg kan visas för kollega/”kund”.

---

## **Idébank / Exploratory / Kom-ihåg**

* Replay är nödvändigt för korrekt återgivning av simulering – ingen panel får visa "slutläge" baserat på endast individuals.csv.
* All central state byggs kring ScenarioResult (eller framtida överklass för run/state).
* Snapshots/checkpoints i eventlogg för snabb replay och hopp.
* UI för replay: slider + knappar, med aktuell eventinfo (display).
* Eventloggpanel kan visa tidslinje/flöde för individ/urval/system – kopplad till aktuell replay.
* Register/index över runs för smidig laddning/byte/analys.
* Plattformen ska kunna återanvändas för både demo, analys, och forskningsrapporter.
* Review/Sync-punkt: Vid varje sprint – läs igenom Idébanken och TODO, synka det som ska realiseras.

---

## **Detta kan utgå/flyttas till bakgrund/roadmap:**

* Tidigare, mer detaljrika roadmappar om alla AP/arbetsblock – håll kvar dessa för referens, men låt huvud-TODO fokusera på aktiva, pågående och högsta-prio-flöden.
* Moduler och kod kring gammal icke-eventdriven simulering (ersatt av replay/ny pipeline).
* Temporära visualiseringar som ej bygger på central state eller replay (används bara för snabbtest, ej som officiell del).

---

## **Hur detta hänger ihop med nuläget**

* **Kärnan i kodbasen** (pipeline, ScenarioResult, eventlogg, GUI-paneler) är implementerad och fungerar för end-to-end-flöde i Falun-baseline och liknande scenarier.
* **Replay, dashboard-integration och run-hantering** är nästa stora utvecklingssteg, tillsammans med bredare analysmöjligheter och full interaktivitet.
* Allt nytt byggs modulärt och API-drivet, så att framtida arbetsflöden och forskningsbehov lätt kan integreras.

---

*Senast uppdaterad: 2025-06-14.*
