"""Koncentrationsexponenten i individernas yrkesfördelning.

Individernas yrken dras ur kommunens yrkesprofil upphöjd till power och
omnormaliserad. Jobben dras ur samma profil UTAN exponent -- se
generate_employers_with_target_jobs, som använder sni_dist['prob'] rakt av.
Arbetare och jobb får därmed olika koncentration i uppgiftsrummet by
construction, vilket är en felmatchningskälla oberoende av allt annat.

Värdet 1.5 stod hårdkodat utan härledning. Testerna låser att det går att
ställa om och vad omställningen betyder.
"""
import os

import numpy as np
import pytest
import yaml

from core.configreader import ConfigReader

# Sökvägar relativt TESTFILEN, inte arbetskatalogen. kor_0077.sh kör pytest
# från tests/, medan en körning från repo-roten också ska fungera.
ROT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCEN = os.path.join(ROT, "scenarios")


def _scenario(namn):
    with open(os.path.join(SCEN, namn), encoding="utf-8") as f:
        return ConfigReader.resolve_extends(yaml.safe_load(f), SCEN)


def _vikter(prob, power):
    w = np.asarray(prob, dtype=float) ** power
    return w / w.sum()


def test_exponent_ett_ger_oforandrad_fordelning():
    """1.0 betyder att individer och jobb dras ur samma fördelning."""
    p = [0.5, 0.3, 0.2]
    assert _vikter(p, 1.0) == pytest.approx(p)


def test_hogre_exponent_koncentrerar():
    """Vanliga yrken blir vanligare, sällsynta sällsyntare."""
    p = [0.5, 0.3, 0.2]
    w = _vikter(p, 1.5)
    assert w[0] > p[0]
    assert w[2] < p[2]
    # och ordningen bevaras
    assert w[0] > w[1] > w[2]


def test_koncentrationen_ar_monoton_i_exponenten():
    p = [0.5, 0.3, 0.2]
    andel_storst = [_vikter(p, e)[0] for e in (0.5, 1.0, 1.5, 2.0, 3.0)]
    assert andel_storst == sorted(andel_storst)


def test_entropin_faller_med_exponenten():
    """Måttet på hur mycket koncentrationen skiljer arbetare från jobb."""
    p = np.array([0.4, 0.3, 0.2, 0.1])
    H = lambda w: -(w * np.log(w)).sum()  # noqa: E731
    assert H(_vikter(p, 1.5)) < H(_vikter(p, 1.0))


def test_forvalet_ar_oforandrat():
    """1.5 är kvar som förval för att inte ändra befintliga körningar tyst."""
    cfg = _scenario("_simulation_defaults.yml")
    assert cfg["simulation"]["occupation_concentration"] == 1.5


def test_varde_ur_scenariot_slar_igenom():
    import sqlite3
    cfg = _scenario("ovansiljan_3_kommuner.yml")
    cfg["simulation"]["occupation_concentration"] = 1.0
    r = ConfigReader(cfg, sqlite3.connect(":memory:"))
    assert float(r.config["simulation"]["occupation_concentration"]) == 1.0


def test_ingen_hardkodad_exponent_kvar():
    """Regressionen som gjorde det här svårt att hitta: ett tal i koden utan
    härledning och utan väg att ändra det."""
    import inspect

    from core import scenariobuilder

    kalla = inspect.getsource(scenariobuilder)
    assert "power = 1.5" not in kalla
    assert "occupation_concentration" in kalla
