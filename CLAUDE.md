# WORM — arbetssätt

Händelsedriven simulering av en lokal arbetsmarknad, byggd på den polära
uppgiftsgeometrin i *The Polar Geometry of Work* (Storck & Andersson).

## Läs först

- Pappret, för geometrins begrepp. **χ är task specificity, inte
  specialisering**; ξ är riktning.
- `docs/ARCHITECTURE.md`, `docs/individmodell.md`, `docs/lonemodell.md`,
  `docs/utbildningsmodell.md`.

Avtalsgolvet ligger på positionens sida som `wage_floor_share·Π`.

## Språk

Kod, kommentarer, commit-meddelanden och tester skrivs på **svenska**.
Kommentarer förklarar *varför*, inte vad.

## En mekanism per commit

Varje ändring: rättelse + tester + ett commit-meddelande som förklarar vad
som var fel, varför det var fel och vad som medvetet lämnas ogjort. Blanda
inte två mekanismer — en körning ska gå att läsa för sig.

Commit-meddelandena är projektets minne. De är långa med avsikt.

## Testdisciplin

Tester körs från `tests/`:

    cd tests && python -m pytest -q

**Ett test som inte kan falla är värdelöst.** Verifiera varje nytt test
genom att bryta koden det skyddar och se att det faller. Bryt en sak i
taget — två samtidiga brytningar kan maskera varandra.

Fallgropar som har kostat tid:
- Testa mekanismen, inte attrappen. Ett test mot `FakeLogger` prövar inte
  vad den riktiga loggen skriver.
- Brusfri testdata gör viktningstester meningslösa: varje viktning ger
  samma svar när punkterna ligger exakt på modellen.
- Testdata måste vara internt konsistent. En grupps `total` som inte
  stämmer med pyramidens summa gör kvoten till något annat än den mäter.

## Körning

    SCENARIO=scenarios/ovansiljan_3_kommuner.yml bash kor_0077.sh

Fem frön, tio år, tester först, sedan `analysis.py --all`. Skriptet vägrar
köra på ocommittade ändringar. Svep: `svep_parameter.sh <param> "<värden>"`.

Testfallet är Ovansiljan (Mora, Orsa, Älvdalen). Modellen ska fungera för
valfri kommunkombination.

## Databas

    python scripts/fetch_data.py --only <delsträng>
    python scripts/create_database.py
    python scripts/load_task_geometry.py --write   # uppgiftsrummet, separat

`create_database.py` rör aldrig `onet_occupation_space`.

## SCB-data (PxWebApi v2)

Bas: `https://statistikdatabasen.scb.se/api/v2`. Tabeller nås via id
(`TABnnnn`), inte ämnesstig. Frågan byggs ur tabellens egen metadata, inte
ur handskrivna värdemängder.

Fyra fallgropar, alla upptäckta genom att en fil inte gick att läsa:

1. **Selektionen måste ligga i POST-kroppen.** Som GET blir URL:en för lång
   och IIS svarar **404**, inte 414.
2. **`UseCodesAndTexts` skriver "kod - text" i VARJE cell**, inte bara i
   rubriken. Dela på första `" - "`.
3. **Tid hamnar i värdekolumnens rubrik** även när uttaget ber om den i
   stub. PxWeb hörsammar inte placeringen för den variabeln.
4. **Filerna är latin-1** när svaret bär klartext. Använd
   `core.database.utils.las_rader`, som provar utf-8 först — omvänd ordning
   ger tyst fel text i stället för ett fel.

Läs alltid `head -3` på en ny fil innan du skriver en läsare för den.
Specifikationen håller för kontraktet, inte för hur utdata ser ut.

Totalradskonventionerna skiljer sig mellan uttag och dokumenteras i varje
läsare: arbetsmarknadsstatus och SNI-filen har totalrader (filtrera),
yrkesregistrets uttag saknar dem (summera), länsfilen har `00 Riket`
(uteslut).

## Inga tysta reserver

Saknas underlag ska koden kasta med besked om hur det hämtas. En platt
fördelning är inte ett sämre alternativ utan ett annat, och den ska inte
smyga sig in när tabellen fattas.

## Kolumnvyer

Individtabellen har kolumnvyer (0110). En hel kolumn tilldelad byter block i
pandas; anropa `world.refresh_ind()` efteråt.
