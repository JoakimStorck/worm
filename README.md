# WORM – Worker-Occupation-Region Model

WORM är en händelsedriven simulering av svensk arbetsmarknad på kommun- och
DeSO-nivå. Individer, jobb och arbetsgivare placeras i två rum samtidigt: ett
**geografiskt** (SWEREF-koordinater, DeSO-zoner, pendlingsavstånd) och ett
**yrkesgeometriskt** – enhetsskivan från *The Polar Geometry of Work*, där varje
yrke är en punkt (χ, ξ) med en task-radie r_o.

Matchning mellan arbetare och jobb är därmed en fråga om **avstånd**: hur långt
är det till jobbet i planet, och hur långt är det geografiskt.

---

## Yrkesgeometrin

Geometrin beräknas inte här. Den kommer färdig från systerprojektet
`occupation-space` (publikt som
[`geometry-of-work`](https://github.com/JoakimStorck/geometry-of-work)), där
O\*NET:s 17 606 task-statements bäddas in med `text-embedding-3-large` och
projiceras med PCA till ett tvådimensionellt plan.

Planet har en tolkning som ligger fast mellan körningar:

```
                 Analytiskt (norr)
                        |
  Fysiskt-manuellt  ----+----  Människocentrerat
      (väster)          |            (öster)
                  Service (söder)
```

* **ξ** (vinkel) = *vad slags arbete* – domänen.
* **χ** (radie) = *hur specifikt* – 0 i mitten är generellt, 1 är högspecialiserat.
* **r_o** = yrkets task-radie, spridningen av dess egna uppgifter kring centroiden.

WORM lagrar kartesiska koordinater `(x_occ, y_occ) = (χ·cos ξ, χ·sin ξ)` och
mäter **euklidiskt avstånd**, så att avstånd, χ och r_o alla lever i samma enhet.

---

## Matchningsmodellen

En arbetares matchproduktivitet mot ett jobb är en gaussisk kärna i planet,
multiplicerad med ett geografiskt avståndsstraff:

```
d      = |(x_occ, y_occ)_individ − (x_occ, y_occ)_jobb|
sigma  = sigma_gamma · sqrt(r_o² + r_i²)
nytta  = exp(−½ d²/sigma²) · exp(−alpha_geo · km)
```

Kärnbredden är geometrisk: yrkets task-radie r_o faltad med arbetarens
**erfarenhetsradie** r_i. En ny arbetare är en punkt (r_i = 0), och r_i växer med
faktisk förflyttning i planet – den som bytt riktning täcker ett bredare område,
den som fördjupat sig förblir smal. (Tidigare fanns här en entropi H; den
föregick geometrimodellen och är borttagen.)

Jobb tilldelas giriga i fallande nytta, med `utility_min` som reservationsnytta:
under den accepteras inget jobb. Det är den parametern som ger marknaden
bestående vakanser i stället för full sysselsättning.

Riktningsbyten kostar. Ett vinkelsteg drar av djup (χ) proportionellt mot
vinkelavståndet, styrt av `switch_cost_kappa` – riktningsspecifikt humankapital
urholkas när man byter domän.

---

## Kom igång

```bash
git clone https://github.com/JoakimStorck/worm.git
cd worm
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 1. Data

Stora dataartefakter ligger utanför git (se `.gitignore`) och synkas manuellt.
Du behöver:

* `data/worm.sqlite3` – databasen. Byggs av `scripts/create_database.py` ur
  SCB-filer (DeSO, befolkning, sysselsättning per SNI, pendling, utbildning) och
  GPKG-lager i `data/`, plus O\*NET-textfiler i `onet_data/`.
  `scripts/fetch_data.py` hämtar O\*NET automatiskt; SCB-uttagen behöver egna
  tabellurval.
* `data/geometry/` – fyra filer från `occupation-space`, ur körningen
  `embeddings__openai__text-embedding-3-large__d3072__year-2025__v30_1/exports`:
  `occupation_embeddings_polar_scaled.csv`, `task_embeddings_polar_scaled.csv`,
  `job_family_centers_polar_scaled.csv`, `occ_meta.csv` samt (rekommenderat)
  `radial_scale.json`.

### 2. Läs in geometrin

```bash
cp data/worm.sqlite3 data/worm.sqlite3.bak     # tabellen skrivs över
python scripts/load_task_geometry.py           # torrkörning, skriver bara ut
# avkommentera write_to_db() och kör igen
```

Skriptet skriver `onet_occupation_space` (och `onet_job_family_geometry`) med
kolumnerna `onet_code, xi, chi, x_occ, y_occ, r_o, geom_source`. Alla 1016
O\*NET-koder får en position: de flesta egen geometri, resten via familjecentrum
eller globalt medelvärde – `geom_source` visar vilket.

### 3. Kör

```bash
python scripts/worm_smoke_match.py    # databaslöst självtest av geometrin
python scripts/run_min.py             # bygg världen + batch-matchning vid t=0
```

Full körning som registreras under `output/` och kan öppnas i dashboarden:

```bash
python -c "import core.scenario_runner as r; r.run_and_log_scenario('scenarios/mora_baseline.yml')"
```

### 4. Dashboard

Bokeh-serverapp – startas med `bokeh serve`, inte `python`:

```bash
bokeh serve pipeline/gui_dashboard_pipeline.py --port 5006
```

Kör den på samma maskin som databasen. Åtkomst från annan dator via SSH-tunnel:

```bash
ssh -L 5006:localhost:5006 användare@värd
# öppna http://localhost:5006/gui_dashboard_pipeline
```

Nya körningar syns i väljaren först efter omstart av servern.

### 5. Analys

```bash
python scripts/diagnose_mismatch.py    # varför är de arbetslösa arbetslösa?
python scripts/beveridge.py            # arbetslöshet mot vakansgrad
```

`diagnose_mismatch` skiljer **geometriskt blockerade** (ingen vakans ligger nära
nog) från **konkurrens/tajming** – uppdelningen avgör om kalibreringen eller
modellen behöver justeras.

---

## Kalibrering

Parametrar under `simulation:` i scenariot styr friktionen:

| Parameter | Betydelse |
|---|---|
| `sigma_gamma` | Kärnbredd som andel av r_o. Lägre = skarpare matchning. |
| `utility_min` | Reservationsnytta. Sätter vakansgraden. |
| `alpha_geo` | Geografiskt avståndsstraff per km. |
| `switch_cost_kappa` | Djupkostnad per radian vid riktningsbyte. |
| `breadth_from_move` | Hur mycket förflyttning breddar r_i. |

Nuvarande värden är härledda ur avståndsfördelningen, inte kalibrerade mot data.
`alpha_geo` är särskilt känslig: 0,1 per km innebär att en mil kostar en faktor
e, vilket är hårt för en glesbygdskommun där 25 km pendling är normalt.

---

## Struktur

```
core/
  world.py              simuleringsmotor, händelsekö, tillstånd som DataFrames
  event_handlers.py     jobbyte, utbildning, träning, uppsägning, karriärbreak
  matching.py           flernivåmatchning DeSO → kommun → global
  occupations/utils.py  matchningskärnan och kapabilitetsdynamiken
  scenariobuilder.py    genererar individer, jobb och arbetsgivare ur scenario + DB
  configreader.py       läser och validerar scenario-YAML
  geography/            DeSO-zoner, koordinater, avstånd
  database/             schema och inläsning av SCB- och O*NET-data
  statistics/           sammanfattande statistik
  visualization/        Bokeh-paneler (yrkesrum, karta, statistik)
scenarios/              scenariodefinitioner (YAML) + SCENARIO_SCHEMA.md
scripts/                körning, geometriinläsning, diagnostik, datahämtning
pipeline/               dashboard-app
```

Tillstånd lagras kolumnärt som pandas-DataFrames (`individuals`, `jobs`,
`employers`) – inte som objekt per agent. Valet är gjort för att kunna hantera
stora populationer: varje agents tillstånd är några få tal, och de tunga
operationerna vektoriseras över kolumnerna.

---

## Licens

MIT. Se [LICENSE](LICENSE).

## Kontakt

[Joakim Storck](https://github.com/JoakimStorck)
