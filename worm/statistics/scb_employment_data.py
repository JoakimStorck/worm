# worm/statistics/scb_employment_data.py

import requests
import pandas as pd
import os
import json

QUERY_PATH = os.path.join(os.path.dirname(__file__), "px_query_verksamhetsomraden.json")
API_URL = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/MI/MI0815/MI0815A/Verksamhetsomraden"

def fetch_and_parse_scb_data():
    """
    Hämtar SCB-data för antal arbetsställen och anställda per kommun och SNI-grupp.
    Returnerar en pandas DataFrame med resultatet.
    """
    with open(QUERY_PATH, encoding="utf-8") as f:
        query = json.load(f)

    response = requests.post(API_URL, json=query)
    response.raise_for_status()

    data = response.json()
    records = []
    for obs, value in zip(data["data"], data["data"]):
        kommun = obs["key"].get("Region") or obs["key"][0]
        sni = obs["key"].get("Verksamhet (SNI 2007)") or obs["key"][1]
        ar = obs["key"].get("Tid") or obs["key"][2]
        varde = value["values"][0]
        records.append((kommun, sni, ar, int(varde)))

    df = pd.DataFrame(records, columns=["Kommun", "SNI", "Ar", "Varde"])
    return df
