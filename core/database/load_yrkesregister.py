"""
core/database/load_yrkesregister.py
-----------------------------------
SCB:s yrkesregister in i databasen, och yrkesfördelning per KOMMUN skattad ur
det med iterativ proportionell anpassning.

PROBLEMET. Individernas yrken drogs ur municipality_occupational_profile, som
går via fetch_sni_distribution och sni_onet_link: kommunens branschmix PÅ
ARBETSSTÄLLENA, använd som fördelning över INVÅNARNA. Det är fel på två sätt
som båda slår hårdast mot utpendlingskommuner. En Älvdaling som arbetar i Mora
har ett yrke ur Moras branschmix, inte Älvdalens. Och en kommun med tunn
branschmix får invånare koncentrerade till få yrken, vilket gör dem svårare att
matcha mot en marknad som domineras av grannen.

VARFÖR IPF. Yrkesregistrets nattbefolkning -- yrke efter var personen BOR --
publiceras bara på länsnivå. Kommunnivå finns inte, sannolikt för att SSYK3
gånger 290 kommuner ger celler som ofta är ensiffriga. Det som däremot finns
per kommun är branschfördelningen bland invånarna, i employment_deso_sni, som
är nattbefolkning: DeSO är en bostadsindelning.

Då är småområdesskattning genom IPF den etablerade vägen:

    start(kommun, yrke) = n(kommun) * summa_SNI p(SNI|kommun) * p(yrke|SNI)

rakas växelvis mot kommunernas sysselsättningstotaler och länets
yrkesfördelning tills båda marginalerna stämmer. Resultatet bevarar båda exakt,
och variationen mellan kommunerna kommer ur deras branschstruktur.

ANTAGANDET SKA NAMNGES I METODAVSNITTET: yrke och kommun antas betingat
oberoende givet bransch, alltså att en verkstadsanställd i Älvdalen har samma
yrkesfördelning som en i Borlänge. Det stämmer inte exakt -- små orter har
färre specialistroller inom samma bransch. Men avvikelsen är mindre än dagens
fel, och att redovisa en känd approximation slår att tyst använda en
branschmix som proxy.

KVAR EFTER DEN HÄR MODULEN: kopplingen SSYK3 -> O*NET. Modellen räknar i
onet_soc, och SCB publicerar ingen sådan korrespondens. Kedjan är SSYK 2012 ->
ISCO-08 (SSYK bygger på ISCO-08) -> SOC 2010 (BLS ISCO_SOC_Crosswalk) ->
O*NET-SOC. Tills den finns skriver modulen yrkesvikter i SSYK3 och modellen
använder fortsatt SNI-vägen; scripts/load_occupation_weights.py tar en
crosswalk-CSV med occupation_code, onet_code, share när den väl är byggd.

    python -m core.database.load_yrkesregister data/TAB4347_sv.csv data/TAB4441_sv.csv
"""
import os
import re
import sqlite3
import sys

import numpy as np
import pandas as pd

from core.database.load_commuting_matrix import _las_rader, _sep

SSYK = re.compile(r"^(\d{3})")
SNI_BOKSTAV = re.compile(r"^([A-U][+A-U]*)")
LAN = re.compile(r"^(\d{2})")


def _las(csv_path):
    """SCB-uttag med rubrikrad, oavsett kodning och avgränsare.

    Yrkesregistrets uttag är kommaseparerade med citattecken och rubriken på
    rad ett, medan pendlings- och arbetsmarknadsfilerna är semikolonseparerade
    med två skräprader före. Att anta fel form ger ParserError, vilket är
    ofarligt -- till skillnad från att anta fel KONVENTION för totalrader,
    vilket ger tyst dubbelräkning.
    """
    rader, kodning = _las_rader(csv_path)
    sep = _sep(rader)
    start = next((i for i, r in enumerate(rader[:20])
                  if "yrke" in r.lower() and r.count(sep) >= 2), 0)
    df = pd.read_csv(csv_path, sep=sep, skiprows=start, dtype=str,
                     encoding=kodning, engine="python", quotechar='"')
    df.columns = [str(c).strip().strip('"') for c in df.columns]
    return df


def _kol(df, *nyckelord):
    for n in nyckelord:
        for c in df.columns:
            if n in c.lower():
                return c
    return None


def las_yrke_naringsgren(csv_path, ar="2023"):
    """Riket: yrke x näringsgren x storleksklass -> antal anställda.

    INGEN TOTALRAD i det här uttaget: kön har bara män och kvinnor, och
    summan över dem är rikets alla anställda. Raderna ska alltså SUMMERAS.
    Det är motsatt konvention mot Arbetsmarknadsstatus Kommun.csv, som har en
    egen totalrad och ska filtreras, och mot SNI-filen där "A-U+US Total"
    kolliderade med näringsgren A. Blandas konventionerna ihop blir det
    dubbelräkning eller halvering utan att något klagar.
    """
    df = _las(csv_path)
    yrke, sni = _kol(df, "yrke"), _kol(df, "näringsgren", "naringsgren")
    storlek, arkol = _kol(df, "storleksklass"), _kol(df, "år", "ar")
    antal = df.columns[-1]
    if not (yrke and sni and antal):
        raise ValueError(f"Saknar kolumner i {csv_path}: {list(df.columns)}")
    if arkol and ar:
        df = df[df[arkol].astype(str).str.strip() == str(ar)]
        if df.empty:
            raise ValueError(f"Inga rader för år {ar}")
    ut = pd.DataFrame({
        "ssyk_code": df[yrke].astype(str).str.extract(SSYK.pattern)[0],
        "sni_code": df[sni].astype(str).str.strip().str.extract(SNI_BOKSTAV.pattern)[0],
        "size_class": (df[storlek].astype(str).str.strip() if storlek else "alla"),
        "employed": pd.to_numeric(df[antal], errors="coerce"),
    }).dropna(subset=["ssyk_code", "sni_code", "employed"])
    ut["employed"] = ut["employed"].astype(int)
    return ut.groupby(["ssyk_code", "sni_code", "size_class"],
                      as_index=False)["employed"].sum()


def las_yrke_lan(csv_path, ar="2023"):
    """Län: yrke -> antal anställda med bostad i länet (nattbefolkning).

    Ålder och kön summeras: uttaget saknar totalrader för båda. Regionen
    "00 Riket" måste uteslutas, annars dubbelräknas hela landet ovanpå
    länen.
    """
    df = _las(csv_path)
    reg, yrke = _kol(df, "region", "län"), _kol(df, "yrke")
    arkol, antal = _kol(df, "år", "ar"), df.columns[-1]
    if not (reg and yrke and antal):
        raise ValueError(f"Saknar kolumner i {csv_path}: {list(df.columns)}")
    if arkol and ar:
        df = df[df[arkol].astype(str).str.strip() == str(ar)]
    kod = df[reg].astype(str).str.extract(LAN.pattern)[0]
    df = df[kod != "00"]                       # Riket ut
    ut = pd.DataFrame({
        "county_code": kod[kod != "00"],
        "ssyk_code": df[yrke].astype(str).str.extract(SSYK.pattern)[0],
        "employed": pd.to_numeric(df[antal], errors="coerce"),
    }).dropna()
    ut["employed"] = ut["employed"].astype(int)
    return ut.groupby(["county_code", "ssyk_code"], as_index=False)["employed"].sum()


# ---------------------------------------------------------------------------
def ipf(start, rad_mal, kol_mal, max_iter=200, tol=1e-9):
    """Iterativ proportionell anpassning av en matris mot båda marginalerna.

    start   (m, n) positiv startskattning -- mönstret som ska bevaras
    rad_mal (m,)   önskade radsummor
    kol_mal (n,)   önskade kolumnsummor

    Marginalerna måste summera till samma tal; annars finns ingen lösning och
    funktionen kastar hellre än att returnera något som ser rimligt ut.

    Nollor i start förblir nollor -- det är avsiktligt. En kommun vars
    branschmix helt saknar en bransch ska inte få yrken som bara förekommer
    där, och IPF kan inte skapa massa där mönstret säger noll. Är en kolumns
    målsumma positiv medan hela kolumnen är noll i start går det inte att
    lösa, och funktionen säger det.
    """
    A = np.asarray(start, dtype=float).copy()
    r = np.asarray(rad_mal, dtype=float)
    k = np.asarray(kol_mal, dtype=float)
    if A.ndim != 2 or A.shape != (len(r), len(k)):
        raise ValueError(f"Formen stämmer inte: {A.shape} mot {len(r)}x{len(k)}")
    if (A < 0).any() or (r < 0).any() or (k < 0).any():
        raise ValueError("Negativa värden")
    if not np.isclose(r.sum(), k.sum(), rtol=1e-6):
        raise ValueError(f"Marginalerna summerar olika: {r.sum():.1f} mot {k.sum():.1f}")
    doda = (A.sum(axis=0) == 0) & (k > 0)
    if doda.any():
        raise ValueError(f"{doda.sum()} kolumner har positivt mål men noll i "
                         f"startskattningen -- olösbart")
    for _ in range(max_iter):
        rs = A.sum(axis=1)
        A *= np.divide(r, rs, out=np.zeros_like(r), where=rs > 0)[:, None]
        ks = A.sum(axis=0)
        A *= np.divide(k, ks, out=np.zeros_like(k), where=ks > 0)[None, :]
        if (np.abs(A.sum(axis=1) - r).max() < tol
                and np.abs(A.sum(axis=0) - k).max() < tol):
            break
    return A


def yrkesvikter_per_kommun(conn, county_code, kommuner=None, ar=2023):
    """Yrkesfördelning per kommun, skattad med IPF.

    Startskattningen är kommunens branschmix bland INVÅNARNA
    (employment_deso_sni, nattbefolkning) korsad med rikets p(yrke|bransch).
    Den rakas mot kommunernas sysselsättningstotaler och länets
    yrkesfördelning.

    Returnerar en DataFrame med municipal_code, occupation_code, weight, där
    vikterna summerar till ett per kommun.
    """
    deso = pd.read_sql("SELECT deso_code, sni_code, employed "
                       "FROM employment_deso_sni", conn)
    deso = deso[deso["sni_code"].astype(str).str.upper() != "TOTAL"]
    deso["kom"] = deso["deso_code"].astype(str).str[:4]
    if kommuner:
        deso = deso[deso["kom"].isin({str(k).zfill(4) for k in kommuner})]
    if deso.empty:
        raise ValueError("Ingen branschfördelning per kommun i employment_deso_sni")
    kom_sni = (deso.groupby(["kom", "sni_code"])["employed"].sum()
               .unstack().astype(float).fillna(0.0))

    riket = pd.read_sql("SELECT ssyk_code, sni_code, employed "
                        "FROM occupation_by_industry", conn)
    p_yrke_sni = (riket.groupby(["sni_code", "ssyk_code"])["employed"].sum()
                  .unstack().astype(float).fillna(0.0))
    p_yrke_sni = p_yrke_sni.div(p_yrke_sni.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)

    gemensam = [c for c in kom_sni.columns if c in p_yrke_sni.index]
    if not gemensam:
        raise ValueError("Branschkoderna matchar inte mellan kommun- och rikstabellen")

    # OKÄND BRANSCH FÅR RIKETS TOTALA YRKESFÖRDELNING. Kommuntabellen har koden
    # US -- "uppgift saknas" -- som rikstabellen inte har: 93 677 personer, 1.8
    # procent. Att bara utesluta dem hade minskat varje kommuns radsumma, och
    # eftersom andelen okänd bransch varierar mellan kommuner hade det blivit
    # en systematisk snedvridning snarare än en proportionell förlust. Okänd
    # bransch betyder ingen information om yrke, inte noll sannolikhet, så de
    # får rikets marginalfördelning över yrken.
    riks_marginal = riket.groupby("ssyk_code")["employed"].sum()
    riks_marginal = (riks_marginal.reindex(p_yrke_sni.columns).fillna(0.0)
                     / max(riks_marginal.sum(), 1.0))
    okanda = [c for c in kom_sni.columns if c not in p_yrke_sni.index]
    start = kom_sni[gemensam].to_numpy() @ p_yrke_sni.loc[gemensam].to_numpy()
    if okanda:
        n_okand = kom_sni[okanda].to_numpy().sum(axis=1)
        start = start + np.outer(n_okand, riks_marginal.to_numpy())
        print(f"[yrkesvikter] {', '.join(okanda)}: {int(n_okand.sum())} personer "
              f"får rikets yrkesfördelning")

    lan = pd.read_sql("SELECT ssyk_code, employed FROM occupation_by_county "
                      "WHERE county_code = ?", conn, params=(str(county_code).zfill(2),))
    if lan.empty:
        raise ValueError(f"Ingen yrkesfördelning för län {county_code}")
    yrken = list(p_yrke_sni.columns)
    lan_v = (lan.set_index("ssyk_code")["employed"]
             .reindex(yrken).fillna(0.0).to_numpy(dtype=float))

    rad_mal = kom_sni.sum(axis=1).to_numpy(dtype=float)
    # Länets yrkesprofil skalas till kommunernas sammanlagda sysselsättning:
    # scenariot är en delmängd av länet, och marginalerna måste summera lika.
    kol_mal = lan_v * (rad_mal.sum() / lan_v.sum())

    lev = kol_mal > 0
    losning = ipf(start[:, lev], rad_mal, kol_mal[lev])
    full = np.zeros_like(start)
    full[:, lev] = losning

    ut = pd.DataFrame(full, index=kom_sni.index, columns=yrken)
    ut = ut.div(ut.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    lang = ut.stack().reset_index()
    lang.columns = ["municipal_code", "occupation_code", "weight"]
    return lang[lang["weight"] > 0].reset_index(drop=True)


# ---------------------------------------------------------------------------
def load_yrkesregister(riks_csv, lan_csv, db_path="data/worm.sqlite3", ar="2023"):
    riket = las_yrke_naringsgren(riks_csv, ar=ar)
    lan = las_yrke_lan(lan_csv, ar=ar)
    conn = sqlite3.connect(db_path)
    riket.to_sql("occupation_by_industry", conn, if_exists="replace", index=False)
    lan.to_sql("occupation_by_county", conn, if_exists="replace", index=False)
    conn.close()
    print(f"[yrkesregister] riket: {len(riket)} rader, "
          f"{riket.ssyk_code.nunique()} yrken, {riket.sni_code.nunique()} branscher, "
          f"{int(riket.employed.sum())} anställda")
    print(f"[yrkesregister] län: {len(lan)} rader, {lan.county_code.nunique()} län, "
          f"{int(lan.employed.sum())} anställda")
    return len(riket), len(lan)


def load_yrkesvikter(db_path="data/worm.sqlite3", county_code=None):
    """Skriver IPF-skattningen till occupation_weights_ssyk_by_municipality.

    EGET TABELLNAMN, inte occupation_weights_by_municipality. Den senare läses
    av municipality_occupational_profile när occupation_source är register, och
    dess occupation_code förväntas vara O*NET. Här är koderna SSYK3. Skrevs de
    dit skulle modellen slå upp SSYK-koder mot onet_occupation_space, få noll
    träffar och falla tillbaka -- eller värre, matcha på måfå. Tabellen byter
    namn när crosswalken finns, och inte förr.
    """
    conn = sqlite3.connect(db_path)
    try:
        lan = pd.read_sql("SELECT DISTINCT county_code FROM occupation_by_county",
                          conn)["county_code"].tolist()
    except Exception:
        conn.close()
        raise ValueError("occupation_by_county saknas -- ladda yrkesregistret först")
    if county_code:
        lan = [str(county_code).zfill(2)]
    delar = []
    for kod in lan:
        kommuner = pd.read_sql(
            "SELECT municipal_code FROM municipalities WHERE municipal_code LIKE ?",
            conn, params=(f"{kod}%",))["municipal_code"].tolist()
        if not kommuner:
            continue
        try:
            delar.append(yrkesvikter_per_kommun(conn, kod, kommuner))
        except ValueError as e:
            print(f"[yrkesvikter] län {kod}: {e}")
    if not delar:
        conn.close()
        raise ValueError("Inga län gick att skatta")
    ut = pd.concat(delar, ignore_index=True)
    ut.to_sql("occupation_weights_ssyk_by_municipality", conn,
              if_exists="replace", index=False)
    conn.close()
    print(f"[yrkesvikter] {ut.municipal_code.nunique()} kommuner, "
          f"{ut.occupation_code.nunique()} yrken, {len(ut)} rader")
    return len(ut)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("Ange rikstabell och länstabell: "
                         "python -m core.database.load_yrkesregister "
                         "data/TAB4347_sv.csv data/TAB4441_sv.csv")
    load_yrkesregister(sys.argv[1], sys.argv[2],
                       db_path=sys.argv[3] if len(sys.argv) > 3
                       else os.path.join("data", "worm.sqlite3"))
