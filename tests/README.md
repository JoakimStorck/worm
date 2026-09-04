# Tester

Kräver ingen databas. Testerna bygger syntetiska världar i minnet, så de går
att köra på vilken maskin som helst och är snabba nog att köra före varje
commit.

```bash
pip install pytest
python -m pytest tests/ -q          # hela sviten, ~5 s
python -m pytest tests/ -v          # med testnamn
python -m pytest tests/test_job_flows.py -q
```

## Vad som täcks

| Fil | Täcker |
|---|---|
| `test_geometry.py` | Euklidiskt avstånd, kärnbredd ur r_o och r_i, kartesisk sampler, kapabilitetsdynamik (djup, bytarkostnad, synkade koordinater) |
| `test_matching.py` | Överskottsformeln, positivt överskott, ingen dubbeltilldelning, reservationslönens och pendlingskostnadens effekt, parameterpropagering till kärnan |
| `test_price_field.py` | Prisfältets form, att djup betalar sig i norr, kartesisk/polär överensstämmelse, normalisering |
| `test_job_flows.py` | Förstörelse och återfyllnad, jämvikt mot teori, storleksoberoende, förskjutning av innehavare, aktivfiltrerad statistik |

## Regressionstester

Fyra tester finns för fel som redan inträffat och inte får återkomma:

- **Parameterpropagering.** `sigma_gamma`, `commute_cost_per_km` och
  `min_surplus` försvann i `**kwargs`, så den händelsedrivna matchningen körde
  på defaultvärden medan batch-matchningen fick rätt värden -- två olika
  kalibreringar i samma körning.
- **Storleksoberoende jobbstock.** `floor()` på antalet nya jobb nollade
  underskott under `1/fill_rate`, vilket kvävde jobbskapandet hos små
  arbetsgivare.
- **Återpostning utan aktiva jobb.** Mallen för nya jobb byggdes ur aktiva
  jobb, så en arbetsgivare som förlorat alla sina positioner dog permanent.
  Med enmansföretag kollapsade stocken till under halva målet.
- **Kortaste vinkelavstånd.** Bytarkostnaden ska räknas på det kortaste
  vinkelavståndet, så att ett steg på 2π−0,2 kostar som 0,2.

## Att skriva nya tester

Fixturerna `individuals` och `jobs` i `conftest.py` ger små DataFrames med
alla kolumner matchningen behöver. `make_world()` bygger en syntetisk `World`
för jobbflödestester, `run_months()` kör förstörelse och månadsposting.

Jobbpostningen använder stokastisk avrundning. En autouse-fixtur sätter fast
frö; testa ändå hellre ackumulerat utfall över flera månader än ett enskilt
anrop.
