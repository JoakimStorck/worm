"""Rakingen till P(yrke, nivå, inriktning | ålder, kön), steg 4b
(core/utbildningsfordelning.py, docs/utbildningsmodell.md)."""
import sqlite3

import numpy as np
import pandas as pd
import pytest

from core.utbildningsfordelning import bygg_fordelning, ipf_2d, raka


def _oddskvot(x, i, j, k, m):
    return (x[i, k] * x[j, m]) / (x[i, m] * x[j, k])


def test_formen_behaller_oddskvoterna_och_far_de_nya_summorna():
    """TAB655 är befolkningen; de anställdas nivå- och inriktningstotaler är
    andra. Sambandet -- oddskvoterna -- ska följa med, inte totalerna."""
    form = np.array([[40.0, 0.0, 0.0], [20.0, 30.0, 10.0], [5.0, 15.0, 40.0]])
    rader, kolumner = np.array([10.0, 50.0, 40.0]), np.array([45.0, 20.0, 35.0])
    x = ipf_2d(form, rader, kolumner)
    np.testing.assert_allclose(x.sum(axis=1), rader, rtol=1e-8)
    np.testing.assert_allclose(x.sum(axis=0), kolumner, rtol=1e-8)
    assert _oddskvot(x, 1, 2, 0, 1) == pytest.approx(_oddskvot(form, 1, 2, 0, 1), rel=1e-6)
    # strukturell nolla: förgymnasial nivå har bara allmän inriktning
    assert x[0, 1] == 0 and x[0, 2] == 0
    with pytest.raises(ValueError, match="olika total"):
        ipf_2d(form, rader, kolumner * 2)


def test_rakingen_aterger_en_fordelning_utan_trevagssamspel():
    """Rakingen är maximum likelihood-skattningen utan trevägssamspel. En
    sann fördelning av den formen ska återfås exakt ur sina tre marginaler --
    och det gäller inte om de raka marginalerna ignoreras."""
    rng = np.random.default_rng(3)
    a, b, c = rng.random((5, 3)), rng.random((5, 4)), rng.random((4, 3))
    sann = 1000 * a[:, None, :] * b[:, :, None] * c[None, :, :]
    x, fel = raka(sann.sum(axis=1), sann.sum(axis=2), sann.sum(axis=0))
    assert max(fel) < 1e-6
    np.testing.assert_allclose(x, sann, rtol=1e-4)


YRKEN, NIVAER, INRIKTNINGAR = ["222", "522"], ["4", "6"], ["0", "7"]


def _sann():
    """En sann fördelning utan trevägssamspel, X = a[o,f] b[o,l] c[l,f]: de
    tre marginalerna är då förenliga, och rakingen ska återfå den."""
    a = np.array([[0.2, 3.0], [2.0, 0.5]])     # yrke x inriktning
    b = np.array([[0.3, 4.0], [3.0, 0.4]])     # yrke x nivå
    c = np.array([[3.0, 1.0], [0.5, 4.0]])     # nivå x inriktning
    return 100 * a[:, None, :] * b[:, :, None] * c[None, :, :]


def _db(nivaskala=(1.0, 1.0), inriktningsskala=(1.0, 1.0)):
    """Anställda 25-29 år, kvinnor, ur den sanna fördelningen. Befolkningen
    (TAB655, 25-34) har samma samband mellan nivå och inriktning men andra
    nivå- och inriktningstotaler: varje rad och kolumn skalas för sig,
    vilket inte ändrar oddskvoterna."""
    x = _sann()
    conn = sqlite3.connect(":memory:")
    rader = lambda m, ri, ci, rn, cn, **k: pd.DataFrame(
        [{rn: ri[i], cn: ci[j], **k, "val": m[i, j]} for i in range(2) for j in range(2)])
    of = rader(x.sum(axis=1), YRKEN, INRIKTNINGAR, "ssyk_code", "field")
    ol = rader(x.sum(axis=2), YRKEN, NIVAER, "ssyk_code", "level")
    lf = rader(x.sum(axis=0) * np.array(nivaskala)[:, None]
               * np.array(inriktningsskala)[None, :] * 50, NIVAER, INRIKTNINGAR,
               "level", "field")
    for d, alder in ((of, "25-29"), (ol, "25-29")):
        d["age_class"], d["sex"], d["year"] = alder, "2", 2024
        d.rename(columns={"val": "employed"}, inplace=True)
    lf["age_class"], lf["sex"], lf["year"], lf["background"] = "25-34", "2", 2024, "S"
    lf.rename(columns={"val": "population"}, inplace=True)
    of.to_sql("employment_occupation_field", conn, index=False)
    ol.to_sql("employment_occupation_level", conn, index=False)
    lf.to_sql("population_level_field", conn, index=False)
    return conn


def _som_array(d):
    x = np.zeros((2, 2, 2))
    for r in d.itertuples():
        x[YRKEN.index(r.ssyk_code), NIVAER.index(r.level), INRIKTNINGAR.index(r.field)] = r.employed
    return x


def test_de_anstallda_marginalerna_ar_exakta_och_tioarsklassen_valjs():
    d, diag = bygg_fordelning(_db())
    np.testing.assert_allclose(_som_array(d), _sann(), rtol=1e-4)
    assert (diag[["fel_of", "fel_ol", "fel_lf"]].max() < 1e-6).all()


def test_befolkningens_samband_styr_men_inte_dess_nivatotal():
    """Befolkningen har andra nivå- och inriktningstotaler än de anställda. Hade TAB655
    använts som marginal och inte som form hade de anställdas nivåtotal
    skrivits över; nu ska resultatet vara den sanna fördelningen ändå."""
    d, _ = bygg_fordelning(_db((4.0, 0.25), (0.3, 2.0)))
    np.testing.assert_allclose(_som_array(d), _sann(), rtol=1e-4)


def test_saknade_tabeller_och_aldersklasser_kastar():
    with pytest.raises(ValueError, match="fetch_data.py"):
        bygg_fordelning(sqlite3.connect(":memory:"))
    conn = _db()
    conn.execute("UPDATE population_level_field SET age_class = '35-44'")
    with pytest.raises(ValueError, match="25-34"):
        bygg_fordelning(conn)
