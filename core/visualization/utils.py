def gdf_to_bokeh_patches(gdf):
    # Konvertera polygonkolumn till format xs, ys för Bokeh.patches
    def get_xy(geom):
        if geom is None or geom.is_empty:
            return [], []
        if geom.geom_type == "MultiPolygon":
            # Ta första polygonen för simplicity
            geom = list(geom.geoms)[0]
        xs, ys = geom.exterior.xy
        return list(xs), list(ys)
    return {
        "xs": [get_xy(geom)[0] for geom in gdf.geometry],
        "ys": [get_xy(geom)[1] for geom in gdf.geometry],
    }

def gdf_points_to_xy(df, id_col="individual_id"):
    """
    Tar en GeoDataFrame med punkter och returnerar en vanlig DataFrame
    med x- och y-kolumner, utan geometry. Behåller övriga kolumner.
    """
    df = df.copy()
    if "geometry" in df.columns:
        df["x"] = df["geometry"].apply(lambda pt: pt.x)
        df["y"] = df["geometry"].apply(lambda pt: pt.y)
        df = df.drop(columns=["geometry"])
    # Om du vill försäkra dig om att id_col finns som sträng
    if id_col in df.columns:
        df[id_col] = df[id_col].astype(str)
    return df
