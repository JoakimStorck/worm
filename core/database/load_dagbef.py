"""
core/database/load_dagbef.py
----------------------------
Anställda med arbetsplats i kommunen (DAGBEFOLKNING) efter yrke (SSYK3),
näringsgren (SNI 2007, grov nivå) och kön, ur TAB4436, till tabellen
employment_workplace_occupation_sni.

VARFÖR. Arbetsställenas branschandelar togs ur employment_deso_sni, som är
invånarnas bransch (nattbefolkning). Jobben ligger på arbetsställena, och för
en utpendlingskommun skiljer sig de två: i Orsa är tillverkningen 5,5 procent
av jobben men 9,7 procent av invånarna, eftersom de arbetar i Mora.

FILEN (scripts/fetch_data.py, "dagbef yrke bransch"). Rubriken är
Region,Yrke2012,SNI2007,Kon,Tid,<innehållskod> -- värdekolumnen heter efter
innehållskoden, inte efter året. Regionerna är en hierarki utan totalrader:
00 riket, tvåsiffriga län, fyrsiffriga kommuner, 99 län okänt, 9999 kommun
okänd. Läsaren VÄLJER kommunnivån; att summera över nivåerna hade räknat
varje anställd tre gånger. "kommun okänd" är ingen kommun och tas inte med.
Restposterna yrke 0002 (okänt) och SNI 00 (okänd verksamhet) behålls; det är
konsumenten som avgör vad de betyder.

Nollceller släpps. Filen har 1,5 miljoner celler, och de flesta kombinationer
av kommun, yrke och bransch är tomma.

    python -m core.database.load_dagbef "data/Anstallda dagbef yrke bransch kommun.csv"
"""
import io
import sqlite3
import sys

import pandas as pd

from core.database.utils import las_rader

TABELL = "employment_workplace_occupation_sni"
STUB = ["Region", "Yrke2012", "SNI2007", "Kon", "Tid"]


def las_dagbef_yrke_bransch(csv_path):
    rader, _ = las_rader(csv_path)
    df = pd.read_csv(io.StringIO("\n".join(rader)), dtype=str)
    saknas = [k for k in STUB if k not in df.columns]
    varden = [k for k in df.columns if k not in STUB]
    if saknas or len(varden) != 1:
        raise ValueError(f"{csv_path}: väntade kolumnerna {STUB} plus EN värdekolumn, "
                         f"fick {list(df.columns)}")
    df["employed"] = pd.to_numeric(df[varden[0]], errors="raise").astype(int)
    kommun = df["Region"].str.fullmatch(r"\d{4}") & (df["Region"] != "9999")
    df = df[kommun & (df["employed"] > 0)]
    ut = pd.DataFrame({
        "municipal_code": df["Region"],
        "ssyk_code": df["Yrke2012"],
        "sni_code": df["SNI2007"],
        "sex": df["Kon"],
        "year": df["Tid"].astype(int),
        "employed": df["employed"],
    })
    return ut.reset_index(drop=True)


def load_dagbef_yrke_bransch(csv_path, db_path="data/worm.sqlite3"):
    df = las_dagbef_yrke_bransch(csv_path)
    conn = sqlite3.connect(db_path)
    df.to_sql(TABELL, conn, if_exists="replace", index=False)
    conn.close()
    print(f"[dagbef] {len(df)} rader, {df.municipal_code.nunique()} kommuner, "
          f"{df.ssyk_code.nunique()} yrken, {df.sni_code.nunique()} branscher, "
          f"{int(df.employed.sum())} anställda, år {sorted(df.year.unique())}")
    return len(df)


if __name__ == "__main__":
    load_dagbef_yrke_bransch(*sys.argv[1:2])
