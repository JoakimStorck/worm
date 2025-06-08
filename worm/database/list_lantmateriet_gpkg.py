import requests

# Hämta "items" (alla versioner)
url = "https://api.lantmateriet.se/stac-vektor/v1/collections/kommun-lan-rike/items"
resp = requests.get(url)
items = resp.json()["features"]

# Leta efter GPKG (GeoPackage) bland asset-länkarna
for item in items:
    assets = item["assets"]
    for asset in assets.values():
        if asset["type"] == "application/geopackage+sqlite3":
            log("GeoPackage-länk:", asset["href"])
