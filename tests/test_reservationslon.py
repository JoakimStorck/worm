"""Löneanspråket under arbetslöshet.

Tre fel i det gamla beteendet, och de hänger ihop.

Anspråket skars med rho -- trettio procent -- samma sekund jobbet försvann.
Ingen sänker sitt löneanspråk med en tredjedel över natten; hon börjar med
anspråket från sin föregående anställning.

Sedan föll det 5 procent per MISSLYCKAD SÖKNING. Arbetslösa söker tretton
gånger om året, så anspråket halverades på ett år -- men bara för att
sökintensiteten råkade vara tretton. Den som sökte sällan behöll sitt anspråk
längre, vilket är bakvänt. Tiden är rätt variabel, och då blir sökintensitet
och anspråkets fall oberoende.

Och golvet var absolut och enda. Kollektivavtalens lägstalöner ligger inte på
en andel av DEN EGNA tidigare lönen utan på en andel av yrkets nivå.
"""
import numpy as np
import pandas as pd
import pytest

from core.event_handlers import (_uppdatera_reservation, bli_arbetslos,
                                 reservationsgolv)


class _Cfg:
    def __init__(self, sim):
        self.config = {"simulation": sim}


class _World:
    """Minsta möjliga värld: individtabellen och konfigurationen."""

    def __init__(self, rader, sim=None):
        self.individuals = pd.DataFrame(rader)
        for kol in ("w_res", "w_last", "unemployed_since", "pi_o"):
            if kol not in self.individuals.columns:
                self.individuals[kol] = np.nan
        self.cfg_reader = _Cfg(sim or {"reservation_mode": "duration",
                                       "reservation_half_days": 150.0,
                                       "reservation_width_days": 60.0,
                                       "reservation_floor_fraction": 0.6,
                                       "reservation_floor": 0.0})

    def get_ind(self, idx, kol):
        return self.individuals.at[idx, kol]


def _w(sim=None, **rad):
    return _World([{"status": "unemployed", **rad}], sim)


# ---------------------------------------------------------------------------
def test_anspraket_skars_inte_nar_jobbet_forsvinner():
    """Det gamla beteendet tog trettio procent på en gång."""
    w = _w(w_res=1.0)
    bli_arbetslos(w, 0, t_now=100.0)
    assert w.individuals.at[0, "w_res"] == pytest.approx(1.0)
    assert w.individuals.at[0, "w_last"] == pytest.approx(1.0)
    assert w.individuals.at[0, "unemployed_since"] == pytest.approx(100.0)


def test_anspraket_borjar_pa_senaste_lon():
    w = _w(w_res=1.0, w_last=1.0, unemployed_since=0.0)
    _uppdatera_reservation(w, 0, t_now=0.0)
    # EXAKT senaste lön, inte nästan. En logistisk kurva centrerad på 150
    # dagar har redan gett vika 8 procent vid noll, så kurvan normaliseras mot
    # sitt värde där.
    assert w.individuals.at[0, "w_res"] == pytest.approx(1.0)


def test_anspraket_faller_mot_golvet_och_stannar():
    w = _w(w_res=1.0, w_last=1.0, unemployed_since=0.0)
    tidigare = 2.0
    for t in (0, 60, 150, 240, 400, 1000, 3000):
        _uppdatera_reservation(w, 0, t_now=float(t))
        nu = float(w.individuals.at[0, "w_res"])
        assert nu <= tidigare + 1e-9      # monotont fallande
        tidigare = nu
    assert nu == pytest.approx(0.6, abs=0.01)     # golvet: 0.6 * senaste lön


def test_halvvags_nagra_dagar_efter_mittpunkten():
    """Normaliseringen flyttar halvvägspunkten några dagar framåt: priset för
    att anspråket ska starta exakt på senaste lön."""
    w = _w(w_res=1.0, w_last=1.0, unemployed_since=0.0)
    _uppdatera_reservation(w, 0, t_now=150.0)
    vid_150 = float(w.individuals.at[0, "w_res"])
    assert 0.80 < vid_150 < 0.82
    _uppdatera_reservation(w, 0, t_now=159.0)
    assert w.individuals.at[0, "w_res"] == pytest.approx(0.8, abs=0.01)


def test_sankningen_ar_inte_abrupt():
    """Efter en månad ska anspråket knappt ha rört sig."""
    w = _w(w_res=1.0, w_last=1.0, unemployed_since=0.0)
    _uppdatera_reservation(w, 0, t_now=30.0)
    assert w.individuals.at[0, "w_res"] > 0.95


def test_uppdateringen_ackumulerar_inte():
    """Sigmoiden räknas om ur w_last och unemployed_since vid varje sökning.
    Anropas den tio gånger på samma tidpunkt ska talet vara detsamma -- till
    skillnad från det gamla förfallet, som multiplicerade."""
    w = _w(w_res=1.0, w_last=1.0, unemployed_since=0.0)
    for _ in range(10):
        _uppdatera_reservation(w, 0, t_now=120.0)
    a = float(w.individuals.at[0, "w_res"])
    w2 = _w(w_res=1.0, w_last=1.0, unemployed_since=0.0)
    _uppdatera_reservation(w2, 0, t_now=120.0)
    assert a == pytest.approx(float(w2.individuals.at[0, "w_res"]))


def test_soktakten_paverkar_inte_anspraket():
    """Kärnan i bytet från sökningar till tid: två personer arbetslösa lika
    länge ska ha samma anspråk oavsett hur många gånger de sökt."""
    flitig = _w(w_res=1.0, w_last=1.0, unemployed_since=0.0)
    for t in range(0, 200, 5):
        _uppdatera_reservation(flitig, 0, t_now=float(t))
    _uppdatera_reservation(flitig, 0, t_now=200.0)
    lat = _w(w_res=1.0, w_last=1.0, unemployed_since=0.0)
    _uppdatera_reservation(lat, 0, t_now=200.0)
    assert (float(flitig.individuals.at[0, "w_res"])
            == pytest.approx(float(lat.individuals.at[0, "w_res"])))


# ---------------------------------------------------------------------------
# Golvet
# ---------------------------------------------------------------------------
def test_relativt_golv_mot_senaste_lon():
    w = _w(w_last=2.0)
    assert reservationsgolv(w, 0) == pytest.approx(1.2)


def test_pi_golvet_binder_for_den_lagavlonade():
    """Den som haft hög lön och sjunker till sextio procent ligger över
    avtalet; den som haft låg lön hamnar under vad någon får betala."""
    sim = {"reservation_floor_fraction": 0.6, "reservation_floor_pi_fraction": 0.7,
           "reservation_floor": 0.0}
    hog = _w(sim, w_last=2.0, pi_o=1.0)
    lag = _w(sim, w_last=0.5, pi_o=1.0)
    assert reservationsgolv(hog, 0) == pytest.approx(1.2)    # relativt binder
    assert reservationsgolv(lag, 0) == pytest.approx(0.7)    # Pi binder


def test_utan_senaste_lon_galler_det_absoluta_golvet():
    """Den som aldrig haft en anställning har ingen senaste lön."""
    w = _w({"reservation_floor_fraction": 0.6, "reservation_floor": 0.4}, w_last=np.nan)
    assert reservationsgolv(w, 0) == pytest.approx(0.4)


def test_golv_over_senaste_lon_later_anspraket_sta():
    w = _w({"reservation_floor_fraction": 0.6, "reservation_floor": 1.5},
           w_res=1.0, w_last=1.0, unemployed_since=0.0)
    _uppdatera_reservation(w, 0, t_now=5000.0)
    assert w.individuals.at[0, "w_res"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Lägena
# ---------------------------------------------------------------------------
def test_per_search_laget_beter_sig_som_forr():
    sim = {"reservation_mode": "per_search", "reservation_decay_per_search": 0.95,
           "reservation_floor": 0.4}
    w = _w(sim, w_res=1.0)
    for _ in range(3):
        _uppdatera_reservation(w, 0, t_now=None)
    assert w.individuals.at[0, "w_res"] == pytest.approx(0.95 ** 3)


def test_duration_laget_ror_inget_utan_arbetsloshetsklocka():
    """Den anställda har unemployed_since = NaN och ska lämnas i fred."""
    w = _w(w_res=1.0, w_last=1.0, unemployed_since=np.nan)
    _uppdatera_reservation(w, 0, t_now=500.0)
    assert w.individuals.at[0, "w_res"] == pytest.approx(1.0)


def test_langa_tider_ger_inte_overflow():
    w = _w(w_res=1.0, w_last=1.0, unemployed_since=0.0)
    _uppdatera_reservation(w, 0, t_now=1e9)
    assert np.isfinite(w.individuals.at[0, "w_res"])
