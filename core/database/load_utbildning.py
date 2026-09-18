"""
core/database/load_utbildning.py
--------------------------------
Utbildningstabellerna för steg 4 (docs/utbildningsmodell.md, "Data för
dragningen"): tre tvåvägsmarginaler av P(yrke, nivå, inriktning | ålder, kön).

    TAB4359  anställda per yrke x inriktning x ålder x kön   -> employment_occupation_field
    TAB4360  anställda per yrke x nivå x ålder x kön         -> employment_occupation_level
    TAB655   befolkningen per kön x ålder x nationell bakgrund
             x nivå x inriktning                             -> population_level_field

FILERNA (scripts/fetch_data.py) har bara koder och en värdekolumn. Tiden står
som kolumnen Tid när PxWeb hörsammar placeringen, annars i värdekolumnens
rubrik ("000006XQ 2024", fallgrop 3 i CLAUDE.md); läsaren tar båda.

INGA TOTALRADER. Yrkets 0002 (okänt), inriktningens 9 (okänd) och nivåns US
(uppgift saknas) är restposter, inte summor. De behålls; konsumenten avgör
vad de betyder.

OLIKA POPULATIONER. TAB4359 och TAB4360 räknar anställda i femårsklasser
16-24 ... 65-69; TAB655 hela befolkningen 16-74 i tioårsklasser. Läsaren
jämnar inte ut skillnaden -- åldersklassen står kvar som SCB skrev den.

KONTROLL. TAB4359 och TAB4360 räknar samma anställda och ska ha identiska
yrkestotaler per ålder och kön. kontrollera_yrkestotaler kastar om de inte
har det; då är ett av uttagen fel år eller ofullständigt.

    python -m core.database.load_utbildning
"""
import io
import re
import sqlite3

import pandas as pd

from core.database.utils import las_rader

FILER = {
    "employment_occupation_field": (
        "data/Anstallda yrke utbildningsinriktning.csv",
        {"Yrke2012": "ssyk_code", "UtbinriktnSUN2020": "field",
         "Alder": "age_class", "Kon": "sex"}, "employed"),
    "employment_occupation_level": (
        "data/Anstallda yrke utbildningsniva.csv",
        {"Yrke2012": "ssyk_code", "UtbNivaSun2020": "level",
         "Alder": "age_class", "Kon": "sex"}, "employed"),
    "population_level_field": (
        "data/Befolkning utbildningsniva inriktning.csv",
        {"Kon": "sex", "Alder": "age_class", "NationellBakgrund": "background",
         "UtbildningsNiva": "level", "UtbinriktnSUN2020": "field"}, "population"),
}
AR_I_RUBRIK = re.compile(r"^\S+\s+(\d{4})$")


def las_tabell(csv_path, kolumner, varde):
    """Läser en av filerna till långt format med kolumnerna i `kolumner`
    omdöpta, plus year och `varde`."""
    rader, _ = las_rader(csv_path)
    df = pd.read_csv(io.StringIO("\n".join(rader)), dtype=str)
    saknas = [k for k in kolumner if k not in df.columns]
    if saknas:
        raise ValueError(f"{csv_path}: kolumnerna {saknas} saknas, fick {list(df.columns)}")
    ovriga = [c for c in df.columns if c not in kolumner and c != "Tid"]
    if len(ovriga) != 1:
        raise ValueError(f"{csv_path}: väntade EN värdekolumn, fick {ovriga}")
    vk = ovriga[0]
    if "Tid" in df.columns:
        ar = df["Tid"].astype(int)
    else:
        m = AR_I_RUBRIK.match(vk)
        if m is None:
            raise ValueError(f"{csv_path}: året står varken i Tid eller i rubriken {vk!r}")
        ar = int(m.group(1))
    ut = df[list(kolumner)].rename(columns=kolumner).copy()
    for c in ut.columns:
        ut[c] = ut[c].str.strip()
    ut["year"] = ar
    ut[varde] = pd.to_numeric(df[vk], errors="raise").astype(int)
    return ut.reset_index(drop=True)


def kontrollera_yrkestotaler(inriktning, niva):
    """TAB4359 och TAB4360 räknar samma anställda: yrkestotalerna per ålder
    och kön ska vara identiska. Kastar annars."""
    nyckel = ["ssyk_code", "age_class", "sex", "year"]
    a = inriktning.groupby(nyckel)["employed"].sum()
    b = niva.groupby(nyckel)["employed"].sum()
    a, b = a.align(b, fill_value=0)
    avvik = (a - b)[a != b]
    if len(avvik):
        raise ValueError(
            f"TAB4359 och TAB4360 har olika yrkestotaler i {len(avvik)} celler "
            f"(t.ex. {avvik.index[0]}: {int(a[avvik.index[0]])} mot "
            f"{int(b[avvik.index[0]])}). Samma år och fullständiga uttag krävs.")


def load_utbildning(db_path="data/worm.sqlite3", filer=FILER):
    tabeller = {}
    for tabell, (fil, kolumner, varde) in filer.items():
        tabeller[tabell] = las_tabell(fil, kolumner, varde)
    kontrollera_yrkestotaler(tabeller["employment_occupation_field"],
                             tabeller["employment_occupation_level"])
    conn = sqlite3.connect(db_path)
    for tabell, df in tabeller.items():
        df.to_sql(tabell, conn, if_exists="replace", index=False)
        print(f"[utbildning] {tabell}: {len(df)} rader, år {sorted(df.year.unique())}, "
              f"{int(df.iloc[:, -1].sum())} personer")
    conn.close()


if __name__ == "__main__":
    load_utbildning()
