import pandas as pd

def clean_and_tidy_employment_data_municipality(input_file, output_file, year=2020, encoding="utf-8"):
    # Läs in filen – antag utf-8, byt till latin1 om du får fel
    try:
        df = pd.read_csv(input_file, encoding=encoding)
    except UnicodeDecodeError:
        df = pd.read_csv(input_file, encoding="latin1")

    # Byt namn på kolumner till engelska (anpassa om din fil har annan struktur)
    df = df.rename(columns={
        "Region": "municipal_code",
        "SNI2007": "sni_code",
        "Year": "year",
        "Antal_Anstallda": "employed",
        "Antal_Arbetsstallen": "workplaces"
    })

    # Om år inte finns, lägg till det explicit
    if "year" not in df.columns:
        df["year"] = year

    # Välj och ordna kolumner enligt tabellschemat
    outcols = [
        "municipal_code", "year", "sni_code", "employed", "workplaces"
    ]
    for col in outcols:
        if col not in df.columns:
            df[col] = None

    df = df[outcols]

    # Spara till CSV
    df.to_csv(output_file, index=False, encoding="utf-8")

# Exempel på körning:
clean_and_tidy_employment_data_municipality(
    "data/arbetsmarknadsstruktur_2020.csv",
    output_file="data/employment_municipality_sni_2020.csv",
    year=2020
)
