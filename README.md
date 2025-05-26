
# WORM: Worker-Occupation-Region Model

WORM är en simuleringsmodell för att analysera matchning mellan arbetsgivare och arbetstagare på lokala arbetsmarknader. Modellen kombinerar O*NET-data med svensk statistik (SCB) och bygger upp en struktur där kompetensprofiler, arbetsgivare, jobb och geografi kopplas samman.

## 🧩 Funktioner

- Transformation av O*NET-data till en tvådimensionell occupation space (PCA)
- Klustring av yrken (med kmeans) och visualisering i polär form
- Matchningslogik baserat på överlappning i kompetensprofil
- Automatisk namngivning av kluster via representativa yrken
- Visualisering med interaktiv och statisk matplotlib-plot
- Hämtning av SCB-data via PX-API
- Stöd för geografisk strukturering (påbörjat)

## 📁 Projektstruktur

```
worm/
├── __init__.py                  # Definierar PROJECT_ROOT
├── occupational_profiles.py     # PCA, klustring, transformerad O*NET
├── plotting/
│   └── occupational.py          # Visualisering av occupation space
├── statistics/
│   └── scb_api.py               # PX-API-hämtning från SCB
├── geography/                   # (påbörjas)
├── employers/                   # (påbörjas)
├── workers/                     # (påbörjas)
scripts/
├── scenario_onet_employers.py   # Demo: generera populationer & matcha
├── demo_plot_full_space.py      # Demo: plotta alla yrken i occupation space
```

## 🧪 Installation & körning

Kräver Python 3.10+ och `requirements.txt`.

```bash
pip install -r requirements.txt
```

Exempel på körning:

```bash
python scripts/demo_plot_full_space.py
```

## 💡 Pågående utveckling

Se `ROADMAP.md` för detaljerade TODO-punkter. Nästa fas fokuserar på att bygga simulerade geografiska arbetsmarknader med verklig SCB-data.

## 📚 Källor

- O*NET Data: [https://www.onetcenter.org/](https://www.onetcenter.org/)
- SCB MI0815A: Verksamhetsområden
- Arbetsmarknadsmodellering via kompetensklustring och geografisk simulering

## 📜 Licens

Prototypstadium – ej publiceringsklar. Kontakta projektledare innan distribution.
