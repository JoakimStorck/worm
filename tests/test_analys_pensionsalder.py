"""Medelpensioneringsålder mot riktning i uppgiftsrummet.

Pensionsmyndighetens yrkesuppdelade underlag är cp1252 med semikolon och
svenskt decimalkomma, och yrkesnamnen är SSYK 2012-benämningar utan kod.
Kedjan namn -> SSYK3 -> O*NET -> position prövas här på syntetiska data; de
riktiga talen kommer ur scripts/analys_pensionsalder.py.
"""
import numpy as np
import pandas as pd
import pytest

from scripts.analys_pensionsalder import (harmonisk, las_pensionsalder,
                                          las_ssyk_namn, normalisera)


CSV = (
    '"Yrke";"Kön";"AntalNyaPensionärer";"Intjänandeår";"Medelpensioneringsålder"\n'
    '"Undersköterskor";"Kvinnor";4330;43,1;65\n'
    '"Kontorsassistenter och sekreterare";"Kvinnor";3480;44,7;65,3\n'
    '"Skötare, vårdare och personliga assistenter m.fl.";"Kvinnor";2950;42,4;65,2\n'
    '"Universitets- och högskollärare";"Män";640;41,0;66,99\n'
)

YRKESFIL = (
    '"region";"yrke";"2023"\n'
    '"20 Dalarnas län";"532 Undersköterskor";1200\n'
    '"20 Dalarnas län";"411 Kontorsassistenter och sekreterare";800\n'
    '"20 Dalarnas län";"231 Universitets- och högskollärare";150\n'
    # Registret skriver benämningen UTAN "m.fl." där rapporten har det.
    '"20 Dalarnas län";"534 Skötare, vårdare och personliga assistenter";400\n'
)


def _skriv(tmp_path, namn, text, kodning="cp1252"):
    p = tmp_path / namn
    p.write_bytes(text.encode(kodning))
    return str(p)


# ----------------------------------------------------------------------
# Läsningen
# ----------------------------------------------------------------------

def test_decimalkomma_och_cp1252(tmp_path):
    """Filen är cp1252 med semikolon och svenskt decimalkomma. Läses den som
    utf-8 kastar den, och läses "65,3" utan ersättning blir åldern NaN."""
    d = las_pensionsalder(_skriv(tmp_path, "p.csv", CSV))
    assert len(d) == 4
    assert d["alder"].max() == pytest.approx(66.99)
    assert d[d.yrke.str.startswith("Kontors")]["alder"].iloc[0] == pytest.approx(65.3)
    assert d["intjanandear"].min() == pytest.approx(41.0)


def test_koden_plockas_ur_yrkesregistrets_benamning(tmp_path):
    n = las_ssyk_namn(_skriv(tmp_path, "y.csv", YRKESFIL))
    assert set(n["ssyk3"]) == {"532", "411", "231", "534"}
    assert n[n.ssyk3 == "231"]["namn"].iloc[0] == "Universitets- och högskollärare"


def test_namnen_matchar_over_skrivsatt():
    """SCB och Pensionsmyndigheten använder samma SSYK-benämningar men inte
    alltid samma skrivsätt: "m.fl." hänger med ibland och inte alltid."""
    assert normalisera("Skötare, vårdare och personliga assistenter m.fl.") == \
        normalisera("Skötare, vårdare och personliga assistenter")
    assert normalisera("Fysiker och kemister m.fl.") == \
        normalisera("Fysiker  och kemister")


def test_matchningen_gar_igenom(tmp_path):
    """Hela kedjan från rapportens namn till SSYK3, inklusive raden där
    rapporten skriver "m.fl." och registret inte gör det."""
    pens = las_pensionsalder(_skriv(tmp_path, "p.csv", CSV))
    namn = las_ssyk_namn(_skriv(tmp_path, "y.csv", YRKESFIL))
    d = pens.merge(namn[["ssyk3", "nyckel"]], on="nyckel", how="left")
    assert d["ssyk3"].notna().sum() == 4


# ----------------------------------------------------------------------
# Anpassningen
# ----------------------------------------------------------------------

def _syntetisk(topp_grader=90.0, amplitud=1.2, brus=0.0, n=60, seed=1):
    rng = np.random.default_rng(seed)
    xi = np.linspace(0, 360, n, endpoint=False)
    r = np.radians(xi - topp_grader)
    return pd.DataFrame({
        "xi": xi,
        "alder": 65.0 + amplitud * np.cos(r) + rng.normal(0, brus, n),
        "antal": np.full(n, 100.0),
        "intjanandear": rng.normal(43, 1, n),
        "chi": rng.uniform(0.2, 0.6, n)})


def test_hittar_toppriktningen():
    r = harmonisk(_syntetisk(topp_grader=90.0, amplitud=1.2), vikt="antal")
    assert r["topp"] == pytest.approx(90.0, abs=1.0)
    assert r["amplitud"] == pytest.approx(1.2, abs=0.05)


def test_riktningen_ar_cirkular():
    """En topp strax under 360 grader ska inte rapporteras som negativ."""
    r = harmonisk(_syntetisk(topp_grader=350.0), vikt="antal")
    assert r["topp"] == pytest.approx(350.0, abs=1.0)


def test_bruset_vidgar_konfidensintervallet():
    tyst = harmonisk(_syntetisk(brus=0.05, seed=2), vikt="antal")
    stokigt = harmonisk(_syntetisk(brus=1.5, seed=2), vikt="antal")
    assert stokigt["se_topp"] > tyst["se_topp"]


def test_kontrollen_tar_bort_det_den_ska():
    """En ålder som helt bestäms av intjänandeåren och inte av riktningen ska
    ge en amplitud nära noll när kontrollen är med."""
    d = _syntetisk(amplitud=0.0, brus=0.0, n=80)
    d["intjanandear"] = np.linspace(38, 46, len(d))
    d["alder"] = 60.0 + 0.2 * d["intjanandear"]
    utan = harmonisk(d, vikt="antal")
    med = harmonisk(d, vikt="antal", kontroller=("intjanandear",))
    assert med["amplitud"] < 0.05
    assert med["R2"] > utan["R2"]


def test_vikterna_anvands():
    """En yrkesgrupp med tio gånger fler personer ska väga tyngre."""
    d = _syntetisk(topp_grader=90.0, amplitud=1.0, n=40)
    d.loc[d.index[:5], "alder"] += 5.0
    lika = harmonisk(d, vikt=None)
    d["antal"] = 100.0
    d.loc[d.index[:5], "antal"] = 1.0
    viktad = harmonisk(d, vikt="antal")
    assert abs(viktad["topp"] - 90.0) < abs(lika["topp"] - 90.0)


# ----------------------------------------------------------------------
# Klustring och figur
# ----------------------------------------------------------------------

def _med_konsrader(d):
    """Varje yrke två gånger, en rad per kön, som i underlaget."""
    d = d.copy()
    d["ssyk3"] = [f"{100 + i}" for i in range(len(d))]
    d["yrke"] = [f"y{i}" for i in range(len(d))]
    d["kon"] = "Kvinnor"
    tva = d.assign(kon="Män", alder=d["alder"] + 0.05)
    return pd.concat([d, tva], ignore_index=True)


def test_klustring_vidgar_felet():
    """De två könsraderna per yrke är inte oberoende observationer. Behandlas
    de som det underskattas standardfelen."""
    d = _med_konsrader(_syntetisk(topp_grader=40.0, amplitud=0.3, brus=0.3,
                                  n=120, seed=5))
    klustrat = harmonisk(d, vikt="antal", kluster="ssyk3")
    naivt = harmonisk(d, vikt="antal", kluster=None)
    assert klustrat["se_topp"] > naivt["se_topp"]
    assert klustrat["kluster"] == 120


def test_klustring_andrar_inte_punktskattningen():
    """Sandwichen rör kovariansen, inte koefficienterna."""
    d = _med_konsrader(_syntetisk(topp_grader=40.0, n=60, seed=6))
    a = harmonisk(d, vikt="antal", kluster="ssyk3")
    b = harmonisk(d, vikt="antal", kluster=None)
    assert a["topp"] == pytest.approx(b["topp"], abs=1e-9)
    assert a["amplitud"] == pytest.approx(b["amplitud"], abs=1e-9)


def test_andra_harmoniken_far_plats():
    d = _med_konsrader(_syntetisk(n=80, seed=7))
    r = harmonisk(d, vikt="antal", harmonik=2)
    assert "cos2" in r["koefficienter"] and "sin2" in r["koefficienter"]
    assert r["R2"] >= harmonisk(d, vikt="antal", harmonik=1)["R2"] - 1e-9


def test_figuren_ritas(tmp_path):
    from scripts.analys_pensionsalder import figur
    d = _med_konsrader(_syntetisk(topp_grader=38.0, n=40, seed=8))
    r = harmonisk(d, vikt="antal")
    p = tmp_path / "f.pdf"
    figur(d, r, str(p))
    assert p.exists() and p.stat().st_size > 1000


# ----------------------------------------------------------------------
# Sektorer och rutnät
# ----------------------------------------------------------------------

def test_yrket_raknas_en_gang():
    """Rader är inte observationer när samma yrke förekommer två gånger. Ett
    yrke med båda könen ska inte se ut som två belägg för samma position."""
    from scripts.analys_pensionsalder import per_yrke
    d = _med_konsrader(_syntetisk(n=30, seed=11))
    d["x"] = np.cos(np.radians(d["xi"]))
    d["y"] = np.sin(np.radians(d["xi"]))
    y = per_yrke(d)
    assert len(y) == 30
    # Åldern vägs ihop med antalet, inte med ett rakt medelvärde.
    rad = d[d["yrke"] == "y0"]
    vantat = np.average(rad["alder"], weights=rad["antal"])
    assert y[y.yrke == "y0"]["alder"].iloc[0] == pytest.approx(vantat)


def test_rutnatet_hittar_gradienten():
    """Rutnätet antar ingen cirkulär form, till skillnad från den harmoniska
    anpassningen."""
    from scripts.analys_pensionsalder import rutnat
    rng = np.random.default_rng(12)
    n = 400
    x, yy = rng.uniform(-0.6, 0.6, n), rng.uniform(-0.6, 0.6, n)
    y = pd.DataFrame({"x": x, "y": yy, "xi": np.degrees(np.arctan2(yy, x)) % 360,
                      "chi": np.hypot(x, yy), "antal": 100.0,
                      "alder": 65 + 0.7 * x + 0.35 * yy})
    _, _, _, grad = rutnat(y, n=5)
    assert grad["riktning"] == pytest.approx(26.6, abs=3.0)
    assert grad["kvot"] == pytest.approx(0.5, abs=0.1)


def test_punkttatheten_paverkar_inte_gradienten():
    """Det rutnätet FAKTISKT gör: ger varje bebodd region samma vikt.

    Samma data, men en region har tio gånger fler yrken. Gradienten ska vara
    oförändrad. Punkttätheten i det verkliga materialet är lika ojämn -- den
    östra halvan har tre gånger fler yrken än den nordvästra -- och en
    anpassning på yrken låter därför de täta områdena bestämma riktningen.

    Vad rutnätet INTE skyddar mot: en region som avviker i nivå drar lika
    mycket som vilken annan region som helst, eftersom den nu väger lika. Med
    tolv bebodda rutor är varje ruta en åttondel av vikten.
    """
    from scripts.analys_pensionsalder import rutnat
    rng = np.random.default_rng(13)

    def ram(x, y):
        d = pd.DataFrame({"x": x, "y": y})
        d["alder"] = 65 + 0.7 * d["x"] + 0.35 * d["y"]
        d["antal"] = 100.0
        d["xi"] = np.degrees(np.arctan2(d["y"], d["x"])) % 360
        d["chi"] = np.hypot(d["x"], d["y"])
        return d

    glest = ram(rng.uniform(-0.6, 0.6, 120), rng.uniform(-0.6, 0.6, 120))
    tat = pd.concat([glest,
                     ram(rng.normal(0.45, 0.05, 600),
                         rng.normal(-0.45, 0.05, 600))], ignore_index=True)
    g1 = rutnat(glest, n=5)[3]
    g2 = rutnat(tat, n=5)[3]
    assert g2["kvot"] == pytest.approx(g1["kvot"], abs=0.08)
    assert g2["riktning"] == pytest.approx(g1["riktning"], abs=5.0)


def test_sektorerna_tacker_varvet():
    from scripts.analys_pensionsalder import sektorer
    y = pd.DataFrame({"xi": np.linspace(0, 359, 64), "antal": 1.0,
                      "alder": 65.0})
    s = sektorer(y, n=8)
    assert len(s) == 8
    assert int(s["yrken"].sum()) == 64
