# TODO

Aktuell arbetslista. Avklarat står under "Gjort" längst ned för överblick över
var projektet står.

---

## Nu: kalibrering

Geometrin är integrerad och kör, men parametrarna är gissade utifrån
avståndsfördelningar, inte kalibrerade mot data.

- [ ] **`alpha_geo` är sannolikt för hård.** Diagnostiken visar att medianen till
      bästa vakans är ~26 km, vilket vid 0,1/km ger faktorn 0,07. I en
      glesbygdskommun är 25 km pendling normalt. Testa 0,02–0,03.
- [ ] Svep `sigma_gamma` × `alpha_geo` över flera körningar och jämför
      jämviktspunkterna (`scripts/beveridge.py` tar flera körningar).
- [ ] Kalibrera mot faktiska tal för kommunen: arbetslöshet ~6–7 %, vakansgrad
      ~2–3 %. Nuvarande körning landar på 12,7 % / 7,0 %.
- [ ] Kör över längre horisont än ett år – serien planar inte helt ut på 12
      månader (vakanser 760 → 749 i sista steget).
- [ ] Låt `diagnose_mismatch.py` läsa parametrarna ur scenariot i stället för
      hårdkodade defaultvärden.

---

## Modell

- [ ] **Omskolningen saknar utlösare** sedan 0085 tog bort den exogena avgången.
      Ska utlösas ur torr sökning (`propensity_start_education` växer redan där),
      efter beslut om nivå och inriktning (individmodell.md 11).
- [ ] **Beslut vid erbjudandet, inte vid ansökan** (lonemodell.md 4.5d). Bud
      utvärderade vid ansökan binder i 40 dagar plus uppsägningstid, så byten
      med negativ lönevinst förekommer. Byggs med avvisningskostnaden (Becsi
      2026, fråga 4). Mät först: share_moves_wage_loss.
- [ ] **Interna byten som notis** (individmodell.md 6, "Interna byten: notisen"):
      extra sökdrag mot arbetsgivarens nypostade position, mötessannolikhet 1,
      ingen pendlingskostnad, försprång `internal_notice_lead_days` med default 0.
      Test: en tredjedel av bytena interna, koncentrerade till stora arbetsgivare.
      Efter 0089 och 0090.
- [ ] **Skriptet ska vägra starta med ocommittade ändringar** (`kor_0077.sh`):
      `git diff --quiet || exit 1`. Frö 3 i 0089-körningen gjordes på ett
      smutsigt träd och rapporten varnade först i efterhand.
- [ ] **v utan pending.** Vakansstocken räknar tillsatta ej tillträdda; SCB gör
      inte det. Rapportera V_open = V − pending som v, behåll V i identiteten.
- [ ] **Kalibrera `on_the_job_search_factor`** mot ~10 % byten och 3–5 års
      duration, nu när intensiteten ägs av individen (0088). Joakim: anställda
      söker ungefär en gång per år eller mer sällan.
- [ ] **Aktiv cirkel släcks inte** i `handle_destroy_job`; `_become_unemployed`
      gör rätt och ska användas.
- [ ] **Crosswalk O*NET--SNI** (`onet_sni_longform.csv`) är inofficiell och
      odokumenterad. Genomtänkt analys av alternativ (yrkesregistret på SSYK4 via
      O*NET-SOC -> ISCO-08 -> SSYK 2012; steg 0 i STRATEGI_v2) innan den byts.

- [ ] **Beveridgekurvan är degenererad.** Med fast arbetskraft och fast antal
      jobb är v en linjär funktion av u per bokföringsidentitet – alla körningar
      hamnar på samma linje. En äkta kurva kräver variation i efterfrågan
      (antal jobb) mellan körningar.
- [ ] Utbildningsdynamiken verkar trög: `propensity_start_education` ökar 0,1 per
      misslyckad sökning, men mismatchen löses upp mycket långsamt. Undersök om
      utbildning flyttar individer tillräckligt långt i planet.
- [ ] `delta_xi`-värdena i scenarierna är ojämna (0,5 / 3 / default 10 som
      wrappar förbi 2π). Uttryck dem som avsedda omorienteringar i radianer.
- [ ] Överväg automationsfält φ_K analogt med `gts_core.py` i `occupation-space`,
      för att kunna simulera teknologichocker som skiftar mismatchen.
- [ ] Procrustes-orientering vid inläsning – behövs bara om en annan
      encoder-körning används än den procrustes-justerade referenskörningen.
      `load_task_geometry.py` varnar redan om `SECTOR_ROTATION ≠ 0`.

---

## Prestanda

Detta är det som begränsar hur stora populationer som går att köra, och därmed
det största kvarvarande arbetspaketet.

- [ ] **Python-loopen i `global_greedy_matching`.** Alla kandidatpar sorteras och
      itereras i tolken. Ersätt med vektoriserad top-k eller
      `scipy.optimize.linear_sum_assignment` (redan importerad, aldrig använd).
- [ ] **Tät nyttomatris** är O(N·M) i minne; den geografiska nivåindelningen är i
      praktiken en kringgång. Ett spatialt index (rutnät eller KD-träd) över
      vakanser i planet skulle göra sökningen lokal.
- [ ] **Event kontra batch.** `start_job_search` anropar batch-maskineriet för en
      individ i taget. Välj hållning: lätt per-agent-sökning mot index, eller
      äkta batchning per månad.
- [ ] Profilera vid 100 000+ agenter innan optimering – flaskhalsen kan lika
      gärna ligga i händelsekön eller i DataFrame-kopieringen.

---

## Infrastruktur

- [ ] **`eventlog.csv` är inte CSV.** Loggern skriver `nyckel värde`-par. Gör om
      till riktig CSV eller Parquet; filen blir mindre och all efteranalys
      enklare.
- [ ] `scripts/fetch_data.py`: SCB-delarna är stubbar. Fyll i tabellvägar och
      JSON-frågor nästa gång ett uttag ändå görs. Migrera till PxWebApi v2
      (v1 fungerar t.o.m. årsskiftet 2026/2027).
- [ ] Dashboardens *Kör simulering* blockerar gränssnittet – kör asynkront eller
      ta bort knappen till förmån för headless-körning.
- [ ] Dashboarden måste startas om för att se körningar skapade av en separat
      process. Ladda om registret vid behov.
- [ ] Överväg datashader eller DeSO-choropleth för att kunna visa stora
      populationer utan att rita en punkt per agent.
- [ ] Inga tester finns. Börja med matchningskärnan och geometriinläsningen –
      `scripts/worm_smoke_match.py` är en grund att bygga vidare på.

---

## Gjort

- [x] Task-baserad geometri från `occupation-space` ersätter skill-PCA-rummet.
      Full täckning av alla 1016 O\*NET-koder via fallback yrke → familj → global.
- [x] Euklidiskt avstånd på `(x_occ, y_occ)` ersätter pseudometriken
      `√(Δχ² + Δξ²)`, som förvrängde vinkelavstånd nära origo.
- [x] Kärnbredd från yrkets task-radie r_o i stället för individens entropi.
- [x] Entropin H borttagen och ersatt av geometrisk erfarenhetsradie r_i som
      växer med faktisk förflyttning i planet.
- [x] Arbetsgivarens position som centroid av jobbens koordinater (tidigare
      cos/sin av medianer, vilket ger en annan punkt).
- [x] Bytarkostnad: vinkelförflyttning drar av djup via `switch_cost_kappa`.
- [x] Reservationsnytta `utility_min` ersätter tröskeln 1e-4 – ger marknaden
      bestående vakanser i stället för full sysselsättning.
- [x] Kompasspanel med geometrins väderstreck och `geom_source`-färgning.
- [x] Död kod borttagen: `core/agents.py`-beroenden, osynkad
      `run_scenario_pipeline.py`, skill-PCA-skript, `worm/plotting/`-dubbletten.
- [x] `scripts/run_min.py`, `worm_smoke_match.py`, `diagnose_mismatch.py`,
      `beveridge.py`, `load_task_geometry.py`, `fetch_data.py`.
