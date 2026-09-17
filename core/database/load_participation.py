"""Arbetskraft och befolkning per åldersklass ur SCB:s BAS-statistik.

Underlaget för vilka årskullar arbetskraften bor i. Utan det fördelas en
given arbetskraft platt över hela det arbetsföra intervallet, vilket ger
sextonåringar samma deltagande som fyrtioåringar och sextiosexåringar samma
som femtioåringar. Felet är inte en avrundning: i Ovansiljan hamnar omkring
800 personer i årskullar som i verkligheten knappt deltar, och eftersom
kohorterna närmast riktåldern då ligger fulltaligt i arbetskraften blir
avgångsflödet systematiskt för stort.

ÅLDERSKLASSERNA LAGRAS SOM SCB REDOVISAR DEM. Tabellen har femårsgrupper
(16-19, 20-24, ..., 60-64, 65-69, 70-74) och därutöver de överlappande
aggregaten 16-64, 16-65 och 16-66. Aggregaten är inte redundanta:
differenserna mellan dem ger arbetskraften vid 65 respektive 66 år, som inte
finns som egna klasser i någon av BAS-tabellerna. Just de åldrarna avgör hur
många som lämnar vid riktåldern, så de måste finnas. Uträkningen görs där
profilen byggs, inte här -- läsaren läser.

TOTALRADER. Kön och födelseregion har egna totalvärden ("1+2" respektive
"tot"), som uttaget väljer. Raderna ska alltså FILTRERAS, inte summeras, och
uttaget hämtar bara totalerna. Samma konvention som pendlingsfilen och
motsatsen till yrkesregistrets uttag.

RÖJANDESKYDD. BAS är skyddad med en statistisk metod, och SCB påpekar att
redovisade totaler inte alltid är lika med summan av de redovisade delarna.
En differens mellan två aggregat kan därför bli negativ i en liten kommun.
Det hanteras där profilen byggs.
"""
import re

import pandas as pd
import sqlite3

from core.database.utils import kommunkod, las_rader

# "16-19", "060-64" (SCB:s egen nollutfyllnad), "70-74", "16-66"
KLASS = re.compile(r"^0?(\d{2})-(\d{2})$")


def _sep(rader):
    huvud = "\n".join(rader[:20])
    return ";" if huvud.count(";") > huvud.count(",") else ","


def _kolumn(df, *nyckelord):
    for c in df.columns:
        lc = str(c).strip().lower()
        for n in nyckelord:
            if lc == n or lc.startswith(n):
                return c
    return None


def normalisera_klass(v):
    """"060-64" -> "60-64". SCB nollutfyller för att sortera rätt, och den
    nollan skulle annars ge en egen klass som ingen matchar mot."""
    m = KLASS.match(str(v).strip())
    if not m:
        return None
    return f"{int(m.group(1))}-{int(m.group(2))}"


def las_arbetskraft_per_alder(csv_path):
    """DataFrame med municipal_code, year, age_group, in_labour_force, total."""
    # TECKENKODNINGEN ÄR INTE GIVEN. Statistikdatabasens CSV är latin-1 när
    # svaret bär klartext. Befolkningsuttaget klarade sig som UTF-8 bara
    # därför att det inte innehåller några å, ä eller ö alls -- det här gör
    # det, eftersom rubrikerna bär både kod och text.
    rader, kodning = las_rader(csv_path)
    sep = _sep(rader)
    start = next((i for i, r in enumerate(rader[:25])
                  if "region" in r.lower() and "alder" in r.lower().replace("ålder", "alder")),
                 None)
    if start is None:
        raise ValueError("Hittar ingen rubrikrad med kolumnerna region och ålder")
    df = pd.read_csv(csv_path, sep=sep, skiprows=start, dtype=str,
                     encoding=kodning, engine="python")
    df.columns = [str(c).strip().strip('"') for c in df.columns]

    reg = _kolumn(df, "region", "kommun")
    ald = _kolumn(df, "alder", "ålder")
    tid = _kolumn(df, "tid", "år")
    if reg is None or ald is None or tid is None:
        raise ValueError(f"Saknar region-, ålders- eller tidskolumn i {csv_path}: "
                         f"{list(df.columns)}")

    # TVÅ VÄRDEKOLUMNER, och ordningen är inte given. Arbetskraften och
    # befolkningen skiljs åt på innehållskoden i rubriken, inte på position:
    # en fil där de bytt plats hade annars gjort deltagandet till sin egen
    # invers utan att något klagar.
    dimensioner = {str(reg).lower(), str(ald).lower(), str(tid).lower(),
                   "kon", "kön", "fodelseregion", "födelseregion"}
    varden = [c for c in df.columns if str(c).strip().lower() not in dimensioner]
    arbetskraft = next((c for c in varden if "arbetskraft" in str(c).lower()), None)
    totalt = next((c for c in varden
                   if "total" in str(c).lower() and c != arbetskraft), None)
    if arbetskraft is None or totalt is None:
        raise ValueError(
            f"Hittar inte båda värdekolumnerna i {csv_path}: {varden}. Uttaget "
            "ska bära arbetskraften (sysselsatta och arbetslösa) och antal "
            "totalt, och rubrikerna ska säga vilken som är vilken "
            "(outputFormatParams=UseCodesAndTexts).")

    klass = df[ald].map(normalisera_klass)
    ut = pd.DataFrame({
        "municipal_code": kommunkod(df[reg].astype(str).str.extract(r"(\d{4})")[0]),
        "year": pd.to_numeric(df[tid], errors="coerce"),
        "age_group": klass,
        "in_labour_force": pd.to_numeric(
            df[arbetskraft].astype(str).str.replace(r"\s", "", regex=True),
            errors="coerce"),
        "total": pd.to_numeric(
            df[totalt].astype(str).str.replace(r"\s", "", regex=True),
            errors="coerce"),
    })
    ut = ut.dropna(subset=["municipal_code", "year", "age_group",
                           "in_labour_force", "total"])
    ut["year"] = ut["year"].astype(int)
    for k in ("in_labour_force", "total"):
        ut[k] = ut[k].astype(float).round().astype(int)

    if ut.empty:
        raise ValueError(f"Inga rader kvar efter filtrering av {csv_path}")
    # EN RAD PER KOMMUN, ÅR OCH KLASS. Blir det fler har kön eller
    # födelseregion kommit med som delar vid sidan av sina totaler, och talen
    # är dubbelräknade.
    if ut.duplicated(["municipal_code", "year", "age_group"]).any():
        raise ValueError(
            f"Flera rader per kommun, år och åldersklass i {csv_path}. Uttaget "
            "ska välja totalvärdena för kön (1+2) och födelseregion (tot).")
    return ut


def load_labour_force_by_age(csv_path, db_path="data/worm.sqlite3"):
    df = las_arbetskraft_per_alder(csv_path)
    conn = sqlite3.connect(db_path)
    df.to_sql("labour_force_by_age", conn, if_exists="replace", index=False)
    conn.close()
    ar = sorted(df["year"].unique())
    klasser = sorted(df["age_group"].unique())
    saknas = {"16-64", "16-65", "16-66"} - set(klasser)
    print(f"[arbetskraft per ålder] {df['municipal_code'].nunique()} kommuner, "
          f"år {ar[0]}-{ar[-1]}, {len(klasser)} åldersklasser, {len(df)} rader")
    if saknas:
        # Utan dem går arbetskraften vid 65 och 66 inte att räkna fram, och de
        # åldrarna bär utträdet.
        print(f"  OBS: aggregaten {sorted(saknas)} saknas i uttaget")
    return len(df)
