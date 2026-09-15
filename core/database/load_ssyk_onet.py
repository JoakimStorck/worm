"""
core/database/load_ssyk_onet.py
-------------------------------
SSYK 2012 -> O*NET-SOC 2019, i två steg och två tabeller.

TVÅ TABELLER MED AVSIKT, eftersom de har olika livslängd och olika status.

    ssyk_isco_key         ren avskrift av SCB:s nyckel: SSYK4 -> ISCO4, en rad
                          per par. Kommalistor uppsplittade, inledande nollor
                          återställda, inget annat. Ändras bara när SCB
                          publicerar en ny nyckel, och kan granskas mot
                          originalet rad för rad.

    ssyk3_onet_crosswalk  härledd: occupation_code, onet_code, share. Bär fyra
                          antaganden och ändras varje gång något av dem
                          omprövas.

Ligger de i samma tabell går det inte att skilja SCB:s uppgift från vår
approximation. Det är samma lärdom som onet_occupation_space, där en tabell med
två slags innehåll och tre skrivare blev omöjlig att resonera om.

KEDJAN har fem led, tre av dem många-till-många:

    SSYK3 -> SSYK4 -> ISCO4 -> ISCO3 -> ESCO-yrke -> O*NET-SOC 2019

ANTAGANDENA, som hör hemma i metodavsnittet:

 1. Likformigt mellan SSYK4-koder inom en SSYK3-grupp. Rätt vikt vore antalet
    anställda per SSYK4, men nattbefolkningen publiceras bara på SSYK3.
 2. Likformigt när en SSYK4 pekar på flera ISCO4. SCB publicerar inga andelar.
 3. Likformigt mellan ESCO-yrken inom en ISCO3-grupp, och mellan de O*NET-koder
    ett ESCO-yrke kopplas till.
 4. Matchningstyperna i ESCO-crosswalken viktas: exactMatch och exactISCO fullt,
    closeMatch halvt, narrowMatch en fjärdedel, broadMatch noll. broadMatch är
    den största posten (2 053 av 4 253) och den vagaste -- chief operating
    officer står som broadMatch till Chief Executives, vilket ser ut som
    motsatt riktning mot SKOS-konventionen. Vikterna är ett val, inte en
    mätning, och går att ändra med parametern matchvikter.

VARFÖR SCB:s NYCKEL BEHÖVS trots att SSYK 2012 bygger på ISCO-08: 37 av 149
SSYK3-koder saknar ISCO-kod med samma nummer, och de sitter systematiskt i
chefs- och specialistserierna 12-17, 21-22 och 26-27. Att mappa på likhet i
koder hade gett noll vikt åt en fjärdedel av yrkena, koncentrerat till den
yttre delen av uppgiftsrummet -- motsatsen till det fel vi rättar.

    python -m core.database.load_ssyk_onet \\
        "data/webb_nyckel_ssyk2012_isco-08_20160905.xlsx" \\
        "data/ONET_(Occupations)_0_updated.csv" \\
        data/esco_1.2.1/occupations_sv.csv
"""
import os
import re
import sqlite3
import sys

import numpy as np
import pandas as pd

KOD4 = re.compile(r"\d{1,4}")

# Vikter per matchningstyp i ESCO-crosswalken. Se antagande 4 ovan.
MATCHVIKTER = {"exactMatch": 1.0, "exactISCO": 1.0, "closeMatch": 0.5,
               "narrowMatch": 0.25, "broadMatch": 0.0}


def _nollfyll(serie):
    """Fyrsiffriga koder med bevarad inledande nolla.

    Excel har tolkat 0110 som talet 110 i ISCO-kolumnen. Samma fälla som
    kommunkoderna i 0132, i en annan fil: koden ser riktig ut och matchar
    ingenting.
    """
    return (pd.Series(serie).astype("string").str.strip()
            .str.replace(r"\.0$", "", regex=True).str.zfill(4))


def las_ssyk_isco(xlsx_path, blad="Nyckel"):
    """SCB:s nyckel -> DataFrame med ssyk4, isco4, en rad per par.

    Bladet har tre metadatarader före rubriken och tomma kolumner mellan de
    två koderna. Rubrikraden söks upp i stället för att hoppas över med ett
    fast antal rader -- antalet varierar mellan SCB:s uttag, och en fast
    hoppning går sönder vid nästa utgåva.
    """
    rat = pd.read_excel(xlsx_path, sheet_name=blad, header=None, dtype=str)
    rubrik = None
    for i in range(min(20, len(rat))):
        rad = " ".join(str(v) for v in rat.iloc[i].tolist()).lower()
        if "ssyk" in rad and "isco" in rad and "kod" in rad:
            rubrik = i
            break
    if rubrik is None:
        raise ValueError("Hittar ingen rubrikrad med SSYK- och ISCO-kod")

    kropp = rat.iloc[rubrik + 1:]
    kolumner = [c for c in kropp.columns if kropp[c].notna().any()]
    if len(kolumner) < 2:
        raise ValueError("Färre än två ifyllda kolumner under rubriken")
    ssyk_kol, isco_kol = kolumner[0], kolumner[1]

    rader = []
    for ssyk, isco in zip(kropp[ssyk_kol], kropp[isco_kol]):
        if pd.isna(ssyk) or pd.isna(isco):
            continue
        s = _nollfyll([ssyk]).iloc[0]
        # KOMMALISTOR. 0210 avbildas på "0110, 0210" och 1120 på "1120, 1420".
        for i in KOD4.findall(str(isco)):
            rader.append({"ssyk4": s, "isco4": i.zfill(4)})
    if not rader:
        raise ValueError("Inga par lästes ur nyckeln")
    ut = pd.DataFrame(rader).drop_duplicates().reset_index(drop=True)
    flera = ut.groupby("ssyk4").size()
    print(f"[ssyk-isco] {len(ut)} par, {ut.ssyk4.nunique()} SSYK4-koder, "
          f"{int((flera > 1).sum())} med fler än en ISCO-kod")
    return ut


def las_esco_onet(csv_path, esco_path, matchvikter=None):
    """ESCO-crosswalken plus ESCO:s yrkeslista -> isco3, onet_code, vikt.

    Crosswalken har sexton metadatarader före rubriken, fält med både
    kommatecken och radbrytningar -- shell-verktyg räknar fel på den, en riktig
    CSV-parser måste användas -- och två slags målrader: 4 210 mot ESCO-yrken
    och 43 direkt mot ISCO-grupper. De senare tas med utan omvägen via ESCO.
    """
    vikter = dict(MATCHVIKTER if matchvikter is None else matchvikter)
    c = pd.read_csv(csv_path, skiprows=16, dtype=str)
    c.columns = [x.strip() for x in c.columns]
    for kol in ("O*NET Id", "ESCO or ISCO URI", "Type of Match"):
        if kol not in c.columns:
            raise ValueError(f"Saknar kolumnen {kol} i {csv_path}")
    c["vikt"] = c["Type of Match"].map(vikter).fillna(0.0)
    c = c[c["vikt"] > 0]
    uri = c["ESCO or ISCO URI"].astype(str)

    # Raderna som pekar direkt på en ISCO-grupp: C1111 -> 111.
    direkt = c[uri.str.contains("/isco/")].copy()
    direkt["isco3"] = (direkt["ESCO or ISCO URI"].astype(str)
                       .str.extract(r"/isco/C?(\d+)")[0].str[:3])

    # Raderna som går via ESCO-yrken.
    e = pd.read_csv(esco_path, dtype=str)
    if "conceptUri" not in e.columns or "iscoGroup" not in e.columns:
        raise ValueError(f"Saknar conceptUri eller iscoGroup i {esco_path}")
    isco_per_uri = dict(zip(e["conceptUri"].astype(str),
                            e["iscoGroup"].astype(str).str.zfill(4).str[:3]))
    via = c[uri.str.contains("/occupation/")].copy()
    via["isco3"] = via["ESCO or ISCO URI"].astype(str).map(isco_per_uri)
    saknas = via["isco3"].isna().sum()
    if saknas:
        print(f"[esco-onet] {saknas} ESCO-URI:er saknas i yrkeslistan "
              f"(versionsdrift) -- de utesluts")
    via = via.dropna(subset=["isco3"])

    ihop = pd.concat([direkt[["isco3", "O*NET Id", "vikt"]],
                      via[["isco3", "O*NET Id", "vikt"]]], ignore_index=True)
    ihop = ihop.rename(columns={"O*NET Id": "onet_code"})
    ut = ihop.groupby(["isco3", "onet_code"], as_index=False)["vikt"].sum()
    print(f"[esco-onet] {len(ut)} par, {ut.isco3.nunique()} ISCO3-grupper, "
          f"{ut.onet_code.nunique()} O*NET-koder")
    return ut


def bygg_crosswalk(nyckel, esco_onet, ssyk3_koder=None, onet_koder=None):
    """SSYK3 -> O*NET med andelar som summerar till ett per SSYK3-grupp.

    Varje led normaliseras för sig, så att en SSYK4 med många ISCO-koder inte
    får mer vikt än en med få. Det är innebörden av "likformigt" i antagandena
    1 till 3.
    """
    n = nyckel.copy()
    n["ssyk3"] = n["ssyk4"].str[:3]
    n["isco3"] = n["isco4"].str[:3]
    if ssyk3_koder:
        n = n[n["ssyk3"].isin({str(k).zfill(3) for k in ssyk3_koder})]

    # Led 1 och 2: likformigt över de ISCO4 en SSYK4 pekar på, sedan
    # likformigt över SSYK4-koderna inom SSYK3-gruppen.
    n["v"] = 1.0 / n.groupby("ssyk4")["isco4"].transform("size")
    n["v"] = n["v"] / n.groupby("ssyk3")["ssyk4"].transform("nunique")
    ssyk_isco = n.groupby(["ssyk3", "isco3"], as_index=False)["v"].sum()

    eo = esco_onet.copy()
    if onet_koder:
        eo = eo[eo["onet_code"].isin(set(onet_koder))]
    # Led 3: andelar inom ISCO3-gruppen.
    eo["andel"] = eo["vikt"] / eo.groupby("isco3")["vikt"].transform("sum")

    ihop = ssyk_isco.merge(eo[["isco3", "onet_code", "andel"]], on="isco3",
                           how="inner")
    ihop["share"] = ihop["v"] * ihop["andel"]
    ut = (ihop.groupby(["ssyk3", "onet_code"], as_index=False)["share"].sum()
          .rename(columns={"ssyk3": "occupation_code"}))
    # Normalisera per SSYK3: led som tappat mål ska inte ge lägre total.
    ut["share"] = ut["share"] / ut.groupby("occupation_code")["share"].transform("sum")
    return ut[ut["share"] > 0].reset_index(drop=True)


def load_ssyk_onet(xlsx_path, crosswalk_csv, esco_csv,
                   db_path="data/worm.sqlite3", matchvikter=None):
    nyckel = las_ssyk_isco(xlsx_path)
    eo = las_esco_onet(crosswalk_csv, esco_csv, matchvikter=matchvikter)

    conn = sqlite3.connect(db_path)
    try:
        ssyk3 = set(pd.read_sql("SELECT DISTINCT ssyk_code FROM occupation_by_county",
                                conn)["ssyk_code"].astype(str))
    except Exception:
        ssyk3 = None
    try:
        onet = set(pd.read_sql("SELECT onet_code FROM onet_occupation_space",
                               conn)["onet_code"].astype(str))
    except Exception:
        onet = None

    cw = bygg_crosswalk(nyckel, eo, ssyk3_koder=ssyk3, onet_koder=onet)
    nyckel.to_sql("ssyk_isco_key", conn, if_exists="replace", index=False)
    cw.to_sql("ssyk3_onet_crosswalk", conn, if_exists="replace", index=False)
    conn.close()

    # SPRIDNINGSMÄTNINGEN. Blir talet några tiotal bär fördelningen fortfarande
    # information; blir det hundratals har kedjan tvättat bort det mesta, och
    # då är slutsatsen att invånarnas yrken inte kan preciseras bättre än så
    # med publikt material.
    per = cw.groupby("occupation_code").size()
    halva = (cw.sort_values("share", ascending=False)
             .groupby("occupation_code")["share"]
             .apply(lambda s: int((s.cumsum() <= 0.5).sum()) + 1))
    print(f"[ssyk-onet] {len(cw)} par, {cw.occupation_code.nunique()} SSYK3-grupper, "
          f"{cw.onet_code.nunique()} O*NET-koder")
    print(f"[ssyk-onet] O*NET-koder per SSYK3: median {int(per.median())}, "
          f"max {int(per.max())}")
    print(f"[ssyk-onet] koder som bär halva vikten: median {int(halva.median())}")
    if ssyk3:
        tappade = sorted(ssyk3 - set(cw.occupation_code))
        if tappade:
            print(f"[ssyk-onet] {len(tappade)} SSYK3 utan O*NET-koppling: "
                  f"{tappade[:8]}")
    if onet:
        utan = len(onet - set(cw.onet_code))
        print(f"[ssyk-onet] {utan} av {len(onet)} O*NET-koder får ingen vikt")
    return len(cw)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit(__doc__.strip().splitlines()[-3].strip())
    load_ssyk_onet(sys.argv[1], sys.argv[2], sys.argv[3],
                   db_path=sys.argv[4] if len(sys.argv) > 4
                   else os.path.join("data", "worm.sqlite3"))


# ---------------------------------------------------------------------------
def load_onet_weights(db_path="data/worm.sqlite3"):
    """occupation_weights_ssyk_by_municipality x ssyk3_onet_crosswalk
    -> occupation_weights_by_municipality.

    Sista steget: kommunernas yrkesfördelning i SSYK3 blir en fördelning över
    O*NET-koder, vilket är den tabell municipality_occupational_profile läser
    när occupation_source är register.

    GÄLLER HELA RIKET, inte ett scenario. Modellen ska kunna byggas av vilka
    kommuner som helst, och tabellen fylls därför för alla 290 -- avgränsningen
    sker när ett scenario väljer sina kommuner, inte här.

    Andelarna normaliseras per kommun efter produkten. En SSYK3-grupp vars
    O*NET-koder delvis saknas i geometrin ska inte ge kommunen lägre total; den
    kvarvarande vikten fördelas om inom gruppen.
    """
    conn = sqlite3.connect(db_path)
    try:
        v = pd.read_sql("SELECT municipal_code, occupation_code, weight "
                        "FROM occupation_weights_ssyk_by_municipality", conn)
        cw = pd.read_sql("SELECT occupation_code, onet_code, share "
                         "FROM ssyk3_onet_crosswalk", conn)
    except Exception as e:
        conn.close()
        raise ValueError(f"Saknar underlagstabell: {e}")
    if v.empty or cw.empty:
        conn.close()
        raise ValueError("Tom yrkesvikts- eller crosswalktabell")

    ihop = v.merge(cw, on="occupation_code", how="inner")
    ihop["w"] = ihop["weight"] * ihop["share"]
    ut = (ihop.groupby(["municipal_code", "onet_code"], as_index=False)["w"].sum()
          .rename(columns={"w": "weight"}))
    ut["weight"] = ut["weight"] / ut.groupby("municipal_code")["weight"].transform("sum")
    ut = ut[ut["weight"] > 0].reset_index(drop=True)
    ut.to_sql("occupation_weights_by_municipality", conn,
              if_exists="replace", index=False)

    # Hur mycket av kommunernas vikt som föll bort i produkten -- de
    # SSYK3-grupper som saknar O*NET-koppling, i huvudsak militära yrken och
    # okänt yrke.
    kvar = (ihop.groupby("municipal_code")["weight"].sum()
            / v.groupby("municipal_code")["weight"].sum())
    conn.close()
    print(f"[onet-vikter] {ut.municipal_code.nunique()} kommuner, "
          f"{ut.onet_code.nunique()} O*NET-koder, {len(ut)} rader")
    print(f"[onet-vikter] andel av SSYK-vikten som nådde fram: "
          f"median {kvar.median():.3f}, lägst {kvar.min():.3f}")
    return len(ut)
