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


KOMMUN_FIL = "data/Arbetsmarknadsstatus kommun utbildningsniva.csv"
KOMMUN_TABELL = "employment_education_municipality"
KOMMUN_RUBRIK = re.compile(r"^(0000088[AH]) - .* (\d{4}M\d{2}) - \2$")


def las_arbetsmarknad_utbildning(csv_path=KOMMUN_FIL):
    """TAB6666 (BAS, november): sysselsatta och arbetslösa 20-65 år per kommun
    och grupperad utbildningsnivå (21, 3, 4, 5, 61, US). UseCodesAndTexts:
    cellerna är "kod - text" och innehåll och månad står i värdekolumnernas
    rubriker, som tas isär. Kommunerna är det enda regionslaget i uttaget."""
    rader, _ = las_rader(csv_path)
    df = pd.read_csv(io.StringIO("\n".join(rader)), dtype=str)
    kod = lambda c: str(c).split(" - ", 1)[0].strip()
    stub = {kod(c): c for c in df.columns if not KOMMUN_RUBRIK.match(c)}
    if not {"Region", "UtbildningsNiva"} <= set(stub):
        raise ValueError(f"{csv_path}: Region eller UtbildningsNiva saknas: {list(df.columns)}")
    varden = {KOMMUN_RUBRIK.match(c).group(1): c for c in df.columns if KOMMUN_RUBRIK.match(c)}
    if set(varden) != {"0000088A", "0000088H"}:
        raise ValueError(f"{csv_path}: väntade sysselsatta och arbetslösa, fick {list(varden)}")
    manad = {KOMMUN_RUBRIK.match(c).group(2) for c in df.columns if KOMMUN_RUBRIK.match(c)}
    if len(manad) != 1:
        raise ValueError(f"{csv_path}: väntade en månad, fick {sorted(manad)}")
    ut = pd.DataFrame({
        "municipal_code": df[stub["Region"]].map(kod),
        "level_group": df[stub["UtbildningsNiva"]].map(kod),
        "employed": pd.to_numeric(df[varden["0000088H"]], errors="raise").astype(int),
        "unemployed": pd.to_numeric(df[varden["0000088A"]], errors="raise").astype(int),
        "period": manad.pop()})
    if not ut["municipal_code"].str.fullmatch(r"\d{4}").all():
        raise ValueError(f"{csv_path}: annat än kommuner bland regionerna")
    return ut


def load_arbetsmarknad_utbildning(db_path="data/worm.sqlite3", csv_path=KOMMUN_FIL):
    df = las_arbetsmarknad_utbildning(csv_path)
    conn = sqlite3.connect(db_path)
    df.to_sql(KOMMUN_TABELL, conn, if_exists="replace", index=False)
    conn.close()
    print(f"[utbildning] {KOMMUN_TABELL}: {df.municipal_code.nunique()} kommuner, "
          f"{df.period.iloc[0]}, {int(df.employed.sum())} sysselsatta")


STUDIE_FIL = "data/Befolkning studiedeltagande utbildningsniva.csv"
STUDIE_TABELL = "population_study_education"
FLODE_FIL = "data/Utbildningsfloden kommun.csv"
FLODE_TABELL = "education_flows_municipality"
FLODE_MATT = {"000008QG": "population_1", "000008QH": "population_2", "000008QI": "net",
              "000008QJ": "age_in", "000008QK": "age_out", "000008QL": "in_migrants",
              "000008QM": "out_migrants", "000008QN": "graduated", "000008QO": "further_educated"}
FLODE_RUBRIK = re.compile(r"^(\w+) (\d{4}-\d{4})$")


def las_studiedeltagande(csv_path=STUDIE_FIL):
    """TAB3731 (riket): antal per kön, ålder, studiedeltagande, nivå och
    förvärvsarbete. Yngsta barnets ålder summeras bort -- inträdet behöver
    den inte -- och de fyra klasserna är en uppdelning, ingen total."""
    df = las_tabell(csv_path, {"Kon": "sex", "Alder": "age", "Studiedeltagande": "study",
                               "UtbildningsNiva": "level", "Sysselsattning": "employment",
                               "BarnAlder": "children"}, "population")
    return (df.groupby(["sex", "age", "study", "level", "employment", "year"],
                       as_index=False)["population"].sum())


def las_utbildningsfloden(csv_path=FLODE_FIL):
    """TAB6928: långt format med en rad per region, nivågrupp, åldersklass
    och mått. ".." -- flyttningar för riket, där de inte är definierade --
    blir ingen rad. Kontroll: befolkningen år 2 är år 1 plus nettot."""
    rader, _ = las_rader(csv_path)
    df = pd.read_csv(io.StringIO("\n".join(rader)), dtype=str)
    stub = ["Region", "Utbildngrupp", "KonAlderFodelseland"]
    if [c for c in stub if c not in df.columns]:
        raise ValueError(f"{csv_path}: väntade {stub}, fick {list(df.columns)}")
    varden = [c for c in df.columns if c not in stub]
    delar = {c: FLODE_RUBRIK.match(c) for c in varden}
    fel = [c for c, m in delar.items() if m is None or m.group(1) not in FLODE_MATT]
    if fel:
        raise ValueError(f"{csv_path}: okända värdekolumner {fel}")
    lang = df.melt(id_vars=stub, value_vars=varden, var_name="kol", value_name="value")
    lang["measure"] = lang["kol"].map(lambda c: FLODE_MATT[delar[c].group(1)])
    lang["period"] = lang["kol"].map(lambda c: delar[c].group(2))
    lang["value"] = pd.to_numeric(lang["value"].replace("..", None), errors="raise")
    lang = lang.dropna(subset=["value"])
    ut = pd.DataFrame({"municipal_code": lang["Region"].str.strip(),
                       "edu_group": lang["Utbildngrupp"].str.strip(),
                       "age_class": lang["KonAlderFodelseland"].str.strip(),
                       "measure": lang["measure"], "value": lang["value"].astype(int),
                       "period": lang["period"]}).reset_index(drop=True)
    kontrollera_floden(ut)
    return ut


def kontrollera_floden(ut):
    """Befolkningen år 2 ska vara år 1 plus nettot, i varje cell. Komponenterna
    summerar inte till nettot (dödsfall och ändrade uppgifter står inte i
    tabellen), så de prövas inte."""
    w = ut.pivot_table(index=["municipal_code", "edu_group", "age_class", "period"],
                       columns="measure", values="value", aggfunc="first")
    saknas = {"population_1", "population_2", "net"} - set(w.columns)
    if saknas:
        raise ValueError(f"TAB6928 saknar måtten {sorted(saknas)}")
    avvik = w[(w.population_1 + w.net) != w.population_2]
    if len(avvik):
        raise ValueError(f"TAB6928: befolkningen år 2 är inte år 1 plus nettot i "
                         f"{len(avvik)} celler, t.ex. {avvik.index[0]}")


def load_intradet(db_path="data/worm.sqlite3"):
    conn = sqlite3.connect(db_path)
    for tabell, df in ((STUDIE_TABELL, las_studiedeltagande()),
                       (FLODE_TABELL, las_utbildningsfloden())):
        df.to_sql(tabell, conn, if_exists="replace", index=False)
        print(f"[utbildning] {tabell}: {len(df)} rader")
    conn.close()


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
