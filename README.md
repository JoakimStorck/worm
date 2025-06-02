# WORM – Worker-Occupation-Region Model

WORM is a modular Python framework designed for analyzing labor markets, commuting patterns, and regional structures. It enables integration of statistical data, geographic hierarchies, and synthetic modeling to support research and planning at municipal, regional, and national levels.

---

## 🌟 Vision

To provide a transparent, scalable, and data-driven simulation environment for studying the Swedish labor market and occupational dynamics, supporting research, policy analysis, and educational use.

The project bridges the gap between real-world labor market data and agent-based modeling, enabling detailed yet flexible experiments with geography, occupations, workforce, and commuting—both for current Swedish conditions and hypothetical future scenarios.

---

## Scalability Metrics & Performance Goals

WORM är utformat för att **hantera simuleringar med 100 000–1 000 000 agenter** på en vanlig workstation/server. Projektets infrastruktur och kodstruktur är explicit anpassad för att möjliggöra effektiv simulering av stora, event-drivna arbetsmarknadsmodeller – både vad gäller minne, processor och IO.

### **Övergripande mål**

* **Minnesanvändning:**
  Optimerad datamodell (pandas DataFrames, numpy-arrayer, ID-baserad länkning) ska möjliggöra att 1e5–1e6 agenter kan laddas och hanteras i RAM på en dator med 16–32 GB RAM.
* **Eventhantering:**
  Event queue och simulering ska klara av att processa >10 000 events/sekund (batchvis) i typiska scenarion, även för storleksordningen 1e6 events.
* **Lagring & export:**
  Allt data (agenter, events, resultat) ska kunna exporteras och laddas in snabbt via kolumnformat (t.ex. Parquet), utan flaskhalsar från Python-objekt.
* **Simuleringstid:**
  Exempelsimulering med 100 000 agenter och 1 000 000 events ska kunna genomföras på < 15 minuter på modern workstation (2024 standard).

### **Mätpunkter och tester**

* **Memory footprint:**
  Redovisas och testas vid varje release för populationsstorlekar 1e4, 1e5 och 1e6 (se AP10c i TODO).
* **Batch/event throughput:**
  Resultat från prestandatester dokumenteras i \[AP10b/AP10c] och loggas i repo/wikis.
* **Demo scripts:**
  Exempelsimuleringar, benchmarks och visualiseringar publiceras som demo-notebooks och scripts (se AP10e).
* **Testsvit:**
  Alla centrala datamodeller, agentbatcher, eventhantering och IO testas med pytest eller motsvarande.

### **Plan för fortsatt optimering**

Se \[AP10: Simulation Infrastructure & Scalability] i TODO för detaljer om parallellisering, distribuerad körning och batchhantering. **Vid behov av större skala kan simulering delas upp batchvis per region eller tidsintervall, och optimeras för multiprocessor/multicore.**

---

## 📐 Scope

* **Synthetic labor market modeling:** Simulate workers, jobs, workplaces, and commuting at the level of municipalities, regions, and user-defined zones.
* **Integration of official data sources:** Combine detailed SCB microdata (employment, establishments, demographics, commuting, education) with O\*NET occupational taxonomies.
* **Flexible geography:** Model arbitrary geographies—from individual municipalities to larger regions—with customizable granularity (zones/districts), using YAML/CSV specifications.
* **Data-driven and random generation:** Allow both fully random (“from scratch”) and empirically grounded (KNN-based) generation of municipalities, regions, and spatial structure.
* **Commuting and spatial flows:** Support the generation and analysis of commuting matrices and the relationship between residence and workplace.
* **Matching and skills modeling:** Represent workers and jobs in an n-dimensional occupation space, enabling studies of skills mismatch, clustering, and labor market dynamics.
* **Reproducible and modular:** Store all data in a local SQLite database; provide demo scripts, import/export routines, and well-documented Python modules for each modeling layer.
* **Visualization and analysis:** Include tools for visualizing geography, labor market structure, commuting flows, and simulation outputs.
* **Open science and documentation:** Maintain transparent, extensible documentation and code to support open research, reproducibility, and collaborative development.

---

## 🚀 Features

* Modular architecture with clear separation of concerns
* Integration with SCB (Statistics Sweden) and O\*NET data
* SQLite backend for local data storage
* YAML support for structured geographic definitions
* K-Nearest Neighbors (KNN) algorithms for typology matching
* Extensible classes for municipalities, regions, zones, and nations
* Demo scripts for data import, analysis, and synthetic generation

---

## 📦 Project Structure

```plaintext
worm/
├── data/                        # Raw data, imported/exported CSV, YAML, SQLite
├── worm/
│   ├── database/                # SQLite handling
│   ├── geography/               # Geographic models and utilities
│   ├── yaml_io/                 # YAML import/export/validation
│   ├── knn/                     # KNN algorithms and related analysis
│   └── utils/                   # Helper functions
├── scripts/                     # Executable demo and helper scripts
├── tests/                       # Unit tests
├── docs/                        # Documentation, README, TODO
├── .gitignore
├── setup.py / pyproject.toml
└── requirements.txt
```

---

## 🛠️ Installation

```bash
git clone https://github.com/JoakimStorck/worm.git
cd worm
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

## 📊 Example Usage

**Initialize the SQLite database and import SCB data:**

```bash
python scripts/demo_sqlite_init.py
```

**List municipalities with population and area:**

```bash
python scripts/demo_list_municipalities.py
```

**Run KNN matching to find similar municipalities:**

```bash
python scripts/demo_knn_match.py
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request.

---

## 📬 Contact

For questions or suggestions, please contact [Joakim Storck](https://github.com/JoakimStorck).

---

*Senast uppdaterad: 2025-06-02. Se TODO.md för aktuell status och detaljer per arbetspaket.*
