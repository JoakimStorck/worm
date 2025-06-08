import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worm.statistics.scb_employment_data import fetch_and_parse_scb_data

if __name__ == "__main__":
    df = fetch_and_parse_scb_data(save_to_csv=True)
    log(df.head())

