"""
core/database/load_lediga_jobb.py
---------------------------------
Lediga jobb per 100 anställningar och län, hela ekonomin, ur TAB6605
(konjunkturstatistik över lediga jobb), till tabellen vacancy_rate_county.

VARFÖR. Jobbmålet ur pendlingsmatrisen räknar sysselsatta, alltså besatta
jobb, och modellen behöver positioner: de besatta plus de lediga
(docs/stockarna.md). Vakansgraden är det som saknas mellan dem.

FILEN (scripts/fetch_data.py, "Lediga jobb"). Stubben är LedJobbTyp och
AARegion; innehåll och kvartal hamnar i värdekolumnernas rubriker, en kolumn
per par, som "0000081B - antal, per anställning 2024K2 - 2024K2" (fallgrop 3
i CLAUDE.md). Läsaren tar isär rubriken i stället för att lita på ordningen.
Cellerna är "kod - text" (UseCodesAndTexts). Saknade värden är "..".

Regionerna är riket (00), län (tvåsiffriga), riksområden (SE…) och NUTS2 --
utan totalrader att filtrera, men med nivåer som överlappar. Läsaren VÄLJER
länen; de övriga nivåerna är andra aggregat av samma anställningar.

Två typer behålls: LJtotA (lediga jobb totalt) och LJomgA (med omgående
tillträde). Konsumenten väljer; modellens öppna vakans svarar mot totalt.

    python -m core.database.load_lediga_jobb "data/Lediga jobb per anstallning lan.csv"
"""
import io
import re
import sqlite3
import sys

import pandas as pd

from core.database.utils import las_rader

TABELL = "vacancy_rate_county"
STUB = ["LedJobbTyp", "AARegion"]
VARDE = "0000081B"          # antal per anställning
MARGINAL = "0000081C"       # dess osäkerhetsmarginal
RUBRIK = re.compile(r"^(\w+) - .* (\d{4}K[1-4]) - \2$")


def _kod(cell):
    return str(cell).split(" - ", 1)[0].strip()


def las_lediga_jobb(csv_path):
    rader, _ = las_rader(csv_path)
    df = pd.read_csv(io.StringIO("\n".join(rader)), dtype=str)
    stub = [c for c in df.columns if _kod(c) in STUB]
    if len(stub) != len(STUB):
        raise ValueError(f"{csv_path}: väntade stubben {STUB}, fick {list(df.columns)}")
    langt = df.melt(id_vars=stub, var_name="rubrik", value_name="varde")
    delar = langt["rubrik"].str.extract(RUBRIK)
    if delar.isna().any().any():
        fel = sorted(langt.loc[delar.isna().any(axis=1), "rubrik"].unique())[:3]
        raise ValueError(f"{csv_path}: rubriker utan innehåll och kvartal: {fel}")
    langt["innehall"], langt["kvartal"] = delar[0], delar[1]
    typ_kol = next(c for c in stub if _kod(c) == "LedJobbTyp")
    reg_kol = next(c for c in stub if _kod(c) == "AARegion")
    langt["vacancy_type"] = langt[typ_kol].map(_kod)
    langt["county_code"] = langt[reg_kol].map(_kod)
    langt = langt[langt["county_code"].str.fullmatch(r"\d{2}")
                  & (langt["county_code"] != "00")]
    langt["varde"] = pd.to_numeric(langt["varde"].replace("..", None), errors="raise")
    ut = langt.pivot_table(index=["county_code", "vacancy_type", "kvartal"],
                           columns="innehall", values="varde", aggfunc="first")
    saknas = {VARDE, MARGINAL} - set(ut.columns)
    if saknas:
        raise ValueError(f"{csv_path}: innehållen {sorted(saknas)} saknas")
    ut = ut.rename(columns={VARDE: "per_100", MARGINAL: "margin"})[["per_100", "margin"]]
    ut = ut.reset_index().rename(columns={"kvartal": "quarter"})
    ut = ut[ut["per_100"].notna()]
    ut.columns.name = None
    return ut.reset_index(drop=True)


def load_lediga_jobb(csv_path, db_path="data/worm.sqlite3"):
    df = las_lediga_jobb(csv_path)
    conn = sqlite3.connect(db_path)
    df.to_sql(TABELL, conn, if_exists="replace", index=False)
    conn.close()
    print(f"[lediga jobb] {len(df)} rader, {df.county_code.nunique()} län, "
          f"kvartal {df.quarter.min()}-{df.quarter.max()}")
    return len(df)


if __name__ == "__main__":
    load_lediga_jobb(*sys.argv[1:2])
