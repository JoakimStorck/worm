"""
core/database/load_commuting_matrix.py
--------------------------------------
SCB:s pendlingsflöden mellan kommuner in i tabellen `commuting`.

Tabellen är referensen för pendlingen. core/occupations/utils.py kallar den
den enda kalibreringen av commute_cost_per_km, och analysis.py ställer
körningens andel tillsättningar över kommungräns mot den. Fanns den inte var
kalibreringen ett påstående utan täckning.

TVÅ FORMAT, eftersom SCB:s statistikdatabas exporterar på två sätt och båda
ligger i data/:

  BRED   "Sysselsatta 15-74 år arbetsställekommun bostadskommun.csv"
         Två inledande skräprader, sedan rubrikraden. Kolumnerna är
         år;kön;bostadskommun följt av en kolumn per arbetsställekommun.

  LÅNG   "Förvärvsarbetande 16-74 år pendlare över kommungräns ...csv"
         En titelrad, en tom rad, sedan bostadskommun, arbetsställekommun,
         kön och en kolumn per år.

Båda innehåller diagonalen, trots att den senares rubrik säger "över
kommungräns". DIAGONALEN ÄR INTE VALFRI: andelen som pendlar över gräns är ett
tal med en nämnare, och nämnaren är alla sysselsatta med bostad i kommunen,
också de som arbetar kvar i den. Utan diagonalen går bara flödena att jämföra,
inte andelarna, och det är andelen share_hires_cross_municipality mäter.

Kommunkoden ligger som fyra siffror först i varje etikett ("2062 Mora
(bostad)"). Suffixen skiljer sig mellan filerna, så koden plockas ut och
namnet kastas: koden är nyckeln mot municipalities.

    python -m core.database.load_commuting_matrix data/<fil>.csv
"""
import os
import re
import sqlite3
import sys

import pandas as pd

KOD = re.compile(r"(\d{4})")
# SCB:s statistikdatabas skriver ISO-8859-1 som förval. Läses den som UTF-8
# faller den antingen med UnicodeDecodeError eller -- värre -- tyst, med
# kommunnamn som inte matchar något. utf-8-sig står först, så att en fil som
# VERKLIGEN är UTF-8 inte tolkas som latin-1.
KODNINGAR = ("utf-8-sig", "cp1252", "iso-8859-1")


def _las_rader(path):
    """Filens rader som text, med den kodning som faktiskt fungerar."""
    for kodning in KODNINGAR:
        try:
            with open(path, encoding=kodning) as f:
                return f.read().splitlines(), kodning
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Kan inte avkoda {path} med någon av {KODNINGAR}")


def _sep(rader):
    """Semikolon i det breda uttaget, komma i det långa."""
    huvud = "\n".join(rader[:20])
    return ";" if huvud.count(";") > huvud.count(",") else ","


def _rubrikrad(rader, sep):
    """Index för rubrikraden. SCB lägger en titelrad och ofta en tom rad
    först, och antalet varierar mellan uttag -- att hoppa över ett fast antal
    rader går sönder nästa gång någon exporterar."""
    for i, rad in enumerate(rader[:20]):
        falt = [f.strip().strip('"').lower() for f in rad.split(sep)]
        if "bostadskommun" in falt:
            return i
    raise ValueError("Hittar ingen rubrikrad med kolumnen bostadskommun")


def las_pendling(csv_path):
    """CSV -> long-form: home_municipality, work_municipality, year, employed.

    Kastar hellre än att returnera en ram av nollor: en matris full av nollor
    ser ut som data och skulle passera varje senare kontroll.
    """
    rader, kodning = _las_rader(csv_path)
    sep = _sep(rader)
    start = _rubrikrad(rader, sep)
    df = pd.read_csv(csv_path, sep=sep, skiprows=start, dtype=str,
                     encoding=kodning, engine="python")
    df.columns = [str(c).strip().strip('"') for c in df.columns]
    kol = {c.lower(): c for c in df.columns}

    bostad = kol.get("bostadskommun")
    if bostad is None:
        raise ValueError("Ingen kolumn bostadskommun i rubrikraden")
    arbete = kol.get("arbetsställekommun") or kol.get("arbetsstallekommun")

    if arbete is not None:
        # LÅNGT FORMAT: en rad per par, en kolumn per år.
        arskolumner = [c for c in df.columns if re.fullmatch(r"\d{4}", str(c).strip())]
        if not arskolumner:
            raise ValueError("Långt format utan årskolumn")
        langt = df.melt(id_vars=[bostad, arbete], value_vars=arskolumner,
                        var_name="year", value_name="employed")
    else:
        # BRETT FORMAT: en kolumn per arbetsställekommun. Observera att
        # bostadskommunen är TREDJE kolumnen, inte den första -- år och kön
        # står före. Den tidigare laddaren tog radetiketten som första
        # kolumnen och hade läst årtalet som bostadskommun.
        arkol = kol.get("år") or kol.get("ar")
        idkol = [c for c in (arkol, kol.get("kön"), kol.get("kon"), bostad) if c]
        varden = [c for c in df.columns
                  if c not in idkol and KOD.match(str(c).strip())]
        if not varden:
            raise ValueError("Brett format utan kolumner för arbetsställekommun")
        langt = df.melt(id_vars=idkol, value_vars=varden,
                        var_name="_arbete", value_name="employed")
        arbete = "_arbete"
        langt["year"] = langt[arkol] if arkol else None

    ut = pd.DataFrame({
        "home_municipality": langt[bostad].astype(str).str.extract(KOD.pattern)[0],
        "work_municipality": langt[arbete].astype(str).str.extract(KOD.pattern)[0],
        "employed": pd.to_numeric(langt["employed"], errors="coerce"),
        "year": pd.to_numeric(langt["year"], errors="coerce"),
    })
    ut = ut.dropna(subset=["home_municipality", "work_municipality", "employed"])
    ut["employed"] = ut["employed"].astype(int)
    # Kön summeras. Uttagen ligger på "totalt" respektive "män och kvinnor",
    # alltså redan en rad per par -- men delas de upp i ett framtida uttag
    # dubbelräknas flödet om raderna inte slås ihop här.
    ut = ut.groupby(["home_municipality", "work_municipality", "year"],
                    dropna=False, as_index=False)["employed"].sum()
    return ut


def load_commuting_matrix(csv_path, db_path="data/worm.sqlite3", year=None):
    df = las_pendling(csv_path)
    if year is not None:
        df = df[df["year"] == year]
    conn = sqlite3.connect(db_path)
    df.to_sql("commuting", conn, if_exists="replace", index=False)
    conn.close()
    ar = sorted({int(a) for a in df["year"].dropna().unique()})
    diag = int(df[df["home_municipality"] == df["work_municipality"]]["employed"].sum())
    tot = int(df["employed"].sum())
    print(f"[commuting] {len(df)} flöden, år {ar}, {tot} sysselsatta varav "
          f"{100 * diag / tot:.1f} procent inom egen kommun.")
    return len(df)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("Ange CSV-fil: python -m core.database.load_commuting_matrix <fil>")
    load_commuting_matrix(sys.argv[1],
                          db_path=sys.argv[2] if len(sys.argv) > 2
                          else os.path.join("data", "worm.sqlite3"))
