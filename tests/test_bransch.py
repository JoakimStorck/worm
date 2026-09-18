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
# Kommunens profil i arbetsställena
# ---------------------------------------------------------------------------

def _profildb(utan=(), extra_crosswalk=()):
    """Kommun 2062, tillverkning (C). Två kluster i uppgiftsrummet: stål
    (811, 812) till höger, bygg (711, 712) till vänster, långt ifrån
    varandra. 111 (chef) är stödyrke. 0002 (okänt) och 011 (militär, ingen
    crosswalk) kan inte placeras och ska falla bort."""
    conn = sqlite3.connect(":memory:")
    if "employment_workplace_occupation_sni" not in utan:
        rader = [("811", 400), ("812", 200), ("711", 200), ("712", 100), ("111", 100),
                 ("0002", 50), ("011", 30)]
        pd.DataFrame([("2062", s_, "C", "1", 2024, n) for s_, n in rader]
                     + [("2062", "811", "C", "1", 2020, 999)],
                     columns=["municipal_code", "ssyk_code", "sni_code", "sex", "year",
                              "employed"]).to_sql(
            "employment_workplace_occupation_sni", conn, index=False)
    lagen = {"811": (0.60, 0.00), "812": (0.62, 0.05), "711": (-0.50, 0.30),
             "712": (-0.52, 0.25), "111": (0.00, 0.00)}
    cw = [(s_, f"O{s_}", 1.0) for s_ in lagen] + list(extra_crosswalk)
    pd.DataFrame(cw, columns=["occupation_code", "onet_code", "share"]).to_sql(
        "ssyk3_onet_crosswalk", conn, index=False)
    onet = [(f"O{s_}", x, y, 0.1) for s_, (x, y) in lagen.items()]
    onet += [(kod, lagen[s_][0], lagen[s_][1], 0.1) for s_, kod, _ in extra_crosswalk]
    pd.DataFrame(onet, columns=["onet_code", "x_occ", "y_occ", "r_o"]).to_sql(
        "onet_occupation_space", conn, index=False)
    return conn


def _profil(**kw):
    from core.bransch import Kommunprofil
    return Kommunprofil(_profildb(**kw))


STAL, BYGG = {"811", "812"}, {"711", "712"}


def test_poolen_ar_kommunens_profil_i_heltal():
    p = _profil()
    assert p.pool("2062", "C", 1000).to_dict() == {
        "811": 400, "812": 200, "711": 200, "712": 100, "111": 100}
    assert int(p.pool("2062", "C", 7).sum()) == 7


def test_poolen_fordelas_exakt_pa_arbetsstallena():
    p = _profil()
    storlekar = [300, 300, 300, 100]
    ut = p.fordela("2062", "C", storlekar, np.random.default_rng(1))
    assert [len(jobb) for _, jobb in ut] == storlekar
    alla = pd.Series([s_ for _, jobb in ut for s_ in jobb]).value_counts().to_dict()
    assert alla == {"811": 400, "812": 200, "711": 200, "712": 100, "111": 100}


def test_arbetsstallena_far_en_riktning_kring_karnan():
    """Stålverket får stålyrkena och byggfirman byggyrkena, inte en blandning
    av båda. Kärnan är aldrig ett stödyrke."""
    p = _profil()
    renhet = []
    for fro in range(10):
        for karna, jobb in p.fordela("2062", "C", [300, 300, 300, 100],
                                     np.random.default_rng(fro)):
            assert karna not in (None, "111")
            profil = [s_ for s_ in jobb if s_ != "111"]
            if len(profil) >= 50:
                a = sum(s_ in STAL for s_ in profil) / len(profil)
                renhet.append(max(a, 1 - a))
    assert np.mean(renhet) > 0.9


def test_stodyrkena_sprids_over_arbetsstallena():
    p = _profil()
    ut = p.fordela("2062", "C", [300, 300, 300, 100], np.random.default_rng(4))
    chefer = [jobb.count("111") for _, jobb in ut[:3]]
    assert all(c >= 1 for c in chefer), chefer


def test_nytt_jobb_dras_kring_karnan():
    p = _profil()
    rng = np.random.default_rng(2)
    nya = pd.Series([p.dra_nytt("2062", "C", "811", rng) for _ in range(3000)])
    assert not (nya.isin(BYGG)).any(), "ett byggjobb postades på stålverket"
    andel = nya.value_counts(normalize=True)
    assert andel["111"] > 0.05
    assert andel["811"] > andel["812"]
    utan = pd.Series([p.dra_nytt("2062", "C", None, rng) for _ in range(3000)])
    assert utan.isin(BYGG).mean() == pytest.approx(0.3, abs=0.04)


def test_ett_svenskt_yrke_ar_en_kod_per_arbetsstalle():
    p = _profil(extra_crosswalk=[("811", "O811b", 1.0)])
    rng = np.random.default_rng(1)
    egna = {}
    assert len({p.onet("811", rng, egna) for _ in range(100)}) == 1
    koder = {p.onet("811", rng, {}) for _ in range(100)}
    assert koder == {"O811", "O811b"}


def test_profil_utan_underlag_kastar():
    from core.bransch import Kommunprofil
    p = _profil()
    with pytest.raises(ValueError, match="kommun 2034"):
        p.pool("2034", "C", 10)
    with pytest.raises(ValueError, match="bransch Q"):
        p.dra_nytt("2062", "Q", None, np.random.default_rng(0))
    with pytest.raises(ValueError, match="employment_workplace_occupation_sni saknas"):
        Kommunprofil(_profildb(utan=("employment_workplace_occupation_sni",)))


def test_scenariobyggarens_jobb_ar_kommunens_pool():
    """Genom scenariobyggaren: branschens jobb över alla arbetsställen är
    kommunens profil exakt, och varje jobb bär sitt arbetsställes kärna."""
    import geopandas as gpd
    from shapely.geometry import Point
    import core.scenariobuilder as sbmod
    from core.scenariobuilder import ScenarioBuilder
    from conftest import FakeConfig

    conn = _profildb()
    sb = ScenarioBuilder.__new__(ScenarioBuilder)
    sb.conn = conn
    sb.rng = np.random.default_rng(1)
    sb.cfg_reader = FakeConfig({})
    geo = pd.read_sql("SELECT * FROM onet_occupation_space", conn).set_index("onet_code")
    sb.onet_space_df = geo.assign(chi=0.3, xi=0.3, geom_source="occupation",
                                  w_rel=1.0, pi_rel=1.0)

    class _GW:
        deso_zones = None
    sb.geoworld = _GW()
    orig = sbmod.assign_deso_code
    sbmod.assign_deso_code = lambda df, zones, x_col, y_col: "Z"
    try:
        emp = gpd.GeoDataFrame({
            "employer_id": ["e0", "e1", "e2"], "municipal_code": "2062",
            "size": [500, 300, 200], "sni_code": "C", "layer": "deso", "zone_code": "A",
            "geometry": [Point(0, 0)] * 3})
        jobs, _ = sb.generate_jobs_from_employers(emp)
    finally:
        sbmod.assign_deso_code = orig
    assert jobs["ssyk_code"].value_counts().to_dict() == {
        "811": 400, "812": 200, "711": 200, "712": 100, "111": 100}
    assert (jobs.groupby("employer_id")["core_ssyk"].nunique() == 1).all()
    assert set(jobs["core_ssyk"]) <= STAL | BYGG
