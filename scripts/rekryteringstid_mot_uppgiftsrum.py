"""
rekryteringstid_mot_uppgiftsrum.py  (scripts/)
----------------------------------------------
Ställer SCB:s genomsnittliga rekryteringstid per näringsgren mot branschens
genomsnittliga position i det polära uppgiftsrummet.

FRÅGAN. Modellen säger att specialiserade yrken är svårare att fylla: en
kompetenscirkel av given radie täcker färre jobb längre ut i rummet. Om det
stämmer ska rekryteringstiden stiga med chi -- och SCB mäter rekryteringstiden
utan att känna till uppgiftsrummet. Ett samband är därför en OBEROENDE
bekräftelse och inte en kalibrering.

DESIGNEN ÄR TOLV PUNKTER, INTE TUSEN. Det frestande vore att ge varje yrke en
rekryteringstid genom att väga branschernas tal, och sedan regressera på 1 016
punkter. Det vore fel: all variation kommer från tretton branschvärden, två
yrken i samma bransch får identisk tid, och R2 skulle mäta att tolv tal
replikerats. Här går riktningen åt andra hållet -- varje bransch får en
POSITION, vägd över de yrken den består av -- och varje punkt är då en
oberoende mätning.

KEDJAN per bransch:
    occupation_by_industry   SSYK3 x SNI, sysselsatta (rikets yrkesregister)
    ssyk3_onet_crosswalk     SSYK3 -> O*NET med andelar
    onet_occupation_space    O*NET -> chi, xi, r_o

    chi(bransch) = summa_yrken syss(yrke, bransch) * chi(yrke)
                   / summa_yrken syss(yrke, bransch)

SCB:s TAL GÄLLER NÄRINGSLIVET. Offentlig förvaltning slutade rapportera
bemannade mot obemannade lediga jobb 2006K2, så vård, skola och kommunal
förvaltning saknas i referensen även om branschgruppen P+Q finns med -- den
avser privata utförare. Det ska stå i varje tolkning av resultatet.

OCH TALET ÄR LITTLES LAG, inte en uppmätt varaktighet: SCB definierar
genomsnittlig rekryteringstid som antalet lediga jobb i relation till antalet
nyanställningar (kvalitetsdeklaration AM0701, avsnitt 1.2.2). Samma räkning som
analysis.py gör. 81 dagar för IT betyder därför inte att en IT-rekrytering tar
längre tid, utan att branschen bär fler öppna tjänster per anställning.

    python scripts/rekryteringstid_mot_uppgiftsrum.py
    python scripts/rekryteringstid_mot_uppgiftsrum.py --ar 2023 --csv ut.csv
"""
import argparse
import os
import re
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database.load_commuting_matrix import _las_rader, _sep  # noqa: E402

DB = "data/worm.sqlite3"
KALLA = "data/TAB4307_sv.csv"
SNI_BOKSTAV = re.compile(r"^([A-U][+A-U]*)")


def las_rekryteringstid(csv_path, ar="2023"):
    """SCB:s rekryteringstid per näringsgren, i dagar.

    Talet publiceras i månader. 0.7 månader blir 21 dagar; aggregatet
    A-S samtliga näringsgrenar ligger på 32 dagar för 2023.
    """
    rader, kodning = _las_rader(csv_path)
    sep = _sep(rader)
    start = next((i for i, r in enumerate(rader[:20]) if "yrke" in r.lower()
                  or "näringsgren" in r.lower()), 0)
    d = pd.read_csv(csv_path, sep=sep, skiprows=start, dtype=str,
                    encoding=kodning, engine="python", quotechar='"')
    d.columns = [c.strip() for c in d.columns]
    sni = next(c for c in d.columns if "näringsgren" in c.lower())
    innehall = next(c for c in d.columns if "tabellinnehåll" in c.lower())
    kvartal = next(c for c in d.columns if "kvartal" in c.lower())
    varde = d.columns[-1]

    d = d[d[innehall].astype(str).str.strip().str.lower().str.startswith("rekryteringstid")]
    d = d[d[kvartal].astype(str).str[:4] == str(ar)]
    if d.empty:
        raise ValueError(f"Inga rekryteringstider för {ar}")
    d["manader"] = pd.to_numeric(d[varde].astype(str).str.replace(",", "."),
                                 errors="coerce")
    d["sni_code"] = d[sni].astype(str).str.strip().str.extract(SNI_BOKSTAV.pattern)[0]
    ut = (d.dropna(subset=["manader", "sni_code"])
          .groupby(["sni_code"], as_index=False)
          .agg(dagar=("manader", lambda s: float(s.mean()) * 30.44),
               etikett=(sni, "first")))
    return ut


def _bokstaver(kod):
    """Näringsgrensbokstäverna i en kod: "M+N" -> {"M","N"}."""
    return {b for b in str(kod).upper() if "A" <= b <= "U"}


def harmonisera(tid, pos):
    """Slår ihop grupper tills de två tabellerna beskriver samma indelning.

    GRUPPERINGARNA SKILJER SIG. TAB4307 har P+Q, K+L, M, N och R+S;
    yrkesregistret har P, Q, K, L, M+N och R+S+T+U. En ren strängmatchning
    tappar tyst de grupper som inte stämmer -- i provet försvann P+Q, alltså
    vård och utbildning, vilket är den bransch som betyder mest i en
    glesbygdskommun.

    Grupperna slås därför ihop till den GROVSTE gemensamma indelningen: två
    koder hör ihop om deras bokstavsmängder överlappar, och resultatet blir
    unionen. P+Q möter P och Q och blir en grupp; M och N möter M+N och blir
    en. Rekryteringstiden vägs med branschens sysselsättning, eftersom ett
    ovägt medelvärde av M och N hade gett en liten bransch samma tyngd som en
    stor.
    """
    komponenter = []
    for kod in list(tid["sni_code"]) + list(pos["sni_code"]):
        b = _bokstaver(kod)
        if not b:
            continue
        traff = [k for k in komponenter if k & b]
        for k in traff:
            komponenter.remove(k)
        komponenter.append(b.union(*traff) if traff else b)

    def grupp(kod):
        b = _bokstaver(kod)
        for k in komponenter:
            if k & b:
                return "+".join(sorted(k))
        return None

    t = tid.copy()
    p_ = pos.copy()
    t["grupp"] = t["sni_code"].map(grupp)
    p_["grupp"] = p_["sni_code"].map(grupp)

    # Positionen vägs med sysselsättningen; rekryteringstiden med samma vikt,
    # hämtad från positionstabellen.
    vikt = p_.groupby("grupp")["syss"].sum()
    p_agg = (p_.groupby("grupp")
             .apply(lambda g: pd.Series({
                 "chi": np.average(g["chi"], weights=g["syss"]),
                 "r_o": np.average(g["r_o"], weights=g["syss"]),
                 "r_req": np.average(g["r_req"], weights=g["syss"]),
                 "syss": g["syss"].sum(),
                 "tackning": np.average(g["tackning"], weights=g["syss"]),
             }), include_groups=False).reset_index())
    t = t.merge(vikt.rename("w"), left_on="grupp", right_index=True, how="left")
    t["w"] = t["w"].fillna(1.0)
    t_agg = (t.groupby("grupp")
             .apply(lambda g: pd.Series({
                 "dagar": np.average(g["dagar"], weights=g["w"]),
                 "etikett": " / ".join(sorted(set(g["etikett"].str[:28]))),
                 "n_kallgrupper": len(g),
             }), include_groups=False).reset_index())
    return t_agg.merge(p_agg, on="grupp", how="inner")


def branschernas_position(conn):
    """Varje näringsgrens vägda position i uppgiftsrummet.

    Vikten är sysselsättningen per yrke och bransch ur rikets yrkesregister,
    spridd över O*NET-koder med crosswalkens andelar. En bransch vars yrken
    saknar O*NET-koppling -- militära yrken och okänt yrke -- tappar den delen
    av sin vikt, och andelen som nådde fram rapporteras så att bortfallet är
    synligt.
    """
    riket = pd.read_sql("SELECT ssyk_code, sni_code, employed "
                        "FROM occupation_by_industry", conn)
    riket = riket.groupby(["ssyk_code", "sni_code"], as_index=False)["employed"].sum()
    cw = pd.read_sql("SELECT occupation_code, onet_code, share "
                     "FROM ssyk3_onet_crosswalk", conn)
    geo = pd.read_sql('SELECT onet_code, chi, xi, r_o, r_req, "Job Family" fam '
                      'FROM onet_occupation_space', conn)

    d = riket.merge(cw, left_on="ssyk_code", right_on="occupation_code")
    d = d.merge(geo, on="onet_code")
    d["v"] = d["employed"] * d["share"]

    def vagt(g, kol):
        return float(np.average(g[kol], weights=g["v"])) if g["v"].sum() > 0 else np.nan

    ut = (d.groupby("sni_code")
          .apply(lambda g: pd.Series({
              "chi": vagt(g, "chi"),
              "r_o": vagt(g, "r_o"),
              "r_req": vagt(g, "r_req"),
              "syss": float(g["v"].sum()),
              "n_yrken": int(g["ssyk_code"].nunique()),
          }), include_groups=False)
          .reset_index())

    # Hur stor del av branschens sysselsättning som nådde fram genom
    # crosswalken. Låg andel gör branschens position osäker: det som faller
    # bort är SSYK-grupper utan O*NET-koppling.
    tot = riket.groupby("sni_code")["employed"].sum()
    natt = (d.drop_duplicates(["sni_code", "ssyk_code"])
            .groupby("sni_code")["employed"].sum())
    ut["tackning"] = (ut["sni_code"].map(natt) / ut["sni_code"].map(tot)).round(3)
    return ut


def main():
    p = argparse.ArgumentParser(
        description="Rekryteringstid mot position i uppgiftsrummet.")
    p.add_argument("--db", default=DB)
    p.add_argument("--kalla", default=KALLA)
    p.add_argument("--ar", default="2023")
    p.add_argument("--csv", default=None, help="skriv tabellen till fil")
    a = p.parse_args()

    tid = las_rekryteringstid(a.kalla, ar=a.ar)
    conn = sqlite3.connect(a.db)
    pos = branschernas_position(conn)
    conn.close()

    # Aggregatet A-S är summan av de övriga och ingen egen observation. Bort
    # innan harmoniseringen, annars sväljer det alla andra grupper.
    tid = tid[~tid["etikett"].str.contains("samtliga", case=False, na=False)]
    d = harmonisera(tid, pos)
    d = d.dropna(subset=["dagar", "chi"]).sort_values("chi")
    saknade = set(tid["sni_code"]) - set(
        k for g in d["grupp"] for k in [g])
    if len(d) < len(tid):
        print(f"\n{len(tid)} källgrupper slogs ihop till {len(d)} jämförbara.")
    if len(d) < 4:
        raise SystemExit(f"Bara {len(d)} branscher matchade -- för få för att "
                         f"säga något.")

    print(f"\nRekryteringstid mot uppgiftsrummets radie, {a.ar}. "
          f"SCB:s tal gäller NÄRINGSLIVET;\noffentlig förvaltning saknas sedan "
          f"2006K2, så P+Q avser privata utförare.\n")
    print(f"{'bransch':<46}{'chi':>7}{'r_req':>7}{'dagar':>7}{'täckn':>7}")
    for r in d.itertuples():
        print(f"{r.etikett[:45]:<46}{r.chi:>7.3f}{r.r_req:>7.3f}"
              f"{r.dagar:>7.0f}{r.tackning:>7.2f}")

    for namn in ("chi", "r_req", "r_o"):
        x = d[namn].to_numpy(dtype=float)
        y = d["dagar"].to_numpy(dtype=float)
        if np.std(x) == 0:
            continue
        r = float(np.corrcoef(x, y)[0, 1])
        rho = float(pd.Series(x).corr(pd.Series(y), method="spearman"))
        b, a0 = np.polyfit(x, y, 1)
        print(f"\n{namn:<6} Pearson r = {r:+.3f}   Spearman rho = {rho:+.3f}   "
              f"lutning {b:+.0f} dagar per enhet")
    print(f"\nn = {len(d)} branscher. Sambandet prövas PER BRANSCH och inte per\n"
          "yrke: all variation i rekryteringstiden kommer från de här talen, och\n"
          "en regression på yrkesnivå hade bara replikerat dem.\n")

    if a.csv:
        d.to_csv(a.csv, index=False)
        print(f"Skrev {a.csv}")


if __name__ == "__main__":
    main()
