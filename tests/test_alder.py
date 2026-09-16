"""Ålder, arbetslivets längd och pensionsavgång.

Före 0155 fanns ingen ålder. Tenure drogs exponentiellt med medel åtta år
oberoende av allt annat, ingen lämnade arbetsmarknaden av åldersskäl, och
ersättningsrekryteringen efter en pensionsavgång fanns därför inte som
rekryteringsflöde.
"""
import sqlite3
import textwrap

import numpy as np
import pandas as pd
import pytest

from conftest import FakeConfig, make_world

from core.database.load_population_age import las_befolkning_per_alder
from core.scenariobuilder import ScenarioBuilder


# ----------------------------------------------------------------------
# Läsaren
# ----------------------------------------------------------------------

BRED = """\
Folkmängd efter region, ålder, kön och år

"region";"ålder";"kön";"2024"
"00 Riket";"20 år";"totalt";100000
"0000 Riket";"20 år";"totalt";100000
"2062 Mora";"20 år";"totalt";200
"2062 Mora";"21 år";"totalt";210
"2062 Mora";"100+ år";"totalt";3
"2062 Mora";"totalt";"totalt";20000
"2039 Älvdalen";"20 år";"totalt";90
"""

CSV3 = """\
"region";"alder";"tid";"BE0101N1"
"00";"20";"2024";100000
"20";"20";"2024";5000
"2062";"20";"2024";200
"2062";"100+";"2024";3
"2039";"20";"2024";90
"""

KLARTEXT = """\
"region";"ålder";"2024"
"Mora";"20 år";200
"Älvdalen";"20 år";90
"""

LANGT = """\
"region";"ålder";"kön";"tid";"Folkmängd"
"2062 Mora";"20 år";"män";"2023";110
"2062 Mora";"20 år";"kvinnor";"2023";95
"2062 Mora";"21 år";"män";"2023";100
"2062 Mora";"21 år";"kvinnor";"2023";105
"""


def _skriv(tmp_path, namn, text):
    p = tmp_path / namn
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return str(p)


def test_riksraden_och_alderstotalen_utesluts(tmp_path):
    """Riksraden skrivs "00 Riket" i det uttag jag sett. Den tvåsiffriga koden
    faller redan på extraktionen av fyra siffror, men en fyrsiffrig variant
    skulle passera den -- och bli en kommun med tio miljoner invånare. Båda
    formerna prövas."""
    df = las_befolkning_per_alder(_skriv(tmp_path, "bred.csv", BRED))
    assert set(df["municipal_code"]) == {"2062", "2039"}
    # "totalt" i ålderskolumnen skulle annars bli en egen ålder och
    # fördubbla kommunens folkmängd.
    assert df[df.municipal_code == "2062"]["n_total"].sum() == 200 + 210 + 3


def test_hundraplus_blir_hundra(tmp_path):
    df = las_befolkning_per_alder(_skriv(tmp_path, "bred.csv", BRED))
    assert 100 in set(df["age"])
    assert df["age"].max() == 100


def test_langt_format_med_koder(tmp_path):
    """Uttaget som fetch_data.py hämtar: koder i långt format, med
    värdekolumnen döpt till tabellens innehållskod. Riket ("00") och länet
    ("20") ligger i samma regionkolumn som kommunerna och faller på
    fyrsiffrighetskravet."""
    df = las_befolkning_per_alder(_skriv(tmp_path, "csv3.csv", CSV3))
    assert set(df["municipal_code"]) == {"2062", "2039"}
    assert int(df[(df.municipal_code == "2062") & (df.age == 20)]["n_total"].iloc[0]) == 200
    assert 100 in set(df["age"])
    assert set(df["year"]) == {2024}


def test_klartext_utan_koder_ger_begripligt_fel(tmp_path):
    """UseTexts ger "Mora" utan kommunkod. Utan koden finns ingen nyckel mot
    resten av databasen, och felet ska säga vad som ska ändras."""
    with pytest.raises(ValueError, match="UseCodes"):
        las_befolkning_per_alder(_skriv(tmp_path, "klartext.csv", KLARTEXT))


def test_konen_summeras_nar_totalraden_saknas(tmp_path):
    """Långt format utan könstotal: delarna summeras i stället."""
    df = las_befolkning_per_alder(_skriv(tmp_path, "langt.csv", LANGT))
    rad = df[(df.municipal_code == "2062") & (df.age == 20)]
    assert len(rad) == 1
    assert int(rad["n_total"].iloc[0]) == 110 + 95
    assert int(df["year"].iloc[0]) == 2023


# ----------------------------------------------------------------------
# Dragningen
# ----------------------------------------------------------------------

class _Byggare:
    """ScenarioBuilder utan databasberoenden i övrigt."""
    def __init__(self, conn, simulation=None):
        self.conn = conn
        self.cfg_reader = FakeConfig(simulation or {})

    age_config = ScenarioBuilder.age_config
    alderspyramid = ScenarioBuilder.alderspyramid
    _skala_pyramid = staticmethod(ScenarioBuilder._skala_pyramid)
    dra_aldrar = ScenarioBuilder.dra_aldrar
    dra_tenure = ScenarioBuilder.dra_tenure


def _db(rader):
    conn = sqlite3.connect(":memory:")
    pd.DataFrame(rader).to_sql("population_by_age", conn, index=False)
    return conn


def _pyramid(kod="2062", year=2024, n_per_alder=100, aldrar=range(0, 101)):
    return [{"municipal_code": kod, "year": year, "age": a,
             "n_total": n_per_alder} for a in aldrar]


def test_skalningen_traffar_populationen_exakt():
    antal = np.array([3.0, 5.0, 2.0, 1.0])
    for pop in (10, 11, 97, 1000):
        ut = ScenarioBuilder._skala_pyramid(antal, pop)
        assert ut.sum() == pop
        assert (ut >= 0).all()


def test_arbetskraften_ligger_i_arbetsfor_alder():
    b = _Byggare(_db(_pyramid()))
    wf, ovriga = b.dra_aldrar("2062", 2024, 2000, 900, np.random.default_rng(1))
    assert len(wf) == 900 and len(wf) + len(ovriga) == 2000
    assert wf.min() >= 16 and wf.max() < 67


def test_de_tva_grupperna_ar_pyramiden():
    """Arbetskraften tar platser INOM pyramiden, den dras inte vid sidan av
    den: summan av de två grupperna per ålder ska vara pyramiden själv."""
    b = _Byggare(_db(_pyramid(n_per_alder=10)))
    wf, ovriga = b.dra_aldrar("2062", 2024, 1010, 400, np.random.default_rng(2))
    alla = np.concatenate([wf, ovriga])
    for a in range(0, 101):
        assert (alla == a).sum() == 10


def test_for_stor_arbetskraft_kastar():
    b = _Byggare(_db(_pyramid(n_per_alder=10)))
    with pytest.raises(ValueError, match="arbetsför ålder"):
        b.dra_aldrar("2062", 2024, 1010, 900, np.random.default_rng(3))


def test_saknad_kommun_kastar():
    b = _Byggare(_db(_pyramid(kod="2062")))
    with pytest.raises(ValueError, match="2034"):
        b.dra_aldrar("2034", 2024, 100, 50, np.random.default_rng(4))


def test_fallback_till_tidigare_ar():
    b = _Byggare(_db(_pyramid(year=2020)))
    aldrar, antal = b.alderspyramid("2062", 2024)
    assert antal.sum() == 101 * 100


def test_riktaldern_gar_att_stalla_om():
    b = _Byggare(_db(_pyramid()), simulation={"age": {"retirement_age": 65,
                                                      "work_age_min": 20}})
    wf, _ = b.dra_aldrar("2062", 2024, 2000, 500, np.random.default_rng(5))
    assert wf.min() >= 20 and wf.max() < 65


# ----------------------------------------------------------------------
# Tenure
# ----------------------------------------------------------------------

def test_tenure_overstiger_aldrig_arbetslivet():
    """Felet patchen rättar: tjugofemåringar med trettio års erfarenhet."""
    b = _Byggare(_db(_pyramid()),
                 simulation={"competence": {"initial_tenure_mean_years": 8.0}})
    alder = np.repeat(np.arange(16, 67, dtype=float), 40)
    niva = ["high"] * len(alder)
    entry, arbetsliv, tenure = b.dra_tenure(alder, niva, np.random.default_rng(6))
    assert (entry == 24.0).all()
    assert (arbetsliv == np.maximum(0.0, alder - 24.0)).all()
    assert (tenure <= arbetsliv + 1e-9).all()
    # Trunkeringen ska bita: med medel åtta år och tak noll till fyrtiotvå
    # hamnar en betydande andel exakt på taket.
    assert (np.isclose(tenure, arbetsliv)).mean() > 0.10


def test_intradesaldern_foljer_utbildningsnivan():
    b = _Byggare(_db(_pyramid()))
    alder = np.array([30.0, 30.0, 30.0, 30.0])
    entry, arbetsliv, _ = b.dra_tenure(
        alder, ["low", "medium", "high", None], np.random.default_rng(7))
    assert list(entry) == [19.0, 20.0, 24.0, 20.0]
    assert list(arbetsliv) == [11.0, 10.0, 6.0, 10.0]


# ----------------------------------------------------------------------
# Åldrande och pensionsavgång
# ----------------------------------------------------------------------

def _varld_med_individer(aldrar, statusar, simulation=None):
    """Minimal värld: en individ per ålder, de sysselsatta sitter på var sin
    position."""
    w = make_world(n_employers=len(aldrar) + 2, size=1, simulation=simulation)
    n = len(aldrar)
    w.individuals = pd.DataFrame({
        "individual_id": [f"i{k}" for k in range(n)],
        "status": list(statusar),
        "job_id": [None] * n,
        "age": np.asarray(aldrar, dtype=float),
        "next_search_time": np.full(n, 10.0),
        "w_res": np.full(n, 0.5),
        "x_occ": np.zeros(n), "y_occ": np.zeros(n), "r_i": np.zeros(n),
        "municipal_code": "2062",
    })
    jobb = w.jobs["job_id"].tolist()
    for k in range(n):
        if statusar[k] == "employed":
            jid = jobb[k]
            w.individuals.at[k, "job_id"] = jid
            pos = w.job_index().get(jid)
            w.jobs.iat[pos, w.jobs.columns.get_loc("individual_id")] = k
            w.set_job_filled(jid, True)
    w._active_key = np.full(n, -1, dtype=np.int64)
    w.refresh_ind()
    return w


def _arsskifte(w, t=365.25, year=2025):
    from core.event_handlers import _aldras_och_pensioneras
    return _aldras_och_pensioneras(
        w, {"time": t, "agent_id": None, "event_type": "new_year",
            "params": {"year": year}})


def test_alla_fyller_ar():
    w = _varld_med_individer([30.0, 45.0], ["unemployed", "employed"])
    _arsskifte(w)
    assert list(w.individuals["age"]) == [31.0, 46.0]


def test_startarets_arsskifte_aldrar_ingen():
    """new_year ligger också på t = 0. Utan undantaget hade befolkningen
    åldrats ett år innan första dagen simulerats."""
    w = _varld_med_individer([66.0], ["employed"])
    ut = _arsskifte(w, t=0.0, year=2024)
    assert ut == {}
    assert list(w.individuals["age"]) == [66.0]
    assert w.individuals.at[0, "status"] == "employed"


def test_riktaldern_lamnar_arbetskraften():
    w = _varld_med_individer([66.0, 65.0], ["employed", "unemployed"])
    ut = _arsskifte(w)
    assert ut["retired"] == 1 and ut["retired_from_job"] == 1
    assert w.individuals.at[0, "status"] == "not_in_labor_force"
    assert w.individuals.at[1, "status"] == "unemployed"


def test_positionen_blir_vakant_inte_forstord():
    """Ersättningsrekryteringen: arbetsgivaren har kvar positionen."""
    w = _varld_med_individer([66.0], ["employed"])
    jid = w.individuals.at[0, "job_id"]
    _arsskifte(w, t=365.25)
    pos = w.job_index()[jid]
    assert bool(w.jobs.iat[pos, w.jobs.columns.get_loc("active")]) is True
    assert pd.isna(w.jobs.iat[pos, w.jobs.columns.get_loc("individual_id")])
    assert w.jobs.iat[pos, w.jobs.columns.get_loc("vacant_since")] == 365.25
    assert pd.isna(w.individuals.at[0, "job_id"])


def test_sokkedjan_bryts():
    """En redan schemalagd sökning ska förfalla: handle_start_job_search
    kastar den när due inte längre är hennes next_search_time."""
    w = _varld_med_individer([66.0], ["unemployed"])
    _arsskifte(w)
    assert pd.isna(w.individuals.at[0, "next_search_time"])


def test_arbetslos_pensionar_raknas_inte_som_arbetslos():
    """Bokföringen: den som går i pension lämnar arbetskraften, hon blir inte
    kvar som arbetslös."""
    w = _varld_med_individer([66.0, 66.0, 40.0],
                             ["unemployed", "employed", "unemployed"])
    ut = _arsskifte(w)
    assert ut["retired"] == 2 and ut["retired_from_job"] == 1
    assert (w.individuals["status"] == "not_in_labor_force").sum() == 2
    assert (w.individuals["status"] == "unemployed").sum() == 1


def test_manadsskiftet_gar_igenom_efter_arsskifte():
    """Rökprov över händelsegränsen: månadsskiftet verifierar kolumnvyerna mot
    tabellen, och åldrandet skriver en hel kolumn strax innan.

    Testet faller INTE om refresh_ind() tas bort ur _aldras_och_pensioneras --
    blockbytet gick inte att framkalla för just den skrivningen. Det prövar
    alltså att de två händelserna fungerar efter varandra, inget mer."""
    from core.event_handlers import handle_new_month
    w = _varld_med_individer([66.0, 40.0], ["employed", "employed"])
    w.individuals["w_neg"] = 1.0
    w.refresh_ind()
    _arsskifte(w, t=365.25)
    handle_new_month({"time": 396.0, "agent_id": None, "event_type": "new_month",
                      "params": {"year": 2025, "month": 2}}, w)
    assert list(w.individuals["age"]) == [67.0, 41.0]
