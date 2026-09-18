"""Yrkeskällan register i scenariobyggaren: samma tabell som körningen
läser, och inget tyst återfall på SNI."""
import os
import sqlite3
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conftest import FakeConfig

KODER = ["11-1011.00", "31-1131.00", "53-7062.04"]


def _byggare(med_tabell=True, kommuner=("2062",)):
    """En scenariobyggare mot en sqlite i minnet. Tabellen har samma
    kolumner som den create_database.py bygger ur yrkesregistret -- utan
    year, vilket var det som fällde den gamla frågan."""
    from core.scenariobuilder import ScenarioBuilder
    conn = sqlite3.connect(":memory:")
    if med_tabell:
        rader = [(k, kod, v) for k in kommuner
                 for kod, v in zip(KODER, (0.2, 0.7, 0.1))]
        pd.DataFrame(rader, columns=["municipal_code", "onet_code", "weight"]).to_sql(
            "occupation_weights_by_municipality", conn, index=False)
    sb = ScenarioBuilder.__new__(ScenarioBuilder)
    sb.conn = conn
    sb.rng = np.random.default_rng(1)
    sb.cfg_reader = FakeConfig({"occupation_source": "register"})
    sb.onet_space_df = pd.DataFrame(
        {"x_occ": [0.3, -0.2, 0.5], "y_occ": [0.1, 0.3, -0.1]},
        index=pd.Index(KODER, name="onet_code"))

    def ingen_sni(*a, **k):
        raise AssertionError("SNI-vägen användes fast källan är register")
    sb._sni_occupational_profile = ingen_sni
    sb.get_onet_codes_with_freq_for_sni = ingen_sni
    return sb


def test_registret_lases_utan_year_kolumn():
    """REGRESSION: frågan krävde year, tabellen saknar den, felet sväljdes och
    startens yrken kom ur SNI medan körningens nya jobb kom ur registret."""
    sb = _byggare()
    prof = sb.municipality_occupational_profile("2062", 2024)
    p = prof.set_index("onet_code")["prob"]
    assert p.to_dict() == pytest.approx({"11-1011.00": 0.2, "31-1131.00": 0.7,
                                         "53-7062.04": 0.1})


def test_saknad_tabell_kastar_med_besked():
    sb = _byggare(med_tabell=False)
    with pytest.raises(ValueError, match="create_database"):
        sb.municipality_occupational_profile("2062", 2024)


def test_saknad_kommun_kastar_med_besked():
    sb = _byggare(kommuner=("2034",))
    with pytest.raises(ValueError, match="saknar kommun 2062"):
        sb.municipality_occupational_profile("2062", 2024)


def test_jobben_dras_ur_branschen_inte_ur_kommunens_profil():
    """Registret beskriver invånarna. Jobben följer arbetsställets bransch
    och storlek (core/bransch.py) -- inte kommunens profil, som gav läkare
    på bilverkstaden, och inte SNI-länken."""
    import geopandas as gpd
    from shapely.geometry import Point
    import core.scenariobuilder as sbmod

    sb = _byggare()
    # Kommunens bilverkstäder (G) har bara mekaniker (723), fast kommunens
    # invånare mest är 31-1131.00.
    pd.DataFrame({"municipal_code": ["2062"], "ssyk_code": ["723"], "sni_code": ["G"],
                  "sex": ["1"], "year": [2024], "employed": [10]}).to_sql(
        "employment_workplace_occupation_sni", sb.conn, index=False)
    # Två O*NET-koder för mekanikern: arbetsstället ska välja EN av dem
    pd.DataFrame({"occupation_code": ["723", "723"],
                  "onet_code": ["53-7062.04", "11-1011.00"],
                  "share": [0.5, 0.5]}).to_sql("ssyk3_onet_crosswalk", sb.conn, index=False)
    sb.onet_space_df = sb.onet_space_df.assign(
        chi=0.3, xi=0.3, r_o=0.27, geom_source="occupation", w_rel=1.0, pi_rel=1.0)
    sb.onet_space_df.reset_index().assign(r_o=0.27).to_sql(
        "onet_occupation_space", sb.conn, index=False)

    class _GW:
        deso_zones = None
    sb.geoworld = _GW()
    orig = sbmod.assign_deso_code
    sbmod.assign_deso_code = lambda df, zones, x_col, y_col: "Z"
    try:
        emp = gpd.GeoDataFrame({
            "employer_id": ["e0"], "municipal_code": "2062", "size": [200],
            "sni_code": "G", "layer": "deso", "zone_code": "A",
            "geometry": [Point(0, 0)]})
        jobs, _ = sb.generate_jobs_from_employers(emp)
    finally:
        sbmod.assign_deso_code = orig
    assert jobs["onet_code"].nunique() == 1, "mekanikern realiserades som flera koder"
    assert jobs["onet_code"].iloc[0] in {"53-7062.04", "11-1011.00"}
    assert (jobs["ssyk_code"] == "723").all()
    assert "31-1131.00" not in set(jobs["onet_code"]), "kommunens profil användes"


def test_varje_arbetsstalle_realiserar_for_sig():
    """Realiseringen gäller ETT arbetsställe. Delas den mellan arbetsställen
    kollapsar befolkningens fördelning till en kod per svenskt yrke."""
    import geopandas as gpd
    from shapely.geometry import Point
    import core.scenariobuilder as sbmod

    sb = _byggare()
    pd.DataFrame({"municipal_code": ["2062"], "ssyk_code": ["723"], "sni_code": ["G"],
                  "sex": ["1"], "year": [2024], "employed": [10]}).to_sql(
        "employment_workplace_occupation_sni", sb.conn, index=False)
    pd.DataFrame({"occupation_code": ["723", "723"],
                  "onet_code": ["53-7062.04", "11-1011.00"],
                  "share": [0.5, 0.5]}).to_sql("ssyk3_onet_crosswalk", sb.conn, index=False)
    sb.onet_space_df = sb.onet_space_df.assign(
        chi=0.3, xi=0.3, r_o=0.27, geom_source="occupation", w_rel=1.0, pi_rel=1.0)
    sb.onet_space_df.reset_index().assign(r_o=0.27).to_sql(
        "onet_occupation_space", sb.conn, index=False)

    class _GW:
        deso_zones = None
    sb.geoworld = _GW()
    orig = sbmod.assign_deso_code
    sbmod.assign_deso_code = lambda df, zones, x_col, y_col: "Z"
    n = 60
    try:
        emp = gpd.GeoDataFrame({
            "employer_id": [f"e{i}" for i in range(n)], "municipal_code": "2062",
            "size": [6] * n, "sni_code": "G", "layer": "deso", "zone_code": "A",
            "geometry": [Point(0, 0)] * n})
        jobs, _ = sb.generate_jobs_from_employers(emp)
    finally:
        sbmod.assign_deso_code = orig
    per = jobs.groupby("employer_id")["onet_code"].nunique()
    assert (per == 1).all()
    andel = jobs.drop_duplicates("employer_id")["onet_code"].value_counts(normalize=True)
    assert set(andel.index) == {"53-7062.04", "11-1011.00"}
    assert andel.min() > 0.25
