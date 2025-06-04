# geoworld.py


import sqlite3
import geopandas as gpd
import pandas as pd
from shapely import wkt

# Bas-klass för alla geografiska entiteter
class GeoEntity:
    def __init__(self, code, name, polygon, **kwargs):
        self.code = code
        self.name = name
        self.polygon = polygon
        for k, v in kwargs.items():
            setattr(self, k, v)
    def __repr__(self):
        return f"{self.__class__.__name__}(code={self.code}, name={self.name})"

class Municipality(GeoEntity): pass
class UrbanArea(GeoEntity): pass
class SmallLocality(GeoEntity): pass
class DeSOZone(GeoEntity): pass
class BusinessZone(GeoEntity): pass
class CommercialZone(GeoEntity): pass

# Hitta första existerande kolumn i en lista av kandidater
def pick_first_existing(columns, candidates, fallback_idx=0):
    for col in candidates:
        if col in columns:
            return col
    return columns[fallback_idx]

# GeoWorld-klass som hanterar geografiska data från en SQLite-databas
# och tillhandahåller metoder för att hämta olika geografiska lager.
class GeoWorld:
    def __init__(self, db_path):
        self.db_path = db_path
        self._cache = {}

    def get_layer(self, table_name, wkt_col="geom_wkt"):
        """
        Hämtar ett geografiskt lager som GeoDataFrame.
        Laddas från databas första gången, därefter från cache.
        """
        import sqlite3
        query = f"SELECT * FROM {table_name}"
        conn = sqlite3.connect(self.db_path)      # Skapa connection-objekt!
        df = pd.read_sql(query, conn)             # Skicka connection till read_sql!
        conn.close()
        gdf = gpd.GeoDataFrame(df, geometry=gpd.GeoSeries.from_wkt(df[wkt_col]))
        self._cache[table_name] = gdf
        return gdf


    # Snygg wrapper för att få attributstil, om du vill:
    @property
    def municipalities(self):
        return self.get_layer("municipalities")

    @property
    def urban_areas(self):
        return self.get_layer("urban_areas")

    @property
    def small_localities(self):
        return self.get_layer("small_localities")

    @property
    def deso_zones(self):
        return self.get_layer("deso")

    @property
    def business_zones(self):
        return self.get_layer("business_zones")

    @property
    def commercial_zones(self):
        return self.get_layer("commercial_zones")


    def _load_municipalities(self):
        return self._load_entities(
            "municipalities",
            code_col="municipal_code",
            name_col="municipality",
            entity_class=Municipality,
        )

    def _load_urban_areas(self):
        return self._load_entities(
            "urban_areas",
            code_col="object_id",
            name_col="urban_area",
            entity_class=UrbanArea,
        )

    def _load_small_localities(self):
        return self._load_entities(
            "small_localities",
            code_col="object_id",
            name_col="small_locality_id",
            entity_class=SmallLocality,
        )

    def _load_deso_zones(self):
        return self._load_entities(
            "deso",
            code_col="object_id",
            name_col="deso_code",
            entity_class=DeSOZone,
        )

    def _load_business_zones(self):
        return self._load_entities(
            "business_zones",
            code_col="id",
            name_col="zone_code",
            entity_class=BusinessZone,
        )

    def _load_commercial_zones(self):
        return self._load_entities(
            "commercial_zones",
            code_col="id",
            name_col="zone_code",
            entity_class=CommercialZone,
        )


    def _columns(self, table):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql(f"SELECT * FROM {table} LIMIT 1", conn)
        conn.close()
        return df.columns.tolist()

    def _load_entities(self, table, code_col, name_col, entity_class):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql(f"SELECT * FROM {table}", conn)
        conn.close()
        entities = {}
        for _, row in df.iterrows():
            code = str(row[code_col]).strip()
            name = str(row[name_col]).strip() if row[name_col] is not None else ""
            polygon = wkt.loads(row["geom_wkt"])
            extra = {k: row[k] for k in row.index if k not in [code_col, name_col, "geom_wkt"]}
            entities[code] = entity_class(code, name, polygon, **extra)
        return entities


    # Exempel på funktion: Hämta alla DeSO för en kommun
    def get_deso_in_municipality(self, municipal_code):
        return [z for z in self.deso_zones.values() if hasattr(z, 'municipal_code') and z.municipal_code == municipal_code]
