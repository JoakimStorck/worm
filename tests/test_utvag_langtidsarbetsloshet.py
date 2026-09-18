"""Utvägen ur långtidsarbetslöshet.

Arbetslöshet var ett ABSORBERANDE tillstånd. Diffusionen suddar cirkeln,
bredden går in i konkurrenskraften som 2*ro2/(rho2 + ro2), q faller, hon blir
inte anställd, och skärpning kräver just den anställning hon inte får. I en
tioårskörning satt 596 personer fast så -- r_i 0.737 mot de övriga
arbetslösas 0.393, alltså 39 procent av deras konkurrenskraft -- och 403 av
dem låg i Älvdalen: tolv procent av kommunens arbetskraft.

Två utvägar. Diffusionen får ett tak relativt cirkelns egen vilaradie, och den
går långsammare. Och omskolningen, som var fullt byggd men aldrig utlöstes,
schemaläggs med en fara som stiger med arbetslöshetens längd.
"""
import numpy as np
import pandas as pd
import pytest

from core.occupations.competence import EMPTY, Circles, CompetenceParams


def _cirklar(n=1, rho2=0.073):
    c = Circles(n=n, K=4)
    for i in range(n):
        c.add(i, "OCC:1", 0.0, 0.0, rho2, mass=5.0)
    return c


# ---------------------------------------------------------------------------
# Diffusionen
# ---------------------------------------------------------------------------
def test_diffusionen_har_ett_tak():
    """Utan tak växer rho2 obegränsat och arbetslöshet blir absorberande."""
    p = CompetenceParams(D=0.05, diffusion_max_ratio=4.0)
    c = _cirklar()
    inaktiv = np.full(1, EMPTY, dtype=c.key.dtype)   # ingen aktiv cirkel
    for _ in range(200):
        c.evolve(1.0, inaktiv, p)
    assert c.rho2[0, 0] == pytest.approx(4.0 * 0.073, rel=1e-6)


def test_taket_ar_relativt_egen_vilaradie():
    """Den med bred profil från början ska inte straffas av samma gräns som
    den med smal."""
    p = CompetenceParams(D=0.05, diffusion_max_ratio=4.0)
    smal, bred = _cirklar(rho2=0.05), _cirklar(rho2=0.20)
    inaktiv = np.full(1, EMPTY, dtype=smal.key.dtype)
    for c in (smal, bred):
        for _ in range(200):
            c.evolve(1.0, inaktiv, p)
    assert smal.rho2[0, 0] == pytest.approx(0.20, rel=1e-6)
    assert bred.rho2[0, 0] == pytest.approx(0.80, rel=1e-6)


def test_taket_gar_att_stanga_av():
    p = CompetenceParams(D=0.05, diffusion_max_ratio=0.0)
    c = _cirklar()
    inaktiv = np.full(1, EMPTY, dtype=c.key.dtype)   # ingen aktiv cirkel
    for _ in range(200):
        c.evolve(1.0, inaktiv, p)
    assert c.rho2[0, 0] > 0.8          # bara det praktiska taket 4.0 kvar


def test_langsammare_forval():
    """0.015 gav fördubblad rho2 på 2.4 år. 0.004 ger ungefär nio."""
    p = CompetenceParams()
    assert p.D == pytest.approx(0.004)
    assert 0.073 / (2 * p.D) == pytest.approx(9.1, abs=0.3)


def test_skarpningen_ar_orord():
    """Den som arbetar ska fortfarande återfå sin spets."""
    p = CompetenceParams(D=0.05, tau_months=6.0)
    c = _cirklar()
    c.rho2[0, 0] = 0.3
    aktiv = np.array([0])                                # cirkelns plats
    for _ in range(10):
        c.evolve(0.5, aktiv, p)
    assert c.rho2[0, 0] == pytest.approx(0.073, abs=0.01)


# ---------------------------------------------------------------------------
# Omskolningen
# ---------------------------------------------------------------------------
class _Cfg:
    def __init__(self, sim):
        self.config = {"simulation": sim}


class _World:
    def __init__(self, rad, sim=None):
        self.individuals = pd.DataFrame([rad])
        for kol in ("unemployed_since", "last_education_draw",
                    "propensity_start_education"):
            if kol not in self.individuals.columns:
                self.individuals[kol] = np.nan
        self.cfg_reader = _Cfg(sim or {"education_rate_scale": 1.0,
                                       "education_half_days": 270.0,
                                       "education_width_days": 90.0})
        self.kö = []

    def _push_event(self, e):
        self.kö.append(e)


def _andel(sim, t_unemp, prop=0.12, n=4000, seed=0):
    from core.event_handlers import _prova_utbildning
    np.random.seed(seed)
    träff = 0
    for _ in range(n):
        w = _World({"unemployed_since": 0.0, "last_education_draw": np.nan,
                    "propensity_start_education": prop}, sim)
        if _prova_utbildning(w, 0, t_unemp):
            träff += 1
    return träff / n


def test_faran_stiger_med_arbetsloshetens_langd():
    sim = {"education_rate_scale": 1.0, "education_half_days": 270.0,
           "education_width_days": 90.0}
    tidigt = _andel(sim, 30.0)
    sent = _andel(sim, 1200.0)
    assert sent > tidigt * 3
    # Och den som nyss blivit arbetslös söker jobb, inte utbildning.
    assert tidigt < 0.02


def test_dragningen_ar_oberoende_av_sokfrekvens():
    """Poisson-tunning mot förfluten tid. En sannolikhet per SÖKNING hade
    gjort omskolning vanligare för den som söker ofta -- samma fel som det
    gamla löneförfallet."""
    from core.event_handlers import _prova_utbildning

    sim = {"education_rate_scale": 20.0, "education_half_days": 0.0,
           "education_width_days": 1.0}

    def kör(steg, seed):
        np.random.seed(seed)
        träff = 0
        for _ in range(3000):
            w = _World({"unemployed_since": 0.0, "last_education_draw": np.nan,
                        "propensity_start_education": 0.12}, sim)
            for t in np.arange(steg, 730.0 + steg, steg):
                if _prova_utbildning(w, 0, float(t)):
                    träff += 1
                    break
        return träff / 3000

    gles = kör(180.0, 1)
    tät = kör(20.0, 1)
    assert abs(gles - tät) < 0.05


def test_skalan_stanger_av():
    assert _andel({"education_rate_scale": 0.0}, 2000.0) == 0.0


def test_utan_arbetsloshetsklocka_sker_inget():
    from core.event_handlers import _prova_utbildning

    w = _World({"unemployed_since": np.nan, "last_education_draw": np.nan,
                "propensity_start_education": 0.12})
    assert _prova_utbildning(w, 0, 500.0) is False


def test_handelsen_pushas_med_varaktighet():
    from core.event_handlers import _prova_utbildning

    np.random.seed(3)
    sim = {"education_rate_scale": 500.0, "education_half_days": 0.0,
           "education_width_days": 1.0, "education_duration_days": 365.0}
    w = _World({"unemployed_since": 0.0, "last_education_draw": np.nan,
                "propensity_start_education": 1.0}, sim)
    assert _prova_utbildning(w, 0, 900.0) is True
    assert w.kö[0]["event_type"] == "start_education"
    assert w.kö[0]["params"]["duration_days"] == 365.0


def test_benagenheten_raknas_inte_upp_per_avslag():
    """Den steg med 0.1 och kapades vid 1.0, alltså full benägenhet efter tio
    avslag -- vilket en arbetslös når på tio månader. Tidsberoendet ligger nu
    i faran, och benägenheten är en stabil individegenskap."""
    import inspect

    from core import event_handlers

    kalla = inspect.getsource(event_handlers.handle_start_job_search)
    assert "current_prop + 0.1" not in kalla
    assert "_prova_utbildning" in kalla
