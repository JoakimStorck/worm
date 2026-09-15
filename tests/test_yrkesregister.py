"""Yrkesregistret och IPF-skattningen per kommun.

Individernas yrken drogs ur kommunens branschmix PÅ ARBETSSTÄLLENA, använd som
fördelning över INVÅNARNA. Yrkesregistrets nattbefolkning finns bara på
länsnivå, så kommunfördelningen skattas med iterativ proportionell anpassning
ur tre marginaler: kommunernas branschmix bland invånarna, rikets
p(yrke|bransch), och länets yrkesfördelning.

Konventionerna för totalrader skiljer sig mellan SCB-uttagen, och det är den
vanligaste tysta felkällan i kedjan:

    Arbetsmarknadsstatus Kommun   har totalrad     -> FILTRERA
    Sysselsatta ... SNI 2007      har totalrad     -> FILTRERA (kollision 0135)
    TAB4347 riket                 saknar totalrad  -> SUMMERA kön
    TAB4441 län                   saknar totalrad  -> SUMMERA ålder och kön,
                                                      men uteslut "00 Riket"
"""
import os
import sqlite3

import numpy as np
import pandas as pd
import pytest

from core.database.load_yrkesregister import (ipf, las_yrke_lan,
                                              las_yrke_naringsgren,
                                              yrkesvikter_per_kommun)

SNI = ["A jordbruk, skogsbruk och fiske", "B+C tillverkning och utvinning",
       "Q vård och omsorg"]
YRK = ["722 Verkstadsmekaniker", "532 Undersköterskor", "611 Odlare"]


def _riksfil(path, varden=None, kodning="iso-8859-1"):
    """Kommaseparerad med citattecken, rubrik på rad ett, kön utan totalrad."""
    rader = []
    for y in YRK:
        for s in SNI:
            n = (varden or {}).get((y[:3], s[0]), 100)
            for kon in ("män", "kvinnor"):
                rader.append({"Yrke (SSYK 2012)": y, "näringsgren SNI 2007": s,
                              "storleksklass": "1-4 anställda", "kön": kon,
                              "år": "2023", "Anställda, antal": n // 2})
    pd.DataFrame(rader).to_csv(path, index=False, quoting=1, encoding=kodning)


def _lansfil(path, varden=None, kodning="iso-8859-1"):
    rader = []
    for reg in ("00 Riket", "20 Dalarnas län"):
        for y in YRK:
            n = (varden or {}).get(y[:3], 300)
            for alder in ("16-24 år", "25-29 år"):
                for kon in ("män", "kvinnor"):
                    rader.append({
                        "region": reg, "Yrke (SSYK 2012)": y, "ålder": alder,
                        "kön": kon, "år": "2023",
                        "Anställda med bostad i regionen (nattbef), antal": n // 4})
    pd.DataFrame(rader).to_csv(path, index=False, quoting=1, encoding=kodning)


# ---------------------------------------------------------------------------
# Läsarna
# ---------------------------------------------------------------------------
def test_riket_summerar_konen(tmp_path):
    """Uttaget saknar totalrad: män plus kvinnor ÄR totalen. Filtreras det i
    stället halveras talen."""
    p = str(tmp_path / "riket.csv")
    _riksfil(p, {("722", "B"): 1000})
    d = las_yrke_naringsgren(p)
    rad = d[(d.ssyk_code == "722") & (d.sni_code == "B+C")]
    assert int(rad.employed.iloc[0]) == 1000


def test_lanet_utesluter_riket(tmp_path):
    """00 Riket ligger i samma kolumn som länen. Summeras den med dubbleras
    hela landet ovanpå."""
    p = str(tmp_path / "lan.csv")
    _lansfil(p)
    d = las_yrke_lan(p)
    assert "00" not in set(d.county_code)
    assert set(d.county_code) == {"20"}


def test_lanet_summerar_alder_och_kon(tmp_path):
    p = str(tmp_path / "lan.csv")
    _lansfil(p, {"532": 800})
    d = las_yrke_lan(p)
    assert int(d[d.ssyk_code == "532"].employed.iloc[0]) == 800


def test_sni_koden_behaller_plustecken(tmp_path):
    """B+C är en egen näringsgren och får inte kapas till B."""
    p = str(tmp_path / "riket.csv")
    _riksfil(p)
    d = las_yrke_naringsgren(p)
    assert "B+C" in set(d.sni_code)


@pytest.mark.parametrize("kodning", ["iso-8859-1", "cp1252", "utf-8"])
def test_kodningar(tmp_path, kodning):
    p = str(tmp_path / f"riket_{kodning}.csv")
    _riksfil(p, kodning=kodning)
    assert len(las_yrke_naringsgren(p)) == 9


# ---------------------------------------------------------------------------
# IPF
# ---------------------------------------------------------------------------
def test_ipf_traffar_bada_marginalerna():
    start = np.array([[1.0, 2.0, 3.0], [4.0, 1.0, 1.0]])
    r = np.array([100.0, 200.0])
    k = np.array([120.0, 90.0, 90.0])
    A = ipf(start, r, k)
    assert A.sum(axis=1) == pytest.approx(r)
    assert A.sum(axis=0) == pytest.approx(k)


def test_ipf_bevarar_monstret():
    """Det IPF gör är att flytta massa, inte att skapa struktur: ett redan
    konsistent startläge ska lämnas orört."""
    start = np.array([[10.0, 20.0], [30.0, 40.0]])
    A = ipf(start, start.sum(axis=1), start.sum(axis=0))
    assert A == pytest.approx(start)


def test_ipf_nollor_forblir_nollor():
    """En kommun vars branschmix saknar en bransch ska inte få yrken som bara
    förekommer där."""
    start = np.array([[1.0, 0.0], [1.0, 1.0]])
    A = ipf(start, np.array([50.0, 150.0]), np.array([100.0, 100.0]))
    assert A[0, 1] == 0.0


def test_ipf_kastar_pa_olika_marginalsummor():
    """Finns ingen lösning ska det sägas, inte returneras något som ser
    rimligt ut."""
    with pytest.raises(ValueError, match="summerar olika"):
        ipf(np.ones((2, 2)), np.array([10.0, 10.0]), np.array([10.0, 30.0]))


def test_ipf_kastar_pa_olosbar_kolumn():
    with pytest.raises(ValueError, match="olösbar"):
        ipf(np.array([[1.0, 0.0], [1.0, 0.0]]),
            np.array([50.0, 50.0]), np.array([50.0, 50.0]))


def test_ipf_konvergerar_snabbt():
    rng = np.random.default_rng(0)
    start = rng.random((40, 120)) + 0.01
    r = rng.random(40) * 1000
    k = rng.random(120)
    k = k / k.sum() * r.sum()
    A = ipf(start, r, k, max_iter=50)
    assert np.abs(A.sum(axis=1) - r).max() < 1e-6


# ---------------------------------------------------------------------------
# Hela kedjan
# ---------------------------------------------------------------------------
def _db(tmp_path, kom_profil):
    p_r, p_l = str(tmp_path / "r.csv"), str(tmp_path / "l.csv")
    _riksfil(p_r, {("722", "B"): 900, ("532", "Q"): 900, ("611", "A"): 900,
                   ("722", "A"): 50, ("722", "Q"): 50, ("532", "A"): 50,
                   ("532", "B"): 50, ("611", "B"): 50, ("611", "Q"): 50})
    _lansfil(p_l, {"722": 400, "532": 400, "611": 400})
    db = str(tmp_path / "t.sqlite3")
    conn = sqlite3.connect(db)
    las_yrke_naringsgren(p_r).to_sql("occupation_by_industry", conn, index=False)
    las_yrke_lan(p_l).to_sql("occupation_by_county", conn, index=False)
    rader = []
    for kom, andelar in kom_profil.items():
        for sni, n in andelar.items():
            rader.append({"deso_code": f"{kom}A0001", "year": 2023,
                          "sni_code": sni, "employed": n})
    pd.DataFrame(rader).to_sql("employment_deso_sni", conn, index=False)
    return conn


def test_kommunerna_skiljer_sig_efter_sin_branschmix(tmp_path):
    """Hela poängen: en verkstadstung kommun ska få fler verkstadsmekaniker
    än en vårdtung, trots att båda rakas mot samma länsprofil."""
    conn = _db(tmp_path, {
        "2062": {"A": 100, "B+C": 800, "Q": 100},     # verkstad
        "2034": {"A": 100, "B+C": 100, "Q": 800},     # vård
    })
    v = yrkesvikter_per_kommun(conn, "20", ["2062", "2034"])
    conn.close()
    p = v.pivot(index="municipal_code", columns="occupation_code",
                values="weight").fillna(0.0)
    assert p.loc["2062", "722"] > p.loc["2034", "722"]
    assert p.loc["2034", "532"] > p.loc["2062", "532"]


def test_vikterna_summerar_till_ett_per_kommun(tmp_path):
    conn = _db(tmp_path, {"2062": {"A": 100, "B+C": 800, "Q": 100},
                          "2034": {"A": 100, "B+C": 100, "Q": 800}})
    v = yrkesvikter_per_kommun(conn, "20", ["2062", "2034"])
    conn.close()
    summor = v.groupby("municipal_code").weight.sum()
    assert summor.to_numpy() == pytest.approx(1.0)


def test_lansprofilen_ar_marginal(tmp_path):
    """Summerat över kommunerna ska yrkesfördelningen bli länets, viktad med
    kommunernas storlek. Det är rakningen som garanterar det."""
    conn = _db(tmp_path, {"2062": {"A": 100, "B+C": 800, "Q": 100},
                          "2034": {"A": 100, "B+C": 100, "Q": 800}})
    v = yrkesvikter_per_kommun(conn, "20", ["2062", "2034"])
    conn.close()
    tot = {"2062": 1000.0, "2034": 1000.0}
    v["n"] = v.weight * v.municipal_code.map(tot)
    andel = v.groupby("occupation_code")["n"].sum()
    andel = andel / andel.sum()
    # Länsprofilen är jämn i provdata: tre yrken, lika stora.
    assert andel.to_numpy() == pytest.approx([1 / 3] * 3, abs=0.01)


def test_ssyk_koderna_skrivs_inte_till_onet_tabellen():
    """occupation_weights_by_municipality läses som O*NET av
    municipality_occupational_profile. SSYK3-koder där skulle ge noll träffar
    mot onet_occupation_space -- eller värre, träffar på måfå."""
    import inspect

    from core.database import load_yrkesregister

    kalla = inspect.getsource(load_yrkesregister)
    assert 'to_sql("occupation_weights_ssyk_by_municipality"' in kalla
    assert 'to_sql("occupation_weights_by_municipality"' not in kalla


def test_okand_bransch_far_rikets_yrkesfordelning(tmp_path):
    """Kommuntabellen har koden US, "uppgift saknas", som rikstabellen saknar:
    93 677 personer i riket. Utesluts de minskar varje kommuns radsumma, och
    eftersom andelen okänd bransch varierar mellan kommuner blir det en
    systematisk snedvridning och inte en proportionell förlust."""
    conn = _db(tmp_path, {
        "2062": {"A": 100, "B+C": 800, "Q": 100},           # ingen okänd
        "2034": {"A": 100, "B+C": 100, "Q": 300, "US": 500},  # halva okänd
    })
    v = yrkesvikter_per_kommun(conn, "20", ["2062", "2034"])
    conn.close()
    # Båda kommunerna ska ha full vikt trots att den ena har US.
    summor = v.groupby("municipal_code").weight.sum()
    assert summor.to_numpy() == pytest.approx(1.0)
    p = v.pivot(index="municipal_code", columns="occupation_code",
                values="weight").fillna(0.0)
    # Kommunen med mycket okänd bransch dras mot en jämnare fördelning,
    # eftersom rikets marginal är jämnare än en enskild bransch profil.
    spridning = p.max(axis=1) - p.min(axis=1)
    assert spridning["2034"] < spridning["2062"]


def test_radsumman_raknar_alla_branscher(tmp_path):
    """Radmålet i IPF ska vara kommunens hela sysselsättning, inte bara den
    del vars bransch matchar rikstabellen."""
    conn = _db(tmp_path, {"2062": {"A": 100, "B+C": 800, "Q": 100},
                          "2034": {"B+C": 100, "US": 900}})
    import inspect

    from core.database import load_yrkesregister
    kalla = inspect.getsource(load_yrkesregister.yrkesvikter_per_kommun)
    assert "rad_mal = kom_sni.sum(axis=1)" in kalla
    v = yrkesvikter_per_kommun(conn, "20", ["2062", "2034"])
    conn.close()
    assert set(v.municipal_code) == {"2062", "2034"}
