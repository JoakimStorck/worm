import numpy as np

import geopandas as gpd
from shapely.geometry import Point

from core.statistics.log import log 

def assign_deso_code(df, deso_gdf, x_col="x", y_col="y"):
    points = gpd.GeoSeries([Point(x, y) for x, y in zip(df[x_col], df[y_col])], crs=deso_gdf.crs)
    df = df.copy()
    df["geometry"] = points
    points_gdf = gpd.GeoDataFrame(df, geometry="geometry", crs=deso_gdf.crs)

    log(f"Exempel på individer:\n{df.head()}")
    log(f"Exempel på DeSO-zoner: \n{deso_gdf.head()}")
    log(f"Individers min/max x/y: {df['x'].min()}, {df['x'].max()}, {df['y'].min()}, {df['y'].max()}")
    log(f"DeSO min/max x/y: {deso_gdf.geometry.bounds.min()}, {deso_gdf.geometry.bounds.max()}")

    # Spatial join: vilket DeSO hör punkten till?
    joined = gpd.sjoin(points_gdf, deso_gdf[["deso_code", "geometry"]], how="left", predicate="within")
    log(f"Kolumner i joined efter spatial join: {joined.columns}")

    return joined["deso_code"].values  # returnerar en array/serie med deso_code

def random_points_in_polygon(polygon, n_points):
    points = []
    minx, miny, maxx, maxy = polygon.bounds
    while len(points) < n_points:
        x, y = np.random.uniform(minx, maxx), np.random.uniform(miny, maxy)
        p = Point(x, y)
        if polygon.contains(p):
            points.append((x, y))
    return points
