# worm/statistics/scb_employment_data.py

import requests
import pandas as pd
import os
import json

from worm import PROJECT_ROOT


def fetch_and_parse_scb_data(query_path=None, save_to_csv=False):
    """
    Hämtar SCB-data för flera kommuner och SNI-koder, där värden (anställda, arbetsställen) ligger som tvådelad lista i "values".
    Returnerar en DataFrame med Region, SNI2007, Year, Antal_Anstallda, Antal_Arbetsstallen.
    """
    if query_path is None:
        query_path = os.path.join(os.path.dirname(__file__), "px_query_verksamhetsomraden_sverige_2020.json")

    api_url = "https://api.scb.se/OV0104/v1/doris/sv/ssd/START/MI/MI0815/MI0815A/Verksamhetsomraden"

    with open(query_path, "r", encoding="utf-8") as f:
        query = json.load(f)

    response = requests.post(api_url, json=query)
    response.raise_for_status()
    data = response.json()

    log(f"Antal observationer: {len(data['data'])}")

    records = []
    for obs in data["data"]:
        region, sni, year = obs["key"]
        values = obs["values"]

        try:
            anstallda = int(values[0]) if values[0] != ".." else None
            arbetsstallen = int(values[1]) if values[1] != ".." else None
            records.append((region, sni, year, anstallda, arbetsstallen))
        except Exception as e:
            log(f"Fel i datapunkt: {obs} — {e}")

    df = pd.DataFrame(records, columns=["Region", "SNI2007", "Year", "Antal_Anstallda", "Antal_Arbetsstallen"])


    if save_to_csv:
        os.makedirs("data", exist_ok=True)
        df.to_csv("data/arbetsmarknadsstruktur_2020.csv", index=False)

    return df
