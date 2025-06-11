import geopandas as gpd
import pandas as pd
import csv

# Ange rätt sökväg och lager
gpk_path = "data/DeSO_2025.gpkg"
layer = "DeSO_2025"
csv_path = "data/municipalities_from_deso.csv"

def fix_swedish_encoding(s):
    if not isinstance(s, str):
        return s
    replacements = {
        "Ã¥": "å", "Ã¤": "ä", "Ã¶": "ö",
        "Ã…": "Å", "Ã„": "Ä", "Ã–": "Ö",
        "Ã¼": "ü", "Ãœ": "Ü", "Ã–": "Ö",
        "Ã©": "é", "Ãˆ": "È"
    }
    for wrong, right in replacements.items():
        s = s.replace(wrong, right)
    return s.strip()

# Läs in DeSO-polygoner
gdf = gpd.read_file(gpk_path, layer=layer)

# Unionera per kommunkod
municipalities = gdf.dissolve(
    by="kommunkod", 
    as_index=False, 
    aggfunc={
        "kommunnamn": "first"  # Tar första kommunnamn per kod
    }
)

# Beräkna area
municipalities["area_ha"] = municipalities["geometry"].area / 10000
municipalities["area_km2"] = municipalities["geometry"].area / 1e6

# Ta fram kommunkod och namn
df = pd.DataFrame({
    "municipal_code": municipalities["kommunkod"],
    "municipality": municipalities["kommunnamn"],
    "area_ha": municipalities["area_ha"].round(2),
    "area_km2": municipalities["area_km2"].round(4),
    "geom_wkt": municipalities["geometry"].apply(lambda x: x.wkt)
})

# Ordna svenska tecken
for col in df.select_dtypes(include="object").columns:
    df[col] = df[col].apply(fix_swedish_encoding)

# Spara som UTF-8 CSV
df.to_csv(csv_path, index=False, encoding="utf-8", quoting=csv.QUOTE_NONNUMERIC)
log(f"{len(df)} kommuner sparade till {csv_path}")
