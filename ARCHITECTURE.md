# WORM – arkitektur

Detta dokument beskriver hur WORM är byggt och varför. Det beskriver koden som
den faktiskt ser ut, inte en planerad framtid; öppna frågor står i `TODO.md`.

---

## 1. Grundvalet: kolumnärt tillstånd, inga agentobjekt

Simuleringens hela tillstånd ligger i tre pandas-DataFrames på `World`:

| Tabell | Nyckelkolumner |
|---|---|
| `individuals` | `individual_id, status, job_id, x, y, deso_code, municipal_code, x_occ, y_occ, chi, xi, r_i, education_level, propensity_*` |
| `jobs` | `job_id, employer_id, individual_id, onet_code, x, y, zone_code, layer, employer_size, x_occ, y_occ, r_o, geom_source` |
| `employers` | `employer_id, municipal_code, x, y, x_occ, y_occ, chi, xi` |

Det finns medvetet **ingen klass per agent**. En objektorienterad representation
(en `Worker`-instans per individ) kostar hundratals byte per agent i
Python-overhead och tvingar fram loopar i tolken. Målet är populationer i
storleksordningen 10⁵–10⁶, och då är struct-of-arrays rätt form: varje agents
arbetsmarknadstillstånd är några få tal, kolumnerna ligger sammanhängande i
minnet, och matchningen kan vektoriseras.

Geometrin förstärker det valet. När ett yrke reduceras till `(x_occ, y_occ, r_o)`
behöver ingen agent bära en högdimensionell kompetensvektor – yrkesrymden är en
uppslagstabell med ~1000 rader, och individen bär två koordinater.

*(Rester av en tidigare OO-design – `core/agents.py`, `core/jobs.py`,
`Occupation`-dataklassen – är borttagna.)*

---

## 2. Två rum

Varje individ och jobb har en position i två oberoende rum:

**Geografiskt rum.** SWEREF-koordinater `(x, y)` i meter, härledda ur
DeSO-zoner och tätortspolygoner (`core/geography/`). Avstånd används för
pendlingsstraff och för att gruppera matchning i nivåer.

**Yrkesgeometriskt rum.** Enhetsskivan från *The Polar Geometry of Work*.
Positionen `(x_occ, y_occ)` är kartesisk, med `chi`/`xi` bevarade för
visualisering och tolkning. Rummet läses in färdigberäknat från
`occupation-space` via `scripts/load_task_geometry.py` – ingen embedding eller
PCA körs i WORM.

Att båda är euklidiska rum är poängen: matchning blir en avståndsberäkning i
stället för en tabelluppslagning mellan diskreta yrkesklasser.

---

## 3. Från scenario till körning

```
scenario.yml
    │  ConfigReader          validerar, löser defaults mot per-kommun-override
    ▼
ScenarioBuilder              frågar SQLite: DeSO, befolkning, SNI-fördelning,
    │                        utbildningsnivåer, yrkesgeometri
    │                        samplar individer, arbetsgivare, jobb
    ▼
World                        händelsekö (heapq), tillstånd som DataFrames
    │
    ├── batch-matchning vid t=0
    └── händelsedriven simulering över horisonten
            │
            ▼
        output/run_<tid>/     eventlog, start- och sluttillstånd, metadata
            │
            ▼
        runs_registry.csv → dashboard
```

**Individer** samplas kartesiskt: kommunens yrkesfördelning (SNI → O\*NET) ger
viktade yrkescentrum, och varje individ placeras vid ett centrum plus gaussisk
jitter i planet, klippt till skivan. Att jittra kartesiskt snarare än i (χ, ξ)
undviker den förvrängning som uppstår nära origo.

**Arbetsgivare** placeras geografiskt efter zonlager och får en yrkesposition som
medelvärdet av sina jobbs `(x_occ, y_occ)` – alltså centroiden, i linje med
geometrimodellens definition.

**Jobb** ärver sitt yrkes position och task-radie r_o.

---

## 4. Matchning

Matchningen sker i tre geografiska nivåer (`core/matching.py`): först inom DeSO,
sedan inom kommun, sist globalt. Två lägen finns – `multilevel_exhaustive` (kör
varje nivå till uttömning) och `interleaved_multilevel_batch` (varvar nivåerna i
rundor). Nivåindelningen håller nyttomatriserna små; en tät matris över alla
individer × alla jobb vore O(N·M) i minne.

Kärnan i alla nivåer är `global_greedy_matching` i `core/occupations/utils.py`:

1. Euklidiskt avstånd `d` mellan individens och jobbets `(x_occ, y_occ)`.
2. Gaussisk kärna med geometrisk bredd `sigma = sigma_gamma·√(r_o² + r_i²)`.
3. Geografiskt straff `exp(−alpha_geo · km)`.
4. Par under `utility_min` förkastas; resten tilldelas giriga i fallande nytta.

Steg 4 är det som skiljer en marknad med friktion från en utan. Utan
reservationsnytta fyller den giriga algoritmen varje ledigt jobb med vilken
kandidat som helst, och marknaden når full sysselsättning.

---

## 5. Händelsemotorn

`World.simulate()` driver en prioritetskö av händelser sorterad på tid.
Händelsetyperna finns i `RULE_SWITCH` i `core/event_handlers.py`: `quit_job`,
`start_job`, `start_job_search`, `start_education`, `end_education`,
`start_internal_training`, `internal_job_change`, `career_break`, plus
systemhändelserna `new_month` och `new_year` som loggar aggregerad statistik.

Händelser föder händelser: ett påbörjat jobb schemalägger framtida uppsägning,
eventuell internutbildning och eventuellt internt jobbyte, var och en med
fördelningar definierade under `event_timings` i scenariot.

All kapabilitetsdynamik går genom en enda punkt, `_update_individual`, som
garanterar att `chi`, `xi`, `r_i` och `(x_occ, y_occ)` alltid är synkroniserade.
Där tas också bytarkostnaden ut: ett vinkelsteg minskar χ proportionellt mot
vinkelavståndet, och förflyttningen breddar erfarenhetsradien r_i.

**Känd spänning.** Motorn är händelsedriven, men matchningsmaskineriet är
batchorienterat och anropas för en sökande i taget från `start_job_search`. Det
betyder batch-overhead per individ. Vid stora populationer behöver antingen
sökningen bli lätt (spatialt index över vakanser) eller matchningen äkta batch
(samla sökande per månad).

---

## 6. Resultat och återspelning

Varje körning skriver en katalog under `output/`:

```
run_<tidsstämpel>/
  metadata.txt                 scenario, tid, körnings-id
  initial_state_*.csv          tillstånd efter batch-matchning vid t=0
  final_state_*.csv            tillstånd vid horisontens slut
  eventlog.csv                 alla händelser
  basic_stats_before/after.json
  *_matching_stats.json, *_commuting_stats.json
```

`runs_registry.csv` indexerar körningarna så att dashboarden kan lista dem.

**Observera:** `eventlog.csv` är trots filändelsen **inte** en CSV.
`EventLogger._write_log` skriver rader på formen
`tid, händelse, nyckel värde, nyckel värde, …`. Verktyg som läser den måste
parsa det formatet (se `scripts/beveridge.py`). Att göra loggen till riktig CSV
eller Parquet står på `TODO.md`.

---

## 7. Visualisering

Dashboarden (`pipeline/gui_dashboard_pipeline.py`) är en **Bokeh-serverapp** –
den bygger ett `curdoc()`-dokument med callbacks och måste startas med
`bokeh serve`. Panelerna i `core/visualization/` delar `ColumnDataSource`-objekt
så att markering i en panel speglas i de andra (`selection_sync.py`).

`occupation_space_panel.py` ritar enhetsskivan med geometrins väderstreck,
radiella stödcirklar och poletiketter, och färgar jobb efter `geom_source` så att
yrken utan egen geometri (familje- eller global fallback) syns direkt.

Knappen *Kör simulering* kör simuleringen synkront i serverns event-loop och
låser gränssnittet under tiden. För annat än små scenarier är mönstret "kör
headless, öppna resultatet i dashboarden" att föredra.

---

## 8. Data

SQLite (`data/worm.sqlite3`) håller allt förberäknat: DeSO-zoner och deras
geometrier, befolkning och utbildningsnivåer, sysselsättning per kommun och SNI,
pendlingsmatris, SNI→O\*NET-mappning och yrkesgeometrin. Databasen byggs av
`scripts/create_database.py` och versionshanteras inte – den och källfilerna
synkas manuellt mellan maskiner.

Yrkesgeometrin är den enda tabellen som byts ut separat, via
`scripts/load_task_geometry.py`. Fallback-hierarkin (eget yrke → jobbfamilj →
globalt medelvärde) garanterar att varje O\*NET-kod som SNI-mappningen kan nå har
en position, vilket krävs för att inga jobb ska sakna koordinater.
