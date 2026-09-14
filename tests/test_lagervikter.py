"""Viktad placering av arbetsgivare.

fetch_zones normaliserade redan varje lagers viktfält -- num_workplaces för
verksamhets- och handelsområden, population för tätorter -- till kolumnen
weight_field. Slingan drog sedan med gdf.sample(1) och rng.choice(all_layers),
alltså likformigt i båda leden: en DeSO med 2 000 anställda hade samma
sannolikhet som en med fem, och småorter fick lika stor andel av
arbetsgivarna som tätorter. Hela layer_configs-blocket i scenariofilen var
verkningslöst.

Det spelar roll för pendlingen: var arbetsgivarna ligger INOM kommunen avgör
avstånden, och medianpendlingen är det enda som går att pröva mot SCB innan
jobbantalen per kommun är rätt.
"""
import numpy as np
import pandas as pd
import pytest

from core.scenariobuilder import _lagervikter


def _lager(vikter):
    return pd.DataFrame({"weight_field": vikter})


def test_zonerna_vags_efter_sitt_viktfalt():
    namn, p, zon = _lagervikter({"urban_areas": _lager([2000.0, 5.0, 95.0])})
    assert namn == ["urban_areas"]
    tot = 2000 + 5 + 95
    assert zon["urban_areas"] == pytest.approx([2000 / tot, 5 / tot, 95 / tot])
    # Likformigt hade gett 1/3 åt zonen med fem anställda.
    assert zon["urban_areas"][1] < 0.01


def test_lagret_vags_efter_sin_sammanlagda_vikt():
    """Fyra lager gav 25 procent var oavsett hur mycket sysselsättning de bar."""
    namn, p, _ = _lagervikter({
        "business_zones": _lager([800.0, 200.0]),     # 1000
        "urban_areas": _lager([3000.0]),              # 3000
        "small_localities": _lager([50.0, 50.0]),     # 100
    })
    andel = dict(zip(namn, p))
    assert andel["urban_areas"] == pytest.approx(3000 / 4100)
    assert andel["small_localities"] == pytest.approx(100 / 4100)
    # Det gamla beteendet gav 1/3 åt vardera.
    assert andel["small_localities"] < 0.1


def test_lager_utan_underlag_blir_likformigt_inom_sig():
    """...men får bara sin zonandel av lagervalet, inte en fjärdedel bara för
    att lagret finns."""
    namn, p, zon = _lagervikter({
        "urban_areas": _lager([1000.0]),
        "commercial_zones": _lager([0.0, 0.0, 0.0]),
    })
    andel = dict(zip(namn, p))
    assert zon["commercial_zones"] == pytest.approx([1 / 3, 1 / 3, 1 / 3])
    assert andel["commercial_zones"] == pytest.approx(3 / 1003)


def test_saknade_och_negativa_vikter_nollas():
    _, _, zon = _lagervikter({"x": _lager([100.0, np.nan, -50.0, 100.0])})
    assert zon["x"] == pytest.approx([0.5, 0.0, 0.0, 0.5])


def test_tomma_lager_hoppas_over():
    namn, p, _ = _lagervikter({"tomt": pd.DataFrame({"weight_field": []}),
                               "urban_areas": _lager([10.0])})
    assert namn == ["urban_areas"] and p == pytest.approx([1.0])


def test_inga_lager_alls_kastar():
    with pytest.raises(ValueError):
        _lagervikter({}, municipal_code="2062")


def test_sannolikheterna_summerar_till_ett():
    namn, p, zon = _lagervikter({
        "a": _lager([1.0, 2.0, 3.0]), "b": _lager([10.0]), "c": _lager([4.0, 4.0])})
    assert p.sum() == pytest.approx(1.0)
    for v in zon.values():
        assert v.sum() == pytest.approx(1.0)


def test_dragningen_foljer_vikterna():
    """Slut till slut: dras zoner med de returnerade sannolikheterna ska
    utfallet spegla vikterna och inte antalet zoner."""
    _, _, zon = _lagervikter({"x": _lager([90.0, 5.0, 5.0])})
    rng = np.random.default_rng(0)
    drag = rng.choice(3, size=20000, p=zon["x"])
    andel = np.bincount(drag, minlength=3) / 20000
    assert andel[0] == pytest.approx(0.90, abs=0.01)
    assert andel[1] == pytest.approx(0.05, abs=0.01)
