"""Arbetsställenas bransch och storlek (core/bransch.py): jobben följer
kommunens branschfördelning, storleken dras givet branschen."""
import sqlite3

import numpy as np
import pandas as pd
import pytest

from core.bransch import Branschstruktur, STORLEKSKLASSER, storleksklass

KLASSER = [k for k, _, _ in STORLEKSKLASSER]


def _db(riket=None, deso=None, utan=()):
    """sqlite i minnet med samma kolumner som create_database.py bygger.

    Riket: Q har alla anställda på stora arbetsställen, G alla på de minsta,
    så att storleken givet branschen syns direkt. Kommunen 2062 har tre
    gånger så många jobb i Q som i G det senaste året, plus en post med okänd
    verksamhet (00). Ett äldre år med omvänd fördelning ska inte läsas."""
    conn = sqlite3.connect(":memory:")
    if "occupation_by_industry" not in utan:
        rader = riket or ([("221", "Q", "100+ anställda", 900)]
                          + [("522", "G", k, 300 if k == "1-4 anställda" else 0)
                             for k in KLASSER])
        pd.DataFrame(rader, columns=["ssyk_code", "sni_code", "size_class", "employed"]).to_sql(
            "occupation_by_industry", conn, index=False)
    if "employment_workplace_occupation_sni" not in utan:
        rader = deso or [("2062", "Q", "1", 2024, 600), ("2062", "Q", "2", 2024, 300),
                         ("2062", "G", "2", 2024, 300), ("2062", "00", "1", 2024, 500),
                         ("2062", "Q", "1", 2023, 100), ("2062", "G", "1", 2023, 900),
                         ("2034", "G", "1", 2024, 50)]
        pd.DataFrame([(k, "522", s, kon, ar, n) for k, s, kon, ar, n in rader],
                     columns=["municipal_code", "ssyk_code", "sni_code", "sex", "year",
                              "employed"]).to_sql(
            "employment_workplace_occupation_sni", conn, index=False)
    return conn


def test_storleksklasserna_har_registrets_granser():
    assert [storleksklass(n) for n in (1, 4, 5, 9, 10, 49, 50, 99, 100, 5000)] == [
        "1-4 anställda", "1-4 anställda", "5-9 anställda", "5-9 anställda",
        "10-19 anställda", "20-49 anställda", "50-99 anställda", "50-99 anställda",
        "100+ anställda", "100+ anställda"]


def test_jobben_foljer_kommunens_branscher_senaste_aret_och_okant_raknas_bort():
    s = Branschstruktur(_db(), max_storlek=1000)
    andel = s.branschandelar("2062")
    assert andel.to_dict() == pytest.approx({"Q": 0.75, "G": 0.25})
    jobb = s.jobb_per_bransch("2062", 1001)
    assert int(jobb.sum()) == 1001
    assert jobb.to_dict() == {"Q": 751, "G": 250}


def test_arbetsstallena_fyller_branschens_mal_exakt():
    s = Branschstruktur(_db(), max_storlek=400)
    st = s.dra_arbetsstallen("2062", 5000, np.random.default_rng(3))
    df = pd.DataFrame(st, columns=["sni", "storlek"])
    assert df.groupby("sni")["storlek"].sum().to_dict() == {"Q": 3750, "G": 1250}
    assert (df["storlek"] >= 1).all() and (df["storlek"] <= 400).all()


def test_storleken_dras_givet_branschen():
    """Vård på stora arbetsställen, handel på små -- inte samma klass för
    alla branscher, vilket var det gamla felet."""
    s = Branschstruktur(_db(), max_storlek=400)
    df = pd.DataFrame(s.dra_arbetsstallen("2062", 20000, np.random.default_rng(5)),
                      columns=["sni", "storlek"])
    g, q = df[df.sni == "G"].storlek, df[df.sni == "Q"].storlek
    assert g.max() <= 4
    # bara det sista, kapade arbetsstället i vården får vara mindre än 100
    assert (q < 100).sum() <= 1 and q.max() <= 400


def test_andelen_jobb_per_klass_foljer_riket():
    """Klassen dras med P(klass | bransch) / medelstorlek, så att JOBBEN och
    inte arbetsställena fördelas som i registret."""
    riket = [("111", "C", k, e) for k, e in zip(KLASSER, (100, 100, 100, 100, 100, 500))]
    s = Branschstruktur(_db(riket=riket, deso=[("2062", "C", "1", 2024, 1)]), max_storlek=1000)
    df = pd.DataFrame(s.dra_arbetsstallen("2062", 400000, np.random.default_rng(7)),
                      columns=["sni", "storlek"])
    andel = df.groupby(df.storlek.map(storleksklass)).storlek.sum() / df.storlek.sum()
    assert andel.reindex(KLASSER).to_numpy() == pytest.approx(
        [0.1, 0.1, 0.1, 0.1, 0.1, 0.5], abs=0.02)


@pytest.mark.parametrize("tabell", ["occupation_by_industry",
                                    "employment_workplace_occupation_sni"])
def test_saknad_tabell_kastar_med_besked(tabell):
    with pytest.raises(ValueError, match="create_database"):
        Branschstruktur(_db(utan=(tabell,)), max_storlek=1000)


def test_saknad_kommun_och_okand_bransch_kastar():
    s = Branschstruktur(_db(), max_storlek=1000)
    with pytest.raises(ValueError, match="saknar kommun 2039"):
        s.branschandelar("2039")
    s2 = Branschstruktur(_db(deso=[("2062", "X", "1", 2024, 10)]), max_storlek=1000)
    with pytest.raises(ValueError, match="X"):
        s2.branschandelar("2062")


def test_maxstorleken_maste_anges():
    with pytest.raises(ValueError, match="workplace_max_size"):
        Branschstruktur(_db(), max_storlek=None)


def test_de_gamla_storleksklasserna_avvisas():
    from core.scenariobuilder import ScenarioBuilder
    sb = ScenarioBuilder.__new__(ScenarioBuilder)
    with pytest.raises(ValueError, match="workplace_max_size"):
        sb.generate_employers_with_target_jobs(
            2024, "2062", 100, {"employer_size_distribution": {}, "allocation_order": []})


# ---------------------------------------------------------------------------
# Jobbets yrke givet bransch och storlek
# ---------------------------------------------------------------------------

def _yrkesdb(utan=()):
    """Vården (Q) på små arbetsställen: bara undersköterskor (532). På stora:
    hälften undersköterskor, hälften läkare (221). SSYK 000 (okänt) saknar
    O*NET-koppling, och 532 delas på en kod med geometri och en utan."""
    conn = sqlite3.connect(":memory:")
    if "occupation_by_industry" not in utan:
        pd.DataFrame([("532", "Q", "1-4 anställda", 40), ("532", "Q", "100+ anställda", 500),
                      ("221", "Q", "100+ anställda", 500), ("000", "Q", "100+ anställda", 999)],
                     columns=["ssyk_code", "sni_code", "size_class", "employed"]).to_sql(
            "occupation_by_industry", conn, index=False)
    pd.DataFrame([("532", "USK", 0.5), ("532", "UTAN_GEOMETRI", 0.5), ("221", "LAK", 1.0)],
                 columns=["occupation_code", "onet_code", "share"]).to_sql(
        "ssyk3_onet_crosswalk", conn, index=False)
    pd.DataFrame({"onet_code": ["USK", "LAK"], "x_occ": [0.1, 0.2]}).to_sql(
        "onet_occupation_space", conn, index=False)
    return conn


def test_yrket_foljer_bransch_och_storlek():
    from core.bransch import YrkeGivetBransch
    y = YrkeGivetBransch(_yrkesdb())
    koder, p = y.fordelning("Q", 3)
    assert dict(zip(koder, p)) == pytest.approx({"USK": 1.0})
    koder, p = y.fordelning("Q", 300)
    # 532 bär 500 * 0.5 till USK (halvan utan geometri faller), 221 bär 500
    assert dict(zip(koder, p)) == pytest.approx({"USK": 1 / 3, "LAK": 2 / 3})


def test_yrke_utan_underlag_kastar():
    from core.bransch import YrkeGivetBransch
    y = YrkeGivetBransch(_yrkesdb())
    with pytest.raises(ValueError, match="bransch G"):
        y.fordelning("G", 3)
    with pytest.raises(ValueError, match="20-49"):
        y.fordelning("Q", 30)
    with pytest.raises(ValueError, match="occupation_by_industry saknas"):
        YrkeGivetBransch(_yrkesdb(utan=("occupation_by_industry",)))


def _tvakoder_db():
    """Mekaniker (723) på bilverkstaden (G) delas lika på två O*NET-koder,
    båda med geometri. Chefer (111) har en kod."""
    conn = sqlite3.connect(":memory:")
    pd.DataFrame([("723", "G", "10-19 anställda", 80), ("111", "G", "10-19 anställda", 20)],
                 columns=["ssyk_code", "sni_code", "size_class", "employed"]).to_sql(
        "occupation_by_industry", conn, index=False)
    pd.DataFrame([("723", "MEK_A", 0.5), ("723", "MEK_B", 0.5), ("111", "CHEF", 1.0)],
                 columns=["occupation_code", "onet_code", "share"]).to_sql(
        "ssyk3_onet_crosswalk", conn, index=False)
    pd.DataFrame({"onet_code": ["MEK_A", "MEK_B", "CHEF"]}).to_sql(
        "onet_occupation_space", conn, index=False)
    return conn


def test_arbetsstallet_realiserar_ett_svenskt_yrke_som_en_kod():
    """Bilverkstadens mekaniker är samma yrke, inte en spridning över
    crosswalkens koder."""
    from core.bransch import YrkeGivetBransch
    y = YrkeGivetBransch(_tvakoder_db())
    rng = np.random.default_rng(1)
    egna = {}
    jobb = [y.dra("G", 15, rng, egna) for _ in range(200)]
    mek = {kod for s_, kod in jobb if s_ == "723"}
    assert len(mek) == 1
    assert {kod for s_, kod in jobb if s_ == "111"} == {"CHEF"}
    assert egna == {"723": mek.pop(), "111": "CHEF"}


def test_over_manga_arbetsstallen_ar_fordelningen_oforandrad():
    """Realiseringen per arbetsställe får inte flytta befolkningens
    fördelning: över många arbetsställen ska den vara produkten av leden."""
    from core.bransch import YrkeGivetBransch
    y = YrkeGivetBransch(_tvakoder_db())
    rng = np.random.default_rng(2)
    koder = []
    for _ in range(3000):
        egna = {}
        koder += [kod for _, kod in (y.dra("G", 15, rng, egna) for _ in range(5))]
    andel = pd.Series(koder).value_counts(normalize=True)
    assert andel.to_dict() == pytest.approx({"MEK_A": 0.4, "MEK_B": 0.4, "CHEF": 0.2}, abs=0.02)
    k, p = y.fordelning("G", 15)
    assert dict(zip(k, p)) == pytest.approx({"MEK_A": 0.4, "MEK_B": 0.4, "CHEF": 0.2})
