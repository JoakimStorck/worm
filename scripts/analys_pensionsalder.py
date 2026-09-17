#!/usr/bin/env python
"""Samvarierar medelpensioneringsåldern med riktningen i uppgiftsrummet?

    python scripts/analys_pensionsalder.py data/Yrkesuppdelat.csv \\
        --yrkesfil data/TAB4441_sv.csv

Pensionsmyndighetens rapport Pensionsåldrar och arbetslivets längd (2026)
redovisar medelpensioneringsålder per yrkesgrupp. Spridningen är omkring tre
år, och ytterlighetarna ligger där geometrin förutsäger: fysiker, kemister och
universitetslärare högst, processoperatörer och montörer lägst. Frågan är om
mönstret följer den angulära koordinaten ξ eller bara utbildningsnivån.

MÅTTET. Yrkesgrupperna anpassas mot

    A(ξ) = a + b cos ξ + c sin ξ

vilket är samma form som papprets löneekvation och som rekryteringstiden i
0147-0149. Toppriktningen atan2(c, b) och amplitudens storlek är det som
prövas mot prediktionen: en topp i den norra halvan.

KONTROLLEN AVGÖR TOLKNINGEN. Medelpensioneringsåldern samvarierar med
utbildningsnivå, och utbildningsnivån samvarierar med ξ. En obetingad
anpassning kan därför visa rätt mönster av fel skäl. Intjänandeåren används
som kontroll: de är antalet år med pensionsrätt och stiger med tidigt inträde
och sammanhängande arbetsliv, alltså ungefär motsatsen till lång utbildning.
Står riktningen kvar när de är med är fyndet geometrins; faller den bort
följer pensionsåldern utbildning och inte domän, vilket också är ett svar.

KEDJAN från yrkesnamn till riktning: namnet matchas mot SSYK 2012 på
tresiffernivå ur yrkesregistrets egen benämningslista, SSYK3 översätts till
O*NET-koder med ssyk3_onet_crosswalk, och varje O*NET-kod har en position i
onet_occupation_space. Riktningen per yrkesgrupp är den viktade
VEKTORSUMMANS riktning och inte medelvärdet av ξ: vinklar är cirkulära, och
ett medelvärde av 350 och 10 grader blir 180 i stället för 0.
"""
import argparse
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from core.database.utils import las_rader

DB = os.path.join("data", "worm.sqlite3")
SSYK3 = re.compile(r"\b(\d{3})\b")


def _sep(rader):
    huvud = "\n".join(rader[:5])
    return ";" if huvud.count(";") > huvud.count(",") else ","


def normalisera(namn):
    """Yrkesnamn till jämförbar form.

    SCB och Pensionsmyndigheten använder samma SSYK-benämningar men inte
    alltid samma skrivsätt: "m.fl." hänger med ibland och inte alltid, och
    bindestreck, komma och dubbla mellanslag varierar.
    """
    s = str(namn).lower().strip().strip('"')
    s = re.sub(r"\bm\.?\s*fl\.?\b", " ", s)
    s = re.sub(r"\bo\.?\s*dyl\.?\b", " ", s)
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"[,;.]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def las_pensionsalder(csv_path):
    """Pensionsmyndighetens yrkesuppdelade underlag."""
    rader, kodning = las_rader(csv_path)
    df = pd.read_csv(csv_path, sep=_sep(rader), dtype=str, encoding=kodning,
                     engine="python")
    df.columns = [str(c).strip().strip('"') for c in df.columns]

    def kol(*n):
        for c in df.columns:
            if any(str(c).lower().startswith(x) for x in n):
                return c
        raise ValueError(f"saknar kolumn {n} i {csv_path}: {list(df.columns)}")

    def tal(serie):
        # Svenskt decimalkomma.
        return pd.to_numeric(serie.astype(str).str.strip()
                             .str.replace("\u00a0", "", regex=False)
                             .str.replace(" ", "", regex=False)
                             .str.replace(",", ".", regex=False), errors="coerce")

    ut = pd.DataFrame({
        "yrke": df[kol("yrke")].astype(str).str.strip().str.strip('"'),
        "kon": df[kol("kön", "kon")].astype(str).str.strip().str.strip('"'),
        "antal": tal(df[kol("antalnya", "antal")]),
        "intjanandear": tal(df[kol("intjänande", "intjanande")]),
        "alder": tal(df[kol("medelpension")]),
    }).dropna(subset=["alder", "antal"])
    ut["nyckel"] = ut["yrke"].map(normalisera)
    return ut


def las_ssyk_namn(csv_path):
    """SSYK3-kod och benämning ur yrkesregistrets egen fil.

    Yrkeskolumnen ser ut som "213 Biologer, farmakologer och specialister
    inom lant- och skogsbruk": koden först, benämningen efter. Läsaren för
    yrkesregistret plockar bara koden, så benämningarna hämtas här.
    """
    rader, kodning = las_rader(csv_path)
    sep = _sep(rader)
    start = next((i for i, r in enumerate(rader[:25])
                  if "yrke" in r.lower() and r.count(sep) >= 1), 0)
    df = pd.read_csv(csv_path, sep=sep, skiprows=start, dtype=str,
                     encoding=kodning, engine="python")
    df.columns = [str(c).strip().strip('"') for c in df.columns]
    kol = next((c for c in df.columns if "yrke" in str(c).lower()), None)
    if kol is None:
        raise ValueError(f"hittar ingen yrkeskolumn i {csv_path}")
    v = df[kol].astype(str).str.strip().str.strip('"').drop_duplicates()
    ut = []
    for s in v:
        m = SSYK3.search(s)
        if not m:
            continue
        namn = s[m.end():].strip(" -–:")
        if namn:
            ut.append({"ssyk3": m.group(1), "namn": namn,
                       "nyckel": normalisera(namn)})
    return pd.DataFrame(ut).drop_duplicates("nyckel")


def riktning_per_ssyk(conn):
    """Vektorsumma per SSYK3 ur crosswalken och uppgiftsrummet."""
    d = pd.read_sql(
        "SELECT c.occupation_code AS ssyk3, c.share, g.x_occ, g.y_occ, g.chi "
        "  FROM ssyk3_onet_crosswalk c "
        "  JOIN onet_occupation_space g ON g.onet_code = c.onet_code", conn)
    if d.empty:
        raise SystemExit("ssyk3_onet_crosswalk eller onet_occupation_space är tom")
    d["share"] = pd.to_numeric(d["share"], errors="coerce").fillna(0.0)
    g = d.groupby("ssyk3").apply(
        lambda t: pd.Series({
            "x": float((t["share"] * t["x_occ"]).sum()),
            "y": float((t["share"] * t["y_occ"]).sum()),
            "chi": float((t["share"] * t["chi"]).sum() / max(t["share"].sum(), 1e-12)),
            "vikt": float(t["share"].sum())}),
        include_groups=False)
    g["xi"] = np.degrees(np.arctan2(g["y"], g["x"])) % 360.0
    return g.reset_index()


def harmonisk(d, vikt=None, kontroller=(), kluster="ssyk3", harmonik=1):
    """A = a + b cos ξ + c sin ξ, med toppriktning och delta-metods-CI.

    KLUSTRADE STANDARDFEL. Varje yrke förekommer två gånger i underlaget, en
    gång per kön, och de två raderna är inte oberoende observationer: samma
    yrke, samma position, i stort sett samma pensionsbeteende. Behandlas de
    som oberoende underskattas standardfelen med ungefär en faktor roten ur
    två. Kovariansen skattas därför med en sandwich klustrad på yrke, vilket
    tillåter godtycklig korrelation inom yrket.
    """
    xi = np.radians(d["xi"].to_numpy(dtype=float))
    kolumner = [np.ones(len(d)), np.cos(xi), np.sin(xi)]
    namn = ["konstant", "cos", "sin"]
    for k in range(2, int(harmonik) + 1):
        kolumner += [np.cos(k * xi), np.sin(k * xi)]
        namn += [f"cos{k}", f"sin{k}"]
    for k in kontroller:
        v = pd.to_numeric(d[k], errors="coerce").to_numpy(dtype=float)
        kolumner.append(v - np.nanmean(v))
        namn.append(k)
    X = np.column_stack(kolumner)
    y = d["alder"].to_numpy(dtype=float)
    w = (np.ones(len(d)) if vikt is None
         else np.clip(pd.to_numeric(d[vikt], errors="coerce").to_numpy(float), 0, None))
    sw = np.sqrt(w)
    Xw, yw = X * sw[:, None], y * sw
    beta, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
    resid = yw - Xw @ beta
    XtX_inv = np.linalg.pinv(Xw.T @ Xw)
    if kluster is not None and kluster in d.columns:
        # Sandwich med kluster: sum_g X_g' u_g u_g' X_g, med den vanliga
        # korrigeringen för antalet kluster.
        meat = np.zeros((X.shape[1], X.shape[1]))
        grupper = pd.Series(d[kluster].to_numpy())
        for _, i in grupper.groupby(grupper).groups.items():
            idx = grupper.index.get_indexer(i) if hasattr(i, "__len__") else [i]
            Xg, ug = Xw[idx], resid[idx]
            s = Xg.T @ ug
            meat += np.outer(s, s)
        G = int(grupper.nunique())
        skala = (G / max(G - 1, 1)) * ((len(d) - 1) /
                                       max(len(d) - X.shape[1], 1))
        kov = skala * XtX_inv @ meat @ XtX_inv
    else:
        dof = max(len(d) - X.shape[1], 1)
        kov = (float(resid @ resid) / dof) * XtX_inv
    b, c = beta[1], beta[2]
    amp = float(np.hypot(b, c))
    topp = float(np.degrees(np.arctan2(c, b)) % 360.0)
    # Delta-metoden för riktningen: gradienten av atan2(c, b).
    n2 = b * b + c * c
    grad = np.array([-c / n2, b / n2]) if n2 > 0 else np.zeros(2)
    var_topp = float(grad @ kov[1:3, 1:3] @ grad)
    se_topp = float(np.degrees(np.sqrt(max(var_topp, 0.0))))
    grad_amp = np.array([b / amp, c / amp]) if amp > 0 else np.zeros(2)
    se_amp = float(np.sqrt(max(grad_amp @ kov[1:3, 1:3] @ grad_amp, 0.0)))
    pred = X @ beta
    ss = ((y - y.mean()) ** 2 * w).sum()
    r2 = 1 - float(((y - pred) ** 2 * w).sum()) / float(ss) if ss > 0 else np.nan
    return {"n": int(len(d)), "niva": float(beta[0]), "topp": topp,
            "se_topp": se_topp, "amplitud": amp, "se_amp": se_amp,
            "R2": float(r2), "beta": beta, "kov": kov,
            "kluster": int(pd.Series(d[kluster]).nunique())
            if kluster in d.columns else 0,
            "koefficienter": dict(zip(namn, [float(v) for v in beta]))}


def per_yrke(d):
    """Ett yrke per rad: könen vägs ihop med antalet nya pensionärer.

    Rader är inte observationer när samma yrke förekommer två gånger. För
    sektorer och rutor ska yrket räknas en gång, annars ser ett yrke med
    båda könen ut som två oberoende belägg för samma position.
    """
    return d.groupby(["yrke", "ssyk3"]).apply(
        lambda t: pd.Series({
            "x": float(t["x"].iloc[0]), "y": float(t["y"].iloc[0]),
            "xi": float(t["xi"].iloc[0]), "chi": float(t["chi"].iloc[0]),
            "antal": float(t["antal"].sum()),
            "alder": float(np.average(t["alder"], weights=t["antal"]))}),
        include_groups=False).reset_index()


def sektorer(y, n=8):
    """Medelålder per riktningssektor, utan att anta någon form på kurvan."""
    bredd = 360.0 / n
    s = ((y["xi"] + bredd / 2) % 360 // bredd).astype(int)
    ut = []
    for i in range(n):
        t = y[s == i]
        mitt = (i * bredd) % 360
        ut.append({"sektor": f"{mitt:.0f}°", "yrken": int(len(t)),
                   "personer": int(t["antal"].sum()) if len(t) else 0,
                   "alder": float(np.average(t["alder"], weights=t["antal"]))
                   if len(t) else np.nan})
    return pd.DataFrame(ut)


def rutnat(y, n=5, minst=2):
    """Medelålder per ruta i planet, och gradienten genom rutorna.

    RUTAN ÄR OBSERVATIONEN, inte yrket. Punkttätheten är starkt ojämn -- den
    östra halvan har tre gånger fler yrken än den nordvästra -- och en
    anpassning på yrken låter därför de täta områdena bestämma riktningen.
    Rutnätet ger varje bebodd del av planet samma vikt, vilket är den
    oberoende prövningen av om lutningen finns i hela planet eller bara där
    punkterna råkar ligga.

    Gradienten anpassas som alder = a + b x + c y på rutmedelvärdena. Den
    antar ingen cirkulär form, till skillnad från den harmoniska
    anpassningen, och bär därmed inte dess antagande.

    VAD RUTNÄTET INTE SKYDDAR MOT: en region som avviker i nivå drar nu lika
    mycket som vilken annan region som helst, eftersom den väger lika. Med
    ett tiotal bebodda rutor är varje ruta en dryg tiondel av vikten.
    Riktningen ur rutnätet ska därför läsas tillsammans med hur den ändras
    med upplösningen, inte som ett tal.
    """
    r = float(max(y["x"].abs().max(), y["y"].abs().max()))
    kant = np.linspace(-r, r, n + 1)
    ix = np.clip(np.digitize(y["x"], kant) - 1, 0, n - 1)
    iy = np.clip(np.digitize(y["y"], kant) - 1, 0, n - 1)
    rutor, karta = [], np.full((n, n), np.nan)
    antal = np.zeros((n, n), dtype=int)
    for i in range(n):
        for j in range(n):
            t = y[(ix == i) & (iy == j)]
            antal[j, i] = len(t)
            if len(t):
                karta[j, i] = float(np.average(t["alder"], weights=t["antal"]))
            if len(t) >= minst:
                rutor.append({"x": float(t["x"].mean()), "y": float(t["y"].mean()),
                              "alder": karta[j, i]})
    R = pd.DataFrame(rutor)
    grad = None
    if len(R) >= 6:
        X = np.column_stack([np.ones(len(R)), R["x"], R["y"]])
        b, *_ = np.linalg.lstsq(X, R["alder"].to_numpy(dtype=float), rcond=None)
        grad = {"dx": float(b[1]), "dy": float(b[2]),
                "riktning": float(np.degrees(np.arctan2(b[2], b[1])) % 360),
                "kvot": float(b[2] / b[1]) if b[1] else np.nan,
                "lutning": float(np.hypot(b[1], b[2])), "rutor": int(len(R))}
    return karta, antal, kant, grad


def figur(d, r, path):
    """Två paneler: åldern mot riktningen med den anpassade kurvan, och
    yrkesgrupperna i planet färgade efter ålder."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(11, 4.8))
    ax = fig.add_subplot(1, 2, 1)
    storlek = 8 + 60 * (d["antal"] / d["antal"].max()) ** 0.5
    for kon, m in (("Kvinnor", "o"), ("Män", "^")):
        t = d[d["kon"].str.lower().str.startswith(kon[:4].lower())]
        if len(t):
            ax.scatter(t["xi"], t["alder"], s=storlek.loc[t.index], marker=m,
                       alpha=0.55, edgecolor="none", label=kon)
    grid = np.linspace(0, 360, 721)
    b = r["beta"]
    kurva = b[0] + b[1] * np.cos(np.radians(grid)) + b[2] * np.sin(np.radians(grid))
    # Pointwise band via delta-metoden på (a, b, c).
    G = np.column_stack([np.ones_like(grid), np.cos(np.radians(grid)),
                         np.sin(np.radians(grid))])
    kov = r["kov"][:3, :3]
    se = np.sqrt(np.clip(np.einsum("ij,jk,ik->i", G, kov, G), 0, None))
    ax.plot(grid, kurva, color="black", lw=1.6)
    ax.fill_between(grid, kurva - 1.96 * se, kurva + 1.96 * se, color="black",
                    alpha=0.12, lw=0)
    ax.axvline(r["topp"], color="firebrick", ls="--", lw=1)
    ax.annotate(f"topp {r['topp']:.0f}°", (r["topp"], ax.get_ylim()[1]),
                xytext=(4, -12), textcoords="offset points", color="firebrick",
                fontsize=9)
    ax.set_xticks(range(0, 361, 45))
    ax.set_xlabel("Riktning i uppgiftsrummet ξ (grader)")
    ax.set_ylabel("Medelpensioneringsålder (år)")
    ax.set_title("A. Ålder mot riktning", fontsize=10, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.grid(alpha=0.25)

    axp = fig.add_subplot(1, 2, 2, projection="polar")
    sc = axp.scatter(np.radians(d["xi"]), d["chi"], c=d["alder"],
                     s=storlek, cmap="viridis", alpha=0.85, edgecolor="none")
    axp.set_theta_zero_location("E")
    axp.set_rlabel_position(135)
    axp.set_title("B. Yrkesgrupperna i planet", fontsize=10, loc="left")
    axp.plot([np.radians(r["topp"])] * 2, [0, d["chi"].max() * 1.05],
             color="firebrick", ls="--", lw=1)
    fig.colorbar(sc, ax=axp, pad=0.1, label="Medelpensioneringsålder (år)")

    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    print(f"\nSparad: {path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pensionsfil")
    ap.add_argument("--yrkesfil", default="data/TAB4441_sv.csv",
                    help="yrkesregisterfil med SSYK3-benämningar")
    ap.add_argument("--db", default=DB)
    ap.add_argument("--figur", default="analysis/figures/pensionsalder_xi.pdf")
    ap.add_argument("--rutor", type=int, default=5,
                    help="rutnätets upplösning (riktningen vandrar med den)")
    a = ap.parse_args()

    pens = las_pensionsalder(a.pensionsfil)
    namn = las_ssyk_namn(a.yrkesfil)
    conn = sqlite3.connect(a.db)
    geom = riktning_per_ssyk(conn)
    conn.close()

    d = pens.merge(namn[["ssyk3", "nyckel"]], on="nyckel", how="left")
    utan = d[d["ssyk3"].isna()]
    d = d.dropna(subset=["ssyk3"]).merge(geom, on="ssyk3", how="inner")

    print(f"{len(pens)} rader i underlaget, {len(d)} matchade mot SSYK3 och "
          f"uppgiftsrummet")
    if len(utan):
        print(f"\nOMATCHADE ({utan['yrke'].nunique()} yrken, "
              f"{int(utan['antal'].sum())} personer):")
        for y in sorted(utan["yrke"].unique())[:20]:
            print(f"   {y}")
    if len(d) < 12:
        raise SystemExit("för få matchade yrken för en harmonisk anpassning")

    print(f"\nmedelpensioneringsålder: {d['alder'].min():.1f}-{d['alder'].max():.1f}, "
          f"viktat medel {np.average(d['alder'], weights=d['antal']):.2f}")

    print("   (standardfel klustrade på yrke: de två könsraderna per yrke är "
          "inte oberoende)")
    for etikett, kontroller in (("utan kontroll", ()),
                                ("med intjänandeår", ("intjanandear",)),
                                ("med intjänandeår och chi", ("intjanandear", "chi"))):
        r = harmonisk(d, vikt="antal", kontroller=kontroller)
        print(f"\n--- {etikett} (n={r['n']}, {r['kluster']} kluster)")
        print(f"   topp {r['topp']:.1f}° ± {r['se_topp']:.1f}   "
              f"amplitud {r['amplitud']:.3f} ± {r['se_amp']:.3f} år   "
              f"R2 {r['R2']:.3f}")
        print("   " + "  ".join(f"{k} {v:+.3f}"
                                for k, v in r["koefficienter"].items()))

    # PER KÖN. Skiljer sig riktningen mellan kvinnor och män är den inte en
    # egenskap hos arbetet utan hos vem som utför det.
    for kon in sorted(d["kon"].unique()):
        del_ = d[d["kon"] == kon]
        if len(del_) < 12:
            continue
        r = harmonisk(del_, vikt="antal", kontroller=("intjanandear",))
        print(f"\n--- endast {kon} (n={r['n']})")
        print(f"   topp {r['topp']:.1f}° ± {r['se_topp']:.1f}   "
              f"amplitud {r['amplitud']:.3f} ± {r['se_amp']:.3f} år")

    # RÄCKER FÖRSTA HARMONIKEN? Samma prövning som pappret gör för
    # löneavkastningen: en andra harmonik läggs till och prövas.
    h1 = harmonisk(d, vikt="antal", kontroller=("intjanandear",), harmonik=1)
    h2 = harmonisk(d, vikt="antal", kontroller=("intjanandear",), harmonik=2)
    print(f"\n--- andra harmoniken")
    print(f"   R2 {h1['R2']:.3f} -> {h2['R2']:.3f}   "
          f"cos2 {h2['koefficienter'].get('cos2', 0):+.3f}  "
          f"sin2 {h2['koefficienter'].get('sin2', 0):+.3f}")

    if a.figur:
        os.makedirs(os.path.dirname(a.figur) or ".", exist_ok=True)
        figur(d, harmonisk(d, vikt="antal", kontroller=("intjanandear",)),
              a.figur)
        d.to_csv(os.path.splitext(a.figur)[0] + ".csv", index=False)

    # UTAN ANTAGANDE OM FORM. Sektorerna och rutorna visar strukturen som den
    # ligger; den harmoniska anpassningen förutsätter en cosinuskurva.
    y = per_yrke(d)
    print("\n--- medelålder per riktningssektor (ett yrke per rad)")
    sek = sektorer(y)
    print(sek.to_string(index=False, float_format=lambda v: f"{v:.2f}"))

    print("\n--- rutnät över planet (viktad medelålder / antal yrken)")
    karta, antal, kant, grad = rutnat(y, n=a.rutor)
    n = a.rutor
    print("        " + "".join(f"  x {kant[i]:+.2f}..{kant[i+1]:+.2f}"
                               for i in range(n)))
    for j in range(n - 1, -1, -1):
        rad = f"  y {kant[j]:+.2f}  "
        for i in range(n):
            rad += ("        .      " if np.isnan(karta[j, i])
                    else f"  {karta[j, i]:6.2f}/{antal[j, i]:<3d}  ")
        print(rad)
    if grad:
        print(f"\n   gradient genom {grad['rutor']} rutor: dx {grad['dx']:+.3f}  "
              f"dy {grad['dy']:+.3f}   riktning {grad['riktning']:.1f}°   "
              f"dy/dx {grad['kvot']:+.2f}   lutning {grad['lutning']:.2f} år")
        print("   (rutan är observationen: punkttätheten är ojämn, och en "
              "anpassning på\n    yrken låter de täta områdena bestämma "
              "riktningen)")

    # KOMPONENTERNA VAR FÖR SIG. Att pressa riktningen till ett gradtal är att
    # övertolka -- den vandrar mellan 25 och 55 grader med rutstorlek och
    # viktning. Det som står emot varje prövning är att BÅDA komponenterna är
    # skilda från noll: cos skulle vara noll om åldern följde samma axel som
    # lönepremien, sin om den följde den rena öst-västaxeln.
    rr = harmonisk(d, vikt="antal", kontroller=("intjanandear",))
    kov, k = rr["kov"], rr["koefficienter"]
    print("\n--- komponenterna var för sig")
    for i, namn in ((1, "cos (öst-väst, PC1)"), (2, "sin (nord-syd, PC2)")):
        se = float(np.sqrt(kov[i, i]))
        print(f"   {namn:24} {list(k.values())[i]:+.3f} ± {se:.3f}   "
              f"t = {list(k.values())[i] / se:+.1f}")

    print("\nYtterligheter i materialet:")
    v = d.sort_values("alder")
    for _, rad in pd.concat([v.head(5), v.tail(5)]).iterrows():
        print(f"   {rad['alder']:.2f}  ξ={rad['xi']:6.1f}°  χ={rad['chi']:.2f}  "
              f"{rad['yrke'][:52]} ({rad['kon']})")


if __name__ == "__main__":
    main()
