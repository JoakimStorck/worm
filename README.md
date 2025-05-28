````markdown
# WORM – Workforce and Regional Modeling

WORM is a modular Python framework designed for analyzing labor markets, commuting patterns, and regional structures. It facilitates the integration of statistical data, geographic hierarchies, and synthetic modeling to support research and planning at municipal, regional, and national levels.

## 🚀 Features

- Modular architecture with clear separation of concerns
- Integration with SCB (Statistics Sweden) data
- SQLite backend for local data storage
- YAML support for structured geographic definitions
- K-Nearest Neighbors (KNN) algorithms for typology matching
- Extensible classes for municipalities, regions, zones, and nations
- Demo scripts for data import, analysis, and synthetic generation

## 📦 Project Structure

```plaintext
worm/
├── data/                        # Raw data, imported/exported CSV, YAML, SQLite
│   ├── scb_municipalities.csv
│   ├── scb_sni_by_municipality.csv
│   ├── worm.sqlite3
│   └── ...
├── worm/
│   ├── __init__.py
│   ├── database/                # SQLite handling
│   │   ├── __init__.py
│   │   ├── schema.py            # Creates and migrates database structure
│   │   ├── loader.py            # Import/export functions to/from DB
│   │   └── query.py             # Standard queries/utilities for SELECT etc.
│   ├── geography/               # Geographic models and utilities
│   │   ├── __init__.py
│   │   ├── municipality.py
│   │   ├── region.py
│   │   ├── nation.py
│   │   ├── zone.py
│   │   └── geo_utils.py
│   ├── yaml_io/                 # YAML handling (import, export, validation)
│   │   ├── __init__.py
│   │   └── loader.py
│   ├── knn/                     # KNN algorithms and related analysis
│   │   ├── __init__.py
│   │   └── municipality_knn.py
│   └── utils/                   # Helper functions, conversion, validation
│       ├── __init__.py
│       └── helpers.py
├── scripts/                     # Executable demo and helper scripts
│   ├── demo_fetch_scb_data.py
│   ├── demo_sqlite_init.py
│   ├── demo_list_municipalities.py
│   ├── demo_knn_match.py
│   ├── demo_generate_synthetic_sni.py
│   └── ...
├── tests/                       # Unit tests (pytest, unittest etc.)
│   └── ...
├── docs/                        # Documentation, README, TODO
│   ├── README.md
│   ├── TODO.md
│   └── ...
├── .gitignore
├── setup.py                     # (or pyproject.toml if you want to package)
└── requirements.txt
````

## 🛠️ Installation

```bash
git clone https://github.com/JoakimStorck/worm.git
cd worm
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 📊 Example Usage

Initialize the SQLite database and import SCB data:

```bash
python scripts/demo_sqlite_init.py
```

List municipalities with population and area:

```bash
python scripts/demo_list_municipalities.py
```

Run KNN matching to find similar municipalities:

```bash
python scripts/demo_knn_match.py
```

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

## 🤝 Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## 📬 Contact

For questions or suggestions, please contact [Joakim Storck](https://github.com/JoakimStorck).

```

