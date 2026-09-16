"""Folkmängd per ettårsklass och kommun ur SCB:s BE0101 (BefolkningNy).

Ålderspyramiden är underlaget för startpopulationens åldrar. Utan den kan
ålder bara dras ur en påhittad fördelning, och då bestämmer antagandet både
hur många som står nära pensionsåldern och hur långa arbetsliv individerna
har bakom sig -- två storheter som modellen ska mäta, inte anta.

TOTALRADER. Konventionerna skiljer sig mellan SCB:s uttag och är därför
dokumenterade i varje läsare. Det här uttaget kan bära tre slags summarader,
och alla tre utesluts:

  * riksraden "00 Riket" i regionkolumnen (samma konvention som länsfilen),
  * ålderskategorin "totalt" eller "tot",
  * könskategorin "totalt", som i stället väljs när den finns.

Kön väljs alltså som "totalt" om kolumnen finns, och summeras annars. Att både
välja totalraden och summera delarna hade dubbelräknat hela befolkningen.

FORMAT. Läsaren väntar sig SCB:s CSV från statistikdatabasen (PxWeb), i det
breda formatet med ett årtal per kolumn eller i långt format med en
årskolumn. Åldersetiketterna är "0 år", "1 år", ..., "100+ år"; siffran läses
ur strängen och "100+" blir 100.
"""
import re

import numpy as np
import pandas as pd
import sqlite3

from core.database.utils import kommunkod

# "34 år", "34", "100+ år", "100+"
ALDER = re.compile(r"^\s*(\d{1,3})\s*\+?\s*(år)?\s*$", re.IGNORECASE)
AR = re.compile(r"^(19|20)\d{2}$")


def _sep(rader):
    """Semikolon i SCB:s svenska export, komma i den engelska."""
    huvud = "\n".join(rader[:20])
    return ";" if huvud.count(";") > huvud.count(",") else ","


def _rubrikrad(rader, sep):
    """Index för rubrikraden. SCB lägger en titelrad och ofta en tom rad
    först, och antalet varierar mellan uttag."""
    for i, rad in enumerate(rader[:25]):
        falt = [f.strip().strip('"').lower() for f in rad.split(sep)]
        if any(f in ("region", "kommun") for f in falt) and \
                any(f.startswith(("ålder", "alder")) for f in falt):
            return i
    raise ValueError("Hittar ingen rubrikrad med kolumnerna region och ålder")


def _kolumn(df, *nyckelord):
    for c in df.columns:
        lc = str(c).strip().lower()
        for n in nyckelord:
            if lc == n or lc.startswith(n):
                return c
    return None


def las_befolkning_per_alder(csv_path, kodning="utf-8-sig"):
    """DataFrame med municipal_code, year, age, n_total."""
    with open(csv_path, encoding=kodning, errors="replace") as f:
        rader = f.read().splitlines()
    sep = _sep(rader)
    start = _rubrikrad(rader, sep)
    df = pd.read_csv(csv_path, sep=sep, skiprows=start, dtype=str,
                     encoding=kodning, engine="python")
    df.columns = [str(c).strip().strip('"') for c in df.columns]

    reg = _kolumn(df, "region", "kommun")
    ald = _kolumn(df, "ålder", "alder")
    if reg is None or ald is None:
        raise ValueError(f"Saknar region- eller ålderskolumn i {csv_path}: "
                         f"{list(df.columns)}")

    kon = _kolumn(df, "kön", "kon")
    if kon is not None:
        totalt = df[kon].astype(str).str.strip().str.lower() == "totalt"
        if totalt.any():
            df = df[totalt]
        else:
            df = df.drop(columns=[kon])
            kon = None

    # Riksraden ut. Uttaget kan vara gjort per kommun utan den, och då finns
    # inget att utesluta -- men står den kvar skulle den bli en "kommun" med
    # tio miljoner invånare. Matchningen sker på ORDET Riket och inte på
    # kodprefixet: "00 Riket" faller redan på extraktionen av fyra siffror
    # nedan, men en fyrsiffrig variant skulle passera den.
    df = df[~df[reg].astype(str).str.contains(r"\briket\b", case=False,
                                              regex=True, na=False)]

    aldrar = df[ald].astype(str).str.strip().str.extract(ALDER)[0]
    df = df[aldrar.notna()]
    aldrar = aldrar[aldrar.notna()].astype(int)

    arkol = [c for c in df.columns if AR.match(str(c).strip())]
    tid = _kolumn(df, "tid", "år ") if not arkol else None
    varde = _kolumn(df, "folkmängd", "folkmangd", "antal", "befolkning")

    ut = pd.DataFrame({"municipal_code": df[reg].astype(str).str.strip(),
                       "age": aldrar.to_numpy()})
    if arkol:
        # Brett format: ett årtal per kolumn.
        langt = []
        for c in arkol:
            langt.append(pd.DataFrame({
                "municipal_code": ut["municipal_code"].to_numpy(),
                "age": ut["age"].to_numpy(),
                "year": int(str(c).strip()),
                "n_total": pd.to_numeric(df[c].astype(str).str.replace(r"\s", "", regex=True),
                                         errors="coerce").to_numpy()}))
        ut = pd.concat(langt, ignore_index=True)
    else:
        if tid is None or varde is None:
            raise ValueError(f"Hittar varken årskolumner eller tid+värde i "
                             f"{csv_path}: {list(df.columns)}")
        ut["year"] = pd.to_numeric(df[tid], errors="coerce").to_numpy()
        ut["n_total"] = pd.to_numeric(
            df[varde].astype(str).str.replace(r"\s", "", regex=True),
            errors="coerce").to_numpy()

    ut = ut.dropna(subset=["year", "n_total"])
    ut["municipal_code"] = kommunkod(
        ut["municipal_code"].str.extract(r"(\d{4})")[0])
    ut = ut.dropna(subset=["municipal_code"])
    ut["year"] = ut["year"].astype(int)
    ut["n_total"] = ut["n_total"].astype(float).round().astype(int)
    ut = ut.groupby(["municipal_code", "year", "age"], as_index=False)["n_total"].sum()

    if ut.empty:
        raise ValueError(f"Inga rader kvar efter filtrering av {csv_path}")
    # EN RAD PER KOMMUN, ÅR OCH ÅLDER. Blir det fler har en dimension
    # (kön, civilstånd, födelseregion) missats och talen är dubbelräknade.
    if ut.duplicated(["municipal_code", "year", "age"]).any():
        raise ValueError("Flera rader per kommun, år och ålder efter filtrering")
    return ut


def load_population_by_age(csv_path, db_path="data/worm.sqlite3"):
    df = las_befolkning_per_alder(csv_path)
    conn = sqlite3.connect(db_path)
    df.to_sql("population_by_age", conn, if_exists="replace", index=False)
    conn.close()
    ar = sorted(df["year"].unique())
    print(f"[befolkning per ålder] {df['municipal_code'].nunique()} kommuner, "
          f"år {ar[0]}-{ar[-1]}, åldrar {df['age'].min()}-{df['age'].max()}, "
          f"{len(df)} rader")
    return len(df)
