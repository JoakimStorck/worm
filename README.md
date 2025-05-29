# WORM – Worker-Occupation-Region Model

WORM is a modular Python framework designed for analyzing labor markets, commuting patterns, and regional structures. It enables integration of statistical data, geographic hierarchies, and synthetic modeling to support research and planning at municipal, regional, and national levels.

---

## 🌟 Vision

To provide a transparent, scalable, and data-driven simulation environment for studying the Swedish labor market and occupational dynamics, supporting research, policy analysis, and educational use.

The project bridges the gap between real-world labor market data and agent-based modeling, enabling detailed yet flexible experiments with geography, occupations, workforce, and commuting—both for current Swedish conditions and hypothetical future scenarios.

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
