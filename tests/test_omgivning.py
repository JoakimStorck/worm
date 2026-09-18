"""Omgivningens underlag (core/omgivning.py, docs/omgivning.md steg O1)."""
import sqlite3

import numpy as np
import pandas as pd
import pytest

from core.omgivning import Omgivning

REGION = ["2062", "2034"]          # Mora och Orsa; Falun (2080) och Rättvik (2031) utanför


def _db(utan=()):
    conn = sqlite3.connect(":memory:")
    if "commuting" not in utan:
        rader = [("2062", "2062", 100), ("2062", "2034", 10), ("2034", "2062", 20),
                 ("2034", "2034", 50), ("2062", "2080", 30), ("2062", "2031", 10),
                 ("2031", "2062", 40), ("2080", "2034", 5), ("2080", "2080", 999)]
        pd.DataFrame([(b, a, 2023, n) for b, a, n in rader]
                     + [("2062", "2080", 2020, 777)],
                     columns=["home_municipality", "work_municipality", "year",
                              "employed"]).to_sql("commuting", conn, index=False)
    if "deso" not in utan:
        def ruta(x0, y0):
            return f"POLYGON (({x0} {y0}, {x0 + 1000} {y0}, {x0 + 1000} {y0 + 1000}, " \
                   f"{x0} {y0 + 1000}, {x0} {y0}))"
        pd.DataFrame([("2080A0010", 300, ruta(0, 0)), ("2080A0020", 100, ruta(10000, 0)),
                      ("2080A0030", 0, ruta(50000, 0)), ("2031A0010", 50, ruta(0, 20000))],
                     columns=["deso_code", "population", "geom_wkt"]).to_sql(
            "deso", conn, index=False)
    return conn


def test_matrisen_delas_i_inom_ut_och_in():
    o = Omgivning(_db(), REGION)
    assert o.ar == 2023, "äldre år ska inte läsas"
    assert int(o.inom.n.sum()) == 180
    assert o.utpendling.set_index("arb").n.to_dict() == {"2080": 30, "2031": 10}
    assert set(zip(o.inpendling.bo, o.inpendling.arb)) == {("2031", "2062"), ("2080", "2034")}
    assert (o.inpendling.bo.isin(REGION) | o.utpendling.arb.isin(REGION)).sum() == 0


def test_nivaerna_raknar_pendlarna():
    """Kolumnsumman är alla jobb i kommunen, radsumman alla sysselsatta
    invånare -- till skillnad från delmatrisen i jobbandelar."""
    o = Omgivning(_db(), [2062, 2034])            # heltalskoder duger
    assert o.jobb("2062") == 100 + 20 + 40
    assert o.sysselsatta("2062") == 100 + 10 + 30 + 10
    assert o.andel_utpendling("2062") == pytest.approx(40 / 150)
    assert o.andel_inpendling("2034") == pytest.approx(5 / 65)


def test_destination_och_ursprung_dras_ur_matrisen():
    o = Omgivning(_db(), REGION)
    rng = np.random.default_rng(1)
    dest = pd.Series([o.dra_destination("2062", rng) for _ in range(4000)])
    assert dest.value_counts(normalize=True)["2080"] == pytest.approx(0.75, abs=0.03)
    assert set(o.dra_ursprung("2062", rng) for _ in range(50)) == {"2031"}
    with pytest.raises(ValueError, match="Ingen utpendling från 2034"):
        o.dra_destination("2034", rng)


def test_platsen_ar_en_deso_dragen_med_befolkningen():
    o = Omgivning(_db(), REGION)
    rng = np.random.default_rng(2)
    xs = pd.Series([o.dra_plats("2080", rng)[0] for _ in range(4000)])
    assert set(xs.round()) == {500.0, 10500.0}, "tomma DeSO ska inte dras"
    assert (xs == 500.0).mean() == pytest.approx(0.75, abs=0.03)
    with pytest.raises(ValueError, match="2081"):
        o.dra_plats("2081", rng)


def test_saknat_underlag_kastar():
    with pytest.raises(ValueError, match="commuting saknas"):
        Omgivning(_db(utan=("commuting",)), REGION)
    with pytest.raises(ValueError, match="saknar kommunerna"):
        Omgivning(_db(), ["2062", "2039"])
