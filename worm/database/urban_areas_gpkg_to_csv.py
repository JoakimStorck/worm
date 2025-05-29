import pandas as pd
from shapely.geometry import shape
import fiona

rows = []
with fiona.open("data/Tatorter_2023.gpkg", layer="Tatorter_2023") as src:
    for feat in src:
        p = feat["properties"]
        geom_wkt = shape(feat["geometry"]).wkt
        rows.append({
            "object_id": p["objectid"],
            "uuid": p["uuid"],
            "urban_area_id": p["tatortskod"],
            "urban_area": p["tatort"],
            "municipality_code": p["kommun"],
            "municipality": p["kommunnamn"],
            "county_code": p["lan"],
            "county": p["lannamn"],
            "area_ha": p["area_ha"],
            "population": p["bef"],
            "year": int(p["ar"]),
            "valid_from": p["validfrom"],
            "valid_to": p["validto"],
            "geom_wkt": geom_wkt
        })

df = pd.DataFrame(rows)
df.to_csv("urban_areas_2023.csv", index=False, encoding="utf-8")
