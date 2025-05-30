import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worm.database import schema, loader

# Create the database schema and load initial data
schema.create_schema()
loader.load_municipalities("data/scb_municipalities.csv")
loader.load_urban_areas("data/scb_urban_areas.csv")
loader.load_small_localities("data/scb_small_localities.csv")
loader.load_deso("data/scb_deso.csv")
loader.load_employment_deso_sni("data/Sysselsatta 15-74 år region, näringsgren SNI 2007 och år.csv")
loader.load_employment_municipality_sni("data/arbetsmarknadsstruktur_2020.csv")
