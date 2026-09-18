"""
validera_yrken_per_kommun.py  (scripts/)
----------------------------------------
Jobbens yrkesfördelning per kommun, som mekanismen ger den, mot den faktiska
i TAB4436 (dagbefolkning per kommun, yrke och bransch). Alla 290 kommuner:
Ovansiljan är ett testfall, och modellen ska fungera för valfri kommun.

MEKANISMEN (core/bransch.py). Kommunens jobb fördelas på branscher efter
dagbefolkningen, storleksklassen dras givet branschen ur riket, och yrket ur
rikets P(SSYK3 | bransch, klass). I väntevärde summeras storleken bort, och
kommunens förväntade fördelning är

    P(ssyk | kommun) = sum_bransch P(bransch | kommun) * P(ssyk | bransch, riket)

Det är antagandet att yrke och kommun är betingat oberoende givet bransch.
Valideringen mäter hur långt det bär.

MÅTTEN. Gemensam massa sum_ssyk min(p, q) mellan förväntad och faktisk
fördelning (1 = identiska). Två referenser gör talet tolkningsbart:
- UTAN BRANSCH: rikets yrkesfördelning rakt av. Skillnaden mot mekanismen är
  vad kommunens branschmix förklarar.
- BRUSGOLV: gemensam massa mellan den faktiska fördelningen och ett
  slumpurval av kommunens egen storlek ur den. En liten kommun är klumpig av
  sig själv, och ingen mekanism som drar jobb ett och ett kan komma närmare
  sanningen än så i en enskild realisering.
Därtill avståndet i uppgiftsrummet mellan förväntad och faktisk tyngdpunkt,
där varje SSYK3-grupp placeras i crosswalkens viktade medelpunkt. Det säger
om felen spelar roll geometriskt eller bara byter grannyrken.

SSYK3-nivå, inte O*NET: crosswalken är densamma på båda sidor och hade bara
lagt till brus.

    python scripts/validera_yrken_per_kommun.py [--ut analysis/yrken_per_kommun.csv]
"""
import argparse
import os
import sqlite3
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OKANT_YRKE, OKAND_BRANSCH = "0002", "00"


def las(conn):
    """(faktisk, p_yrke_bransch, lagen) ur databasen.

    faktisk: anställda per kommun, bransch och yrke (dagbef, senaste året),
    utan restposterna. p_yrke_bransch: rikets P(ssyk | bransch), storleken
    summerad. lagen: SSYK3-gruppernas tyngdpunkt i uppgiftsrummet."""
    faktisk = pd.read_sql(
        "SELECT municipal_code AS kommun, sni_code AS bransch, ssyk_code AS ssyk, "
        "       SUM(employed) AS n "
        "  FROM employment_workplace_occupation_sni "
        " WHERE year = (SELECT MAX(year) FROM employment_workplace_occupation_sni) "
        " GROUP BY 1, 2, 3", conn)
    faktisk = faktisk[(faktisk.ssyk != OKANT_YRKE) & (faktisk.bransch != OKAND_BRANSCH)]
    riket = pd.read_sql("SELECT sni_code AS bransch, ssyk_code AS ssyk, "
                        "SUM(employed) AS n FROM occupation_by_industry GROUP BY 1, 2", conn)
    riket = riket[riket.ssyk != "000"]
    p = riket.pivot(index="bransch", columns="ssyk", values="n").fillna(0.0)
    p = p.div(p.sum(axis=1), axis=0)
    cw = pd.read_sql("SELECT c.occupation_code AS ssyk, c.share, g.x_occ, g.y_occ "
                     "  FROM ssyk3_onet_crosswalk c "
                     "  JOIN onet_occupation_space g ON g.onet_code = c.onet_code", conn)
    cw["wx"], cw["wy"] = cw.share * cw.x_occ, cw.share * cw.y_occ
    g = cw.groupby("ssyk")[["wx", "wy", "share"]].sum()
    lagen = pd.DataFrame({"x": g.wx / g.share, "y": g.wy / g.share})
    return faktisk, p, lagen


def overlapp(p: pd.Series, q: pd.Series) -> float:
    a, b = p.align(q, fill_value=0.0)
    return float(np.minimum(a, b).sum())


def forvantad(branschandel: pd.Series, p_yrke_bransch: pd.DataFrame) -> pd.Series:
    """sum_bransch P(bransch | kommun) * P(ssyk | bransch)."""
    b = branschandel.reindex(p_yrke_bransch.index).fillna(0.0)
    saknas = set(branschandel.index) - set(p_yrke_bransch.index)
    if saknas:
        raise ValueError(f"branscherna {sorted(saknas)} saknas i rikets fördelning")
    return (p_yrke_bransch.mul(b, axis=0)).sum(axis=0)


def brusgolv(q: pd.Series, n: int, rng, upprepningar=20) -> float:
    """Gemensam massa mellan q och ett urval av storlek n ur q, i medel."""
    v = q.to_numpy()
    ut = [np.minimum(rng.multinomial(n, v / v.sum()) / n, v).sum()
          for _ in range(upprepningar)]
    return float(np.mean(ut))


def tyngdpunkt(p: pd.Series, lagen: pd.DataFrame):
    l_ = lagen.reindex(p.index)
    ok = l_.x.notna()
    w = p[ok] / p[ok].sum()
    return float((w * l_.x[ok]).sum()), float((w * l_.y[ok]).sum())


def validera(conn, rng=None):
    rng = rng or np.random.default_rng(0)
    faktisk, p_yb, lagen = las(conn)
    utan = faktisk.groupby("ssyk").n.sum()
    utan = utan / utan.sum()
    rader = []
    for kommun, g in faktisk.groupby("kommun"):
        n = int(g.n.sum())
        q = g.groupby("ssyk").n.sum() / n
        andel = g.groupby("bransch").n.sum() / n
        p = forvantad(andel, p_yb)
        fx, fy = tyngdpunkt(q, lagen)
        px, py = tyngdpunkt(p, lagen)
        rader.append({"kommun": kommun, "anstallda": n,
                      "mekanism": overlapp(p, q), "utan_bransch": overlapp(utan, q),
                      "brusgolv": brusgolv(q, n, rng),
                      "tyngdpunkt_avstand": float(np.hypot(fx - px, fy - py))})
    return pd.DataFrame(rader)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/worm.sqlite3")
    ap.add_argument("--ut", default="analysis/yrken_per_kommun.csv")
    a = ap.parse_args()
    conn = sqlite3.connect(a.db)
    df = validera(conn)
    namn = pd.read_sql("SELECT municipal_code AS kommun, municipality AS namn "
                       "FROM municipalities", conn)
    df = df.merge(namn.drop_duplicates("kommun"), on="kommun", how="left")
    os.makedirs(os.path.dirname(a.ut), exist_ok=True)
    df.sort_values("kommun").to_csv(a.ut, index=False)
    print(f"{len(df)} kommuner -> {a.ut}\n")
    kv = df[["mekanism", "utan_bransch", "brusgolv", "tyngdpunkt_avstand"]].quantile(
        [0.1, 0.5, 0.9]).round(3)
    print(kv.to_string())
    df["storlek"] = pd.qcut(df.anstallda, 4, labels=["minst", "små", "större", "störst"])
    print("\nper storlekskvartil (median):")
    print(df.groupby("storlek", observed=True)[["anstallda", "mekanism", "utan_bransch",
                                                "brusgolv", "tyngdpunkt_avstand"]]
          .median().round(3).to_string())
    kol = [c for c in ("kommun", "namn", "anstallda", "mekanism", "brusgolv",
                       "tyngdpunkt_avstand") if c in df]
    print("\nsämst mot brusgolvet:")
    df["mot_golv"] = df.mekanism - df.brusgolv
    print(df.sort_values("mot_golv").head(8)[kol + ["mot_golv"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
