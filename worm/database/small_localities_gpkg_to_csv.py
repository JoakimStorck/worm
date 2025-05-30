import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
import csv


# Läs in filen (GeoPackage)
gdf = gpd.read_file("data/Smaorter_2023.gpkg", layer="Smaorter_2023")

# Skapa en DataFrame med rätt engelska kolumnnamn
df = pd.DataFrame({
    "object_id": gdf["objectid"],
    "uuid": gdf["uuid"],
    "small_locality_id": gdf["smaort"],
    "municipal_code": gdf["kommun"],
    "municipality": gdf["kommunnamn"],
    "county_code": gdf["lan"],
    "county": gdf["lannamn"],
    "area_ha": gdf["area_ha"],
    "area_km2": gdf["area_ha"] / 100.0,
    "population": gdf["bef"],
    "year": gdf["ar"],
    "geom_wkt": gdf["geometry"].apply(lambda x: x.wkt)
})

# Spara till CSV (utan index)
df.to_csv("data/scb_small_localities.csv", index=False, encoding="utf-8", quoting=csv.QUOTE_NONNUMERIC)
