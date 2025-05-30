import geopandas as gpd
import pandas as pd
import csv

# Ange sökvägen till din GeoPackage-fil och namn på lagret
gpk_path = "data/DeSO_2025.gpkg"
layer = "DeSO_2025"
csv_path = "data/scb_deso.csv"

# Läs in lagret
gdf = gpd.read_file(gpk_path, layer=layer)

# Skapa dataframe med engelska kolumnnamn (lägg gärna till/justera vid behov!)
df = pd.DataFrame({
    "object_id": gdf["objectid"],
    "object_identity": gdf["objektidentitet"],
    "deso_code": gdf["desokod"],
    "regso_code": gdf["regsokod"],
    "county_code": gdf["lanskod"],
    "municipal_code": gdf["kommunkod"],
    "municipality": gdf["kommunnamn"],
    "version": gdf["version"],
    "area_ha": gdf["geometry"].area / 10000,      # Om area_ha inte finns i data
    "area_km2": gdf["geometry"].area / 1e6,       # Area i km2 (1 km^2 = 1 000 000 m^2)
    "geom_wkt": gdf["geometry"].apply(lambda x: x.wkt)
})

# Om area_ha finns i filen (SCB brukar ibland leverera den direkt), använd den:
if "area_ha" in gdf.columns:
    df["area_ha"] = gdf["area_ha"]
    df["area_km2"] = gdf["area_ha"] / 100.0

# Spara till UTF-8 CSV
df.to_csv(csv_path, index=False, encoding="utf-8", quoting=csv.QUOTE_NONNUMERIC)

print(f"Sparade {len(df)} rader till {csv_path}")
