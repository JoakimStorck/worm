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


def test_avtalsgolvet_ligger_inte_i_ansprake():
    """Jag lade in det som en Pi-andel och tog bort det igen: avtalsgolvet
    finns redan på POSITIONENS sida, som wage_floor_share * Pi i
    negotiated_wage. Påfört hennes anspråk hade det skalats med hennes
    tidigare lön, men avtalet i vården är detsamma oavsett vad hon tjänade
    förut."""
    import inspect

    from core import event_handlers

    kalla = inspect.getsource(event_handlers.reservationsgolv)
    assert "reservation_floor_pi_fraction" not in kalla
    # Och golvet är rent personrelativt.
    assert reservationsgolv(_w(w_last=2.0), 0) == pytest.approx(1.2)


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


# ---------------------------------------------------------------------------
# Percentilvägen
# ---------------------------------------------------------------------------
def _wp(**rad):
    """Individ med skattad relevansfördelning."""
    sim = {"reservation_mode": "duration", "reservation_half_days": 150.0,
           "reservation_width_days": 60.0, "reservation_min_percentile": 0.05,
           "reservation_max_drop_per_month": 0.0, "reservation_floor_fraction": 0.6,
           "reservation_floor": 0.0}
    return _World([{"status": "unemployed", **rad}], sim)


def test_anspraket_ar_percentil_i_egen_fordelning():
    """Median 1.0, log-sd 0.3, ingångspercentil 0.8 -> anspråket startar på
    kvantilen 0.8, alltså 1.0 * exp(0.3 * 0.8416)."""
    w = _wp(w_res=1.29, w_last=1.29, unemployed_since=0.0,
            w_rel_med=1.0, w_rel_sd=0.3, p_claim0=0.8)
    _uppdatera_reservation(w, 0, t_now=0.0)
    assert w.individuals.at[0, "w_res"] == pytest.approx(np.exp(0.3 * 0.8416), abs=1e-3)


def test_percentilen_faller_mot_bottenpercentilen():
    w = _wp(w_res=1.29, w_last=1.29, unemployed_since=0.0,
            w_rel_med=1.0, w_rel_sd=0.3, p_claim0=0.8)
    _uppdatera_reservation(w, 0, t_now=5000.0)
    # p_min = 0.05 -> kvantilen exp(0.3 * (-1.6449))
    assert w.individuals.at[0, "w_res"] == pytest.approx(np.exp(-0.3 * 1.6449), abs=1e-3)


def test_bred_fordelning_ger_djupare_fall():
    """Botten är endogen: den som ser en bred lönefördelning kan sjunka
    längre än den som ser en smal, oavsett egen historik."""
    smal = _wp(w_res=1.0, w_last=1.0, unemployed_since=0.0,
               w_rel_med=1.0, w_rel_sd=0.1, p_claim0=0.5)
    bred = _wp(w_res=1.0, w_last=1.0, unemployed_since=0.0,
               w_rel_med=1.0, w_rel_sd=0.5, p_claim0=0.5)
    for w in (smal, bred):
        _uppdatera_reservation(w, 0, t_now=5000.0)
    assert bred.individuals.at[0, "w_res"] < smal.individuals.at[0, "w_res"]


def test_den_som_lag_under_medel_borjar_lagre():
    """Asymmetrin faller ut ur ingångspercentilen: inget eget steg behövs."""
    over = _wp(w_res=1.0, w_last=1.0, unemployed_since=0.0,
               w_rel_med=1.0, w_rel_sd=0.3, p_claim0=0.9)
    under = _wp(w_res=1.0, w_last=1.0, unemployed_since=0.0,
                w_rel_med=1.0, w_rel_sd=0.3, p_claim0=0.2)
    for w in (over, under):
        _uppdatera_reservation(w, 0, t_now=0.0)
    assert over.individuals.at[0, "w_res"] > under.individuals.at[0, "w_res"]


def test_taket_bromsar_fallet():
    """Percentilskalan är olinjär, så en person högt upp kan annars tappa en
    femtedel på en månad. Trögheten ÄR mekanismen och får inte kringgås."""
    utan = _wp(w_res=2.0, w_last=2.0, unemployed_since=0.0,
               w_rel_med=1.0, w_rel_sd=0.6, p_claim0=0.95, w_res_time=0.0)
    med = _World([{"status": "unemployed", "w_res": 2.0, "w_last": 2.0,
                   "unemployed_since": 0.0, "w_rel_med": 1.0, "w_rel_sd": 0.6,
                   "p_claim0": 0.95, "w_res_time": 0.0}],
                 {"reservation_mode": "duration", "reservation_half_days": 150.0,
                  "reservation_width_days": 60.0, "reservation_min_percentile": 0.05,
                  "reservation_max_drop_per_month": 0.08,
                  "reservation_floor_fraction": 0.6, "reservation_floor": 0.0})
    for w in (utan, med):
        _uppdatera_reservation(w, 0, t_now=300.0)
    assert med.individuals.at[0, "w_res"] > utan.individuals.at[0, "w_res"]
    # Med taket får anspråket inte ha fallit mer än 8 % per månad.
    assert med.individuals.at[0, "w_res"] >= 2.0 * (1 - 0.08) ** (300 / 30.44) - 1e-9


def test_tunn_mangd_faller_tillbaka_pa_personrelativt():
    """En fördelning skattad på tre positioner är brus."""
    w = _wp(w_res=1.0, w_last=1.0, unemployed_since=0.0,
            w_rel_med=np.nan, w_rel_sd=np.nan, p_claim0=np.nan)
    _uppdatera_reservation(w, 0, t_now=5000.0)
    assert w.individuals.at[0, "w_res"] == pytest.approx(0.6, abs=0.01)


def test_normkvantilen_stammer():
    from core.event_handlers import _normkvantil
    for p, v in ((0.05, -1.644854), (0.5, 0.0), (0.8, 0.841621), (0.99, 2.326348)):
        assert _normkvantil(p) == pytest.approx(v, abs=1e-5)


# ---------------------------------------------------------------------------
# Relevansfördelningen och varaktighetsmåttet
# ---------------------------------------------------------------------------
def test_relevansfordelningen_vags_med_motessannolikheten():
    """Fördelningen ska spegla vad hon SER: positioner nära i uppgiftsrummet
    och nära i planet väger tyngre."""
    import numpy as _np

    from core.matching_core import relevansfordelning

    class W:
        def __init__(self):
            n = 40
            rng = _np.random.default_rng(0)
            # Halva nära i uppgiftsrummet och lågt betalda, halva långt bort
            # och högt betalda.
            self._jobs = pd.DataFrame({
                "x_occ": _np.r_[_np.full(20, 0.0), _np.full(20, 2.0)],
                "y_occ": _np.zeros(n), "r_o": _np.full(n, 0.3),
                "r_req": _np.full(n, 0.3),
                "wage": _np.r_[_np.full(20, 0.8), _np.full(20, 2.0)],
                "x": _np.zeros(n), "y": _np.zeros(n)})
            self.individuals = pd.DataFrame([{"x_occ": 0.0, "y_occ": 0.0,
                                              "r_i": 0.1, "x": 0.0, "y": 0.0,
                                              "w_res": 1.0}])
            self.cfg_reader = _Cfg({"sigma_gamma": 1.0, "requirement_k": 2.0,
                                    "choice_scale": 0.05})

        def vacant_mask(self):
            return _np.ones(len(self._jobs), bool)

        def job_arrays(self):
            from core.occupations.utils import build_job_arrays
            return build_job_arrays(self._jobs)

        def ind_row(self, idx):
            return self.individuals.iloc[idx]

    f = relevansfordelning(W(), 0)
    assert f is not None
    med, sd, n = f
    # De nära och lågt betalda dominerar vikten, så medianen ligger under 2.0.
    assert med < 1.2
    assert sd > 0


def test_tunn_vakansstock_ger_ingen_fordelning():
    import numpy as _np

    from core.matching_core import relevansfordelning

    class W:
        _jobs = pd.DataFrame({"x_occ": [0.0], "y_occ": [0.0], "r_o": [0.3],
                              "r_req": [0.3], "wage": [1.0], "x": [0.0], "y": [0.0]})
        individuals = pd.DataFrame([{"x_occ": 0.0, "y_occ": 0.0, "r_i": 0.1,
                                     "x": 0.0, "y": 0.0}])
        cfg_reader = _Cfg({})

        def vacant_mask(self):
            return _np.ones(1, bool)

        def job_arrays(self):
            from core.occupations.utils import build_job_arrays
            return build_job_arrays(self._jobs)

        def ind_row(self, idx):
            return self.individuals.iloc[idx]

    assert relevansfordelning(W(), 0) is None


def test_varaktighetsmattet(tmp_path):
    import os

    from scripts.analysis import arbetsloshetens_varaktighet

    R = str(tmp_path / "run")
    os.makedirs(R)
    t = 1000.0
    rader = ([{"individual_id": f"i{i}", "status": "unemployed",
               "unemployed_since": t - 400} for i in range(30)]
             + [{"individual_id": f"j{i}", "status": "unemployed",
                 "unemployed_since": t - 50} for i in range(30)]
             + [{"individual_id": f"k{i}", "status": "employed",
                 "unemployed_since": np.nan} for i in range(40)])
    pd.DataFrame(rader).to_csv(os.path.join(R, "final_state_individuals.csv"),
                               index=False)
    v = arbetsloshetens_varaktighet(R, t_slut=t)
    assert v["n"] == 60
    assert v["andel_12man"] == pytest.approx(0.5)
    assert v["andel_6man"] == pytest.approx(0.5)
    assert v["median"] == pytest.approx(225.0)


def test_uppstartens_arbetslosa_far_klocka():
    """Utan unemployed_since och w_last returnerar _uppdatera_reservation
    tidigt, och anspråket står kvar på rho * Pi för evigt. I en körning var
    2 553 av 3 233 arbetslösa sådana -- fyra femtedelar -- och eftersom Pi är
    deras EGET yrkes pris avvisade de varje lågavlönad position vars Pi låg
    lägre. Stocken blev den ursprungliga kohorten, frusen."""
    df = pd.DataFrame({"status": ["unemployed", "employed", "not_in_labor_force"],
                       "pi_o": [1.0, 1.2, 0.9]})
    rho = 0.7
    df["w_res"] = rho * df["pi_o"]
    df["w_last"] = np.where(df["status"].to_numpy() == "unemployed",
                            df["w_res"].to_numpy(), np.nan)
    df["unemployed_since"] = np.where(df["status"].to_numpy() == "unemployed",
                                      0.0, np.nan)
    assert df.at[0, "w_last"] == pytest.approx(0.7)
    assert df.at[0, "unemployed_since"] == 0.0
    assert np.isnan(df.at[1, "w_last"])          # anställd: ingen klocka
    assert np.isnan(df.at[2, "unemployed_since"])


def test_scenariobuilder_satter_klockan():
    import inspect

    from core import scenariobuilder

    kalla = inspect.getsource(scenariobuilder)
    assert 'df["unemployed_since"] = np.where' in kalla
    assert 'df["w_last"] = np.where' in kalla


def test_uppstartens_fordelning_skattas_en_gang():
    """Och att passet finns: utan den faller kohorten tillbaka på den
    personrelativa sigmoiden i stället för percentilvägen."""
    import inspect

    from core.world import World

    assert "_skatta_relevansfordelningar" in inspect.getsource(World.simulate)
    kalla = inspect.getsource(World._skatta_relevansfordelningar)
    assert "relevansfordelning" in kalla
    assert "p_claim0" in kalla
