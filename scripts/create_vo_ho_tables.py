import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# run_loaders.py
from worm.database import loader

db_path = "data/worm.sqlite3"
handels_gpkg = "data/Handelsomraden_2020.gpkg"
verksamhets_gpkg = "data/Verksamhetsomraden_2020.gpkg"

print("=== Laddar in Handelsområden ===")
loader.load_handelsomraden(handels_gpkg, db_path)
print("=== Handelsområden inlästa ===\n")

print("=== Laddar in Verksamhetsområden ===")
loader.load_verksamhetsomraden(verksamhets_gpkg, db_path)
print("=== Verksamhetsområden inlästa ===\n")

