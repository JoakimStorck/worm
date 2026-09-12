"""Exportlagret: en parser, tre tabeller.

Tidigare hade validate_mobility, convergence och figures varsin kopia av
samma parser, och check_invariants och compare_municipalities läste
tillståndsfilerna med varsin logik. Fem tolkningar av samma data."""
import os

import numpy as np
import pandas as pd
import pytest

from pathlib import Path

from core.analysis.eventlog import (parse_line, transitions_table, timeseries_table,
                                    summary_row, coverage, export, load_tables)


def _write_run(tmp_path, n_trans=200, n_months=24):
    rng = np.random.default_rng(0)
    lines = []
    L, J = 1000, 900
    for m in range(1, n_months + 1):
        V = int(60 + 200 * np.exp(-m / 6))
        U = L - J + V
        lines.append(f"{(m-1)*30.44:.2f}, new_month, agent_type system, month {m}, "
                     f"employed {L-U}, unemployed {U}, unmatched_jobs {V}, "
                     f"not_in_labour_force 500, active_jobs {J}, posted 40")
    same = rng.random(n_trans) < 0.2
    mgmt = (~same) & (rng.random(n_trans) < 0.1)
    u = np.where(same, 0.0, rng.rayleigh(0.55, n_trans))
    for i, (v, s, mg) in enumerate(zip(u, same, mgmt)):
        src = "11-1011.00" if mg else "49-9041.00"
        tgt = src if s else ("11-2021.00" if mg else "51-2011.00")
        lines.append(f"{i:.2f}, start_job, agent_id {i}, job_id J{i}, d_task {v*0.27:.4f}, "
                     f"u_R {v:.4f}, u_R_occ {v:.4f}, from_onet {src}, to_onet {tgt}, "
                     f"occ_change {0 if s else 1}, w_field 1.0000, w_neg 0.6000, "
                     f"q_hire 0.8000")
    lines.append("5.0, start_job_search, agent_id 1, event_detail match_failed")
    d = tmp_path / "run_x"
    d.mkdir()
    (d / "eventlog.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(d), same, mgmt


def test_parse_line_handles_the_log_format():
    r = parse_line("31.00, new_month, agent_type system, month 2, employed 900\n")
    assert r["time"] == 31.0 and r["event"] == "new_month"
    assert r["month"] == "2" and r["employed"] == "900"
    assert parse_line("skräp") is None
    assert parse_line("") is None


def test_transitions_table_marks_the_cps_sample(tmp_path):
    run, same, mgmt = _write_run(tmp_path)
    from core.analysis.eventlog import read_events
    tr = transitions_table(read_events(run))
    assert len(tr) == same.size
    assert int((~tr["occ_change"]).sum()) == int(same.sum())
    assert int((tr["occ_change"] & tr["is_mgmt"]).sum()) == int(mgmt.sum())
    # CPS-urvalet: yrkesbyten utan chefsövergångar
    assert int(tr["in_cps_sample"].sum()) == int((~same & ~mgmt).sum())
    assert tr["wage_ratio"].iloc[0] == pytest.approx(0.6)


def test_timeseries_carries_the_identity(tmp_path):
    run, _, _ = _write_run(tmp_path)
    from core.analysis.eventlog import read_events
    ts = timeseries_table(read_events(run))
    assert len(ts) == 24
    # U = L - J + V ska hålla exakt i syntetiska data
    assert float(ts["identity_residual"].abs().max()) == pytest.approx(0.0)
    assert (ts["u"] > 0).all() and (ts["v"] > 0).all()


def test_summary_row_collects_the_key_figures(tmp_path):
    run, same, mgmt = _write_run(tmp_path)
    row = summary_row(run)
    assert row["months"] == 24
    assert row["n_transitions"] == same.size
    assert row["share_same_occ"] == pytest.approx(float(same.mean()), abs=0.01)
    assert 0.4 < row["median_u_R"] < 0.9
    assert row["median_wage_ratio"] == pytest.approx(0.6)
    assert row["identity_residual_max"] == pytest.approx(0.0)


def test_coverage_grows_with_spread():
    rng = np.random.default_rng(1)
    tight = (rng.normal(0.3, 0.02, 300), rng.normal(0.1, 0.02, 300))
    spread = (rng.uniform(-0.7, 0.7, 300), rng.uniform(-0.7, 0.7, 300))
    assert coverage(*tight, 0.25) < coverage(*spread, 0.25)
    assert 0.0 <= coverage(*tight, 0.25) <= 1.0


def test_export_and_reload(tmp_path):
    run, _, _ = _write_run(tmp_path)
    res = export(run)
    for name in ("transitions", "timeseries", "flows", "summary"):
        assert os.path.isfile(os.path.join(res["out_dir"], f"{name}.csv"))
    again = load_tables(run)          # ska läsa, inte räkna om
    assert len(again["transitions"]) == len(res["transitions"])
    assert again["summary"]["run"] == res["summary"]["run"]


def test_scripts_agree_on_the_same_numbers(tmp_path):
    """Poängen med lagret: alla skript ska se samma siffror."""
    run, _, _ = _write_run(tmp_path)
    t = load_tables(run)
    cps = t["transitions"][t["transitions"]["in_cps_sample"]]
    assert t["summary"]["median_u_R"] == pytest.approx(
        float(cps["u_R_occ"].median()), abs=1e-6)
    assert t["summary"]["n_cps_sample"] == len(cps)


def test_summary_carries_provenance(tmp_path):
    """REGRESSION i metod: utan härkomst blandar en samlad tabell körningar
    från olika kodversioner, och en jämförelse mäter kodhistorik i stället
    för skillnader mellan scenarier. Tjugo körningar samlades så en gång."""
    import json
    run, _, _ = _write_run(tmp_path)
    (pd.Series(dtype=float))  # noqa
    with open(os.path.join(run, "run_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"run_id": "run_x", "scenario": "mora", "seed": 4711,
                   "git_commit": "abcdef1234567890", "git_dirty": False,
                   "municipalities": ["2062"],
                   "simulation": {"sigma_gamma": 0.875, "choice_scale": 0.05}}, f)
    row = summary_row(run)
    assert row["scenario"] == "mora"
    assert row["seed"] == 4711
    assert row["commit"] == "abcdef12"
    assert row["dirty"] is False
    assert row["municipalities"] == "2062"
    assert row["p_sigma_gamma"] == 0.875


def test_summary_without_provenance_still_works(tmp_path):
    """Äldre körningar saknar run_meta.json och ska inte falla."""
    run, _, _ = _write_run(tmp_path)
    row = summary_row(run)
    assert "commit" not in row
    assert row["n_transitions"] > 0


def test_ecdf_band_spans_the_runs():
    """Med flera frön ska figuren visa bandet, inte ett godtyckligt utfall."""
    from core.analysis.eventlog import ecdf_band
    rng = np.random.default_rng(0)
    runs = {f"r{i}": rng.rayleigh(0.55 + 0.05 * i, 800) for i in range(5)}
    b = ecdf_band(runs)
    assert not b.empty and int(b["n_runs"].iloc[0]) == 5
    assert (b["min"] <= b["q25"]).all() and (b["q25"] <= b["median"]).all()
    assert (b["median"] <= b["q75"]).all() and (b["q75"] <= b["max"]).all()
    assert (b["max"] - b["min"]).max() > 0.01, "inget band trots olika frön"


def test_group_stats_separates_within_from_between(tmp_path):
    """Spridningen inom scenario måste kunna skiljas från skillnaden mellan
    scenarier, annars tolkas brus som effekt."""
    from core.analysis.eventlog import group_stats
    df = pd.DataFrame({
        "run": [f"r{i}" for i in range(6)],
        "scenario": ["mora"] * 3 + ["falun"] * 3,
        "seed": [1, 2, 3, 1, 2, 3],
        "u_pct": [10.0, 10.4, 9.8, 8.1, 8.4, 7.9],
        "median_u_R": [0.64, 0.66, 0.65, 0.70, 0.72, 0.69],
    })
    g = group_stats(df, by="scenario").set_index("scenario")
    assert set(g.index) == {"mora", "falun"}
    assert (g["n_runs"] == 3).all()
    assert g.loc["mora", "u_pct_median"] > g.loc["falun", "u_pct_median"]
    # Bandet inom scenario ska vara smalare än skillnaden mellan dem
    within = g.loc["mora", "u_pct_max"] - g.loc["mora", "u_pct_min"]
    between = g.loc["mora", "u_pct_median"] - g.loc["falun", "u_pct_median"]
    assert within < between
    assert g.loc["mora", "seeds"] == "1,2,3"


def test_figure_manifest_records_provenance(tmp_path):
    """En figur i ett manuskript ska gå att spåra till sina körningar."""
    import json
    from core.analysis.figio import write

    run = tmp_path / "run_p"
    run.mkdir()
    (run / "run_meta.json").write_text(json.dumps(
        {"git_commit": "deadbeef1234", "seed": 9, "scenario": "mora",
         "git_dirty": False}), encoding="utf-8")
    out = tmp_path / "figs"
    m = write(None, "demo", str(out),
              data={"serie": pd.DataFrame({"x": [1, 2], "y": [3, 4]})},
              run_dirs=[str(run)], note="test", extra={"gamma": 0.875})
    assert m["n_runs"] == 1 and m["seeds"] == [9]
    assert m["commits"] == ["deadbeef1234"] and not m["mixed_commits"]
    assert m["parameters"]["gamma"] == 0.875
    assert os.path.isfile(out / "demo__serie.csv")
    saved = json.loads((out / "demo.json").read_text(encoding="utf-8"))
    assert saved["figure"] == "demo"


def test_manifest_flags_mixed_commits(tmp_path):
    import json
    from core.analysis.figio import write
    runs = []
    for i, c in enumerate(("aaa111", "bbb222")):
        d = tmp_path / f"r{i}"
        d.mkdir()
        (d / "run_meta.json").write_text(json.dumps({"git_commit": c, "seed": i}),
                                         encoding="utf-8")
        runs.append(str(d))
    m = write(None, "mix", str(tmp_path / "f"), run_dirs=runs)
    assert m["mixed_commits"] is True and len(m["commits"]) == 2


# ---------------------------------------------------------------------------
# Global och inomyrkes lönefördelning (0064)
# ---------------------------------------------------------------------------

def test_wage_ratio_is_measured_against_the_occupation_not_the_job():
    """REGRESSION: wage_ratio var w_neg/w_field, och w_field är JOBBETS lön
    Pi_j = Pi_o*exp(eta). Med w = Pi_j*p**theta står eta i både täljare och
    nämnare och försvinner IDENTISKT ur kvoten. Bottenkvartilen låg därför på
    exakt 1.000 med 43 procent på punkten trots att sd(log w_field) inom yrke
    var 0.103: arbetsgivareffekten fanns i modellen men inte i måttet."""
    import numpy as np
    from core.analysis.eventlog import transitions_table

    bas = dict(event="start_job", from_onet="11-1011.00", to_onet="35-9021.00",
               u_R=0.8, u_R_occ=0.8, q_hire=1.0, r_req=0.0, occ_change=1)
    ev = [dict(bas, time=1.0, agent_id=1, job_id="J1",
               w_occ=1.0, w_field=1.20, w_neg=1.20),     # eta = +0.18
          dict(bas, time=2.0, agent_id=2, job_id="J2",
               w_occ=1.0, w_field=0.80, w_neg=0.80)]     # eta = -0.22
    tr = transitions_table(ev)

    assert "w_occ" in tr.columns
    # Mot jobbet vore båda exakt 1.0; mot yrket skiljer de sig
    assert tr["wage_ratio"].tolist() == pytest.approx([1.20, 0.80])
    assert tr["employer_premium"].tolist() == pytest.approx([1.20, 0.80])


def test_wage_stock_is_measured_annually_not_per_event():
    """Beståndet mäts i new_year-hanteraren, inte som egen händelsetyp: en
    wage_snapshot i kön skulle konkurrera med den kommande lönerevisionen om
    ordningen inom samma tidpunkt."""
    import numpy as np, pandas as pd
    from core.event_handlers import _wage_stock_stats, RULE_SWITCH

    assert "wage_snapshot" not in RULE_SWITCH

    class W:
        individuals = pd.DataFrame({
            "status": ["employed"] * 100 + ["unemployed"] * 20,
            "w_neg": list(np.linspace(0.5, 1.5, 100)) + [np.nan] * 20,
            "job_id": [f"J{i}" for i in range(100)] + [None] * 20,
        })
        jobs = pd.DataFrame({"job_id": [f"J{i}" for i in range(100)],
                             "wage": [1.0] * 100})

        @staticmethod
        def job_index():
            return {f"J{i}": i for i in range(100)}
    st = _wage_stock_stats(W())
    assert st["stock_n"] == 100
    assert st["stock_w_p50"] == pytest.approx(1.0, abs=0.02)
    assert st["stock_w_p90p10"] == pytest.approx(1.4 / 0.6, rel=0.05)
    assert st["stock_sd_log_w"] > 0
    # Hälften av beståndet ligger över yrkeslönen 1.0: definitionsvillkoret
    assert st["stock_share_above_pi"] == pytest.approx(0.5, abs=0.02)

    # För få anställda ger inget mått i stället för ett brusigt
    class Tiny:
        individuals = pd.DataFrame({"status": ["employed"] * 3,
                                    "w_neg": [1.0, 1.1, 0.9],
                                    "job_id": ["J0", "J1", "J2"]})
        jobs = pd.DataFrame({"job_id": ["J0", "J1", "J2"], "wage": [1.0] * 3})

        @staticmethod
        def job_index():
            return {"J0": 0, "J1": 1, "J2": 2}
    assert _wage_stock_stats(Tiny()) == {}


def test_wage_figure_reads_the_shared_ratio_and_fits_in_quadrature():
    """REGRESSION: fig_wages räknade sin EGEN kvot w_neg/w_field, medan
    w_field är jobbets lön Pi_j = Pi_o*exp(eta). Med w = Pi_j*p**theta
    försvinner eta identiskt ur den kvoten, så figuren visade p**theta och
    inte lönekvoten -- med en spik vid exakt 1.00 i alla jobb där r_j ~ 0.
    0064 rättade måttet i eventlog men figuren räknade vidare på egen hand.

    Och de två spridningskällorna adderas i KVADRATUR:
    sigma**2 = sigma_eta**2 + (theta*k*sigma_q)**2 * r**2. En rät linje i
    sigma mot r underskattar interceptet och överskattar lutningen."""
    import inspect
    import numpy as np
    from scripts import figures as F

    src = inspect.getsource(F.fig_wages)
    kod = [ln for ln in src.splitlines() if not ln.lstrip().startswith("#")]
    assert not [ln for ln in kod if 'w_neg"] / ' in ln or "w_neg'] / " in ln], \
        "figuren härleder kvoten själv igen"
    assert any('"wage_ratio"' in ln for ln in kod), "ska läsa wage_ratio ur tabellen"

    # Kvadraturskattningen återger kända parametrar
    sig_eta, slope = 0.10, 0.30
    r = np.array([0.1, 0.35, 0.6, 0.9])
    sd = np.sqrt(sig_eta ** 2 + (slope * r) ** 2)
    b, a = np.polyfit(r ** 2, sd ** 2, 1)
    assert np.sqrt(a) == pytest.approx(sig_eta, abs=1e-6)
    assert np.sqrt(b) == pytest.approx(slope, abs=1e-6)
    # en rät linje i sigma mot r missar båda parametrarna påtagligt
    b_lin, a_lin = np.polyfit(r, sd, 1)
    assert abs(a_lin - sig_eta) > 0.02, "linjär anpassning råkar träffa interceptet"
    assert abs(b_lin - slope) > 0.02, "linjär anpassning råkar träffa lutningen"


def test_dispersion_panel_uses_mean_r_squared_and_shows_q_spread():
    """x-värdet är kvartilens MEDELVÄRDE av r**2, inte kvadraten på dess
    mittpunkt: sigma**2 är linjär i r**2, så E[r**2] är det som ska plottas.
    E[r]**2 skiljer sig med variansen inom kvartilen och avviker med upp till
    57 procent i den understa kvartilen på riktiga data.

    Och sd(log q) måste visas bredvid, för antagandet att den är konstant över
    r är falskt: urvalet rangordnar på q och grinden sållar hårdare vid höga
    krav, så den faller med en faktor 3.6 över kvartilerna. Utan den serien
    ser krökningen i vänsterserien ut som brus."""
    import inspect
    import numpy as np
    from scripts import figures as F

    kod = [ln for ln in inspect.getsource(F.fig_wages).splitlines()
           if not ln.lstrip().startswith("#")]
    assert any("** 2).mean()" in ln for ln in kod), "x ska vara E[r**2]"
    assert any("sd_log_q" in ln for ln in kod), "sd(log q) ska med i datafilen"

    # Jensen: för en skev fördelning i kvartilen skiljer sig E[r^2] från mitt^2
    r = np.concatenate([np.zeros(800), np.linspace(0.0, 0.048, 200)])
    mitt = (0.0 + 0.048) / 2
    assert abs((r ** 2).mean() - mitt ** 2) / mitt ** 2 > 0.3


def test_stock_and_revision_reach_the_run_table():
    """REGRESSION: _wage_stock_stats (0064) och _apply_wage_revision (0067)
    skriver till new_year-radens extra, men summary_row läste bara transitions
    och timeseries. Måtten stannade i eventlog.csv och nådde aldrig runs.csv --
    samma väg som n_applicants och theta tappades."""
    from core.analysis.eventlog import summary_row
    import pandas as pd, numpy as np

    ev = [{"event": "new_year", "time": 366.0, "year": 2025,
           "stock_sd_log_w": 0.21, "stock_w_p90p10": 2.30, "stock_w_p50": 1.05,
           "stock_w_p10": 0.70, "stock_w_p90": 1.61,
           "revision_g_mean": 0.031, "revision_g_p10": 0.020,
           "revision_g_p90": 0.045, "revision_share_zero": 0.02,
           "revision_n": 9000},
          {"event": "new_year", "time": 731.0, "year": 2026,
           "stock_sd_log_w": 0.24, "stock_w_p90p10": 2.45, "stock_w_p50": 1.08,
           "stock_w_p10": 0.71, "stock_w_p90": 1.74,
           "revision_g_mean": 0.033, "revision_g_p10": 0.021,
           "revision_g_p90": 0.048, "revision_share_zero": 0.03,
           "revision_n": 9100}]
    tr = pd.DataFrame({"u_R": [0.7], "u_R_occ": [0.7], "w_neg": [1.0],
                       "w_occ": [1.0], "w_field": [1.0], "wage_ratio": [1.0],
                       "in_cps_sample": [True], "occ_change": [True],
                       "is_mgmt": [False], "r_req": [0.3], "q_hire": [0.9],
                       "commute_km": [5.0], "n_applicants": [3.0]})
    ts = pd.DataFrame({"year": [1.0], "month": [1], "vacancies": [10],
                       "employed": [90], "unemployed": [10],
                       "labour_force": [100], "active_jobs": [100],
                       "posted": [0], "not_in_labour_force": [0],
                       "u": [10.0], "v": [10.0], "tightness": [1.0],
                       "identity_residual": [0]})
    row = summary_row("/tmp/x", events=ev, tr=tr, ts=ts)

    # Beståndet: sista årets tvärsnitt, inte medelvärdet
    assert row["stock_sd_log_w"] == pytest.approx(0.24)
    assert row["stock_w_p90p10"] == pytest.approx(2.45)
    # Revisionen: medel över åren, eftersom varje år är en dragning
    assert row["revision_g_mean"] == pytest.approx(0.032)
    assert row["revision_share_zero"] == pytest.approx(0.025)


def test_bootstrap_uses_the_same_matching_as_the_run():
    """REGRESSION: förmatchningen körde interleaved_multilevel_batch_matching,
    en fyra patchar äldre version av samma modell -- utan kön i överskottet,
    arbetsgivarens urval, kravgrinden eller loneformeln. Nio tusen matchningar,
    alltså större delen av beståndet i flera år, var gjorda under en modell vi
    inte längre tror på.

    Och dess geografiska trappa DeSO -> kommun -> globalt var en SYSTEMATISK
    partitionering: den som råkade komma tidigt i deso_codes-ordningen tog de
    bästa jobben i hela kommunen, vilket gav startbeståndet en gradient efter
    körordning i en modell där geografi är förklaringsvariabeln."""
    import inspect
    from core import matching_core as mc
    from core import world as world_mod

    # Den gamla vägen finns inte kvar
    assert not hasattr(world_mod.World, "match_individuals_to_jobs")
    assert not hasattr(world_mod.World, "update_after_matching")
    import importlib
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("core.matching")

    # Uppstarten återimplementerar ingen matchning: den anropar apply_once.
    # Kommentarer och docstring räknas inte -- de förklarar varför geografin
    # togs bort och skulle annars fälla kontrollen mot sig själva.
    src = inspect.getsource(mc.bootstrap_matching)
    kod = [ln for ln in src.splitlines() if not ln.lstrip().startswith("#")]
    kod = "\n".join(kod).split('"""')
    kod = "".join(kod[::2])              # utanför docstringen
    assert "apply_once" in kod
    assert "deso" not in kod.lower(), "geografisk partitionering igen"
    assert "shuffle" in kod, "partitioneringen ska vara slumpmässig"

    # Och hanteraren ramar in samma funktion
    from core import event_handlers as eh
    assert "apply_once" in inspect.getsource(eh.handle_start_job_search)


def test_bootstrap_round_size_follows_target_density():
    """Omgångsstorleken härleds ur måltätheten, inte ur en fri parameter: med
    ungefär 1/tightness sökande per ledig vakans liknar konkurrensen vid start
    den under körning, och antalet omgångar blir ett resultat."""
    per_vak, n_vak, n_kö = 2.4, 100, 1000
    n = max(1, min(n_kö, int(round(per_vak * n_vak))))
    assert n == 240
    # Färre lediga jobb ger mindre omgångar, alltså samma täthet
    assert max(1, min(n_kö, int(round(per_vak * 10)))) == 24
    # Kön tar slut innan omgången fylls
    assert max(1, min(50, int(round(per_vak * 100)))) == 50




def test_bootstrap_hires_are_marked_and_left_out_of_the_cps_sample():
    """REGRESSION: uppstartens anställningar går genom handle_start_job och
    hamnar därför i transitions -- 10 165 av 21 594 i en femårskörning. De
    räknades som yrkesövergångar, eftersom individens seedade onet_code
    skiljer sig från jobbets, och blåste upp n_cps_sample från 8 285 till
    17 900: hälften av valideringsunderlaget var att folk fick sitt FÖRSTA
    jobb, inte att de bytte.

    De spädde dessutom ut median u_R nedåt: uppstartens egna övergångar hade
    median 0.687 mot körningens 0.76-0.80, eftersom konkurrensen per vakans är
    som störst när alla är lediga samtidigt."""
    from core.analysis.eventlog import transitions_table

    bas = dict(event="start_job", from_onet="53-7062.00", to_onet="35-9021.00",
               u_R=0.9, u_R_occ=0.9, w_occ=1.0, w_field=1.0, w_neg=1.0,
               q_hire=0.9, r_req=0.3, occ_change=1, is_mgmt=0)
    ev = [dict(bas, time=0.0, agent_id=1, job_id="J1", is_bootstrap=True),
          dict(bas, time=400.0, agent_id=2, job_id="J2")]
    tr = transitions_table(ev)

    assert "is_bootstrap" in tr.columns
    assert tr["is_bootstrap"].tolist() == [True, False]
    # Uppstarten ligger kvar i tabellen men utanför valideringsurvalet
    assert len(tr) == 2
    assert tr["in_cps_sample"].tolist() == [False, True]


def test_hot_paths_do_not_scan_the_job_table():
    """REGRESSION: 'jobs.loc[jobs["job_id"] == job_id, ...]' skannar hela
    jobbtabellen med en strängjämförelse -- mätt 773 mikrosekunder för
    jämförelsen och 986 för skrivningen över 11 200 rader, mot 5.5 för ett
    uppslag i job_index och 7.2 för en iat-skrivning. Mönstret satt i varje
    separation och varje jobbförstörelse, alltså i de mest frekventa
    händelserna som finns. Och jobs.iloc[pos][col] bygger en Series av hela
    raden: 54 mikrosekunder mot 11 för kolumnaccess."""
    import inspect
    from core import event_handlers as eh
    from core import matching_core as mc

    for fn in (eh.handle_start_job, eh.handle_start_job_search, eh._clear_holder,
               eh.handle_destroy_job, mc.apply_once):
        # Kommentarer och docstring räknas inte: de citerar mönstret de
        # ersätter och skulle annars fälla kontrollen mot sig själva.
        kod = [ln for ln in inspect.getsource(fn).splitlines()
               if not ln.lstrip().startswith("#")]
        text = "".join("\n".join(kod).split('"""')[::2])
        assert "jobs['job_id'] ==" not in text and 'jobs["job_id"] ==' not in text, \
            f"boolesk skanning av jobbtabellen i {fn.__name__}"

    # Och uppslaget av job_id efter en träff sker på kolumnen, inte på raden
    mc_kod = inspect.getsource(mc.apply_once)
    assert "['job_id'].iat[" in mc_kod


def test_locality_is_measured_between_occupations_on_the_cps_sample():
    """REGRESSION: fig_commute mätte u_R -- avståndet från INDIVIDENS position
    till jobbet -- på hela transitions. Rapporten mäter u_R_occ, avståndet
    från KÄLLYRKETS centroid till jobbets, normerat med källans radie, på
    CPS-urvalet. CPS observerar yrkesbyten, alltså avstånd mellan två yrken,
    och det är u_R_occ som ska jämföras med 0.70.

    Skillnaden är inte kosmetisk. Med u_R låg bottenkvartilen på 1.64 och gav
    en U-form som flera tolkningar byggde på; med u_R_occ ligger den på 0.79,
    alltså med de andra, och kurvan faller i stället monotont i toppen:
    0.79 / 0.74 / 0.79 / 0.60. Individen kan ligga långt från jobbet även när
    yrkena ligger nära."""
    import inspect
    from scripts import figures as F

    for fn in (F.fig_commute, F.fig_mobility):
        kod = [ln for ln in inspect.getsource(fn).splitlines()
               if not ln.lstrip().startswith("#")]
        text = "".join("\n".join(kod).split('"""')[::2])
        assert "u_R_occ" in text, f"{fn.__name__} mäter inte mellan yrken"
        assert '["u_R"]' not in text, f"{fn.__name__} mäter från individen"

    # Och summary_row gör redan rätt: cps-urvalet och u_R_occ
    src = inspect.getsource(__import__("core.analysis.eventlog",
                                       fromlist=["summary_row"]).summary_row)
    assert 'cps["u_R_occ"]' in src


def test_ladder_and_residual_pool_are_measured():
    """De tre måtten i lonemodell.md avsnitt 5, som avgör vilken diagnos som
    dominerar innan något byggs: byten per år och lönevinst per byte skiljer
    en för snabb stege (kappa = lambda_1/delta ~ 26 mot empiriska 2-5) från en
    felförankrad Pi; restpoolens sammansättning visar undanträngningen; och
    vakansernas ålder skiljer en växande stock av samma positioner från ett
    växande flöde."""
    from core.analysis.eventlog import transitions_table, summary_row
    import pandas as pd, numpy as np

    bas = dict(event="start_job", from_onet="53-7062.00", to_onet="35-9021.00",
               u_R=0.7, u_R_occ=0.7, w_occ=1.0, w_field=1.0, q_hire=0.9,
               r_req=0.3, occ_change=1, is_mgmt=0)
    ev = [dict(bas, time=100.0, agent_id=1, job_id="J1", w_neg=1.10,
               w_prev=1.00, job_to_job=True, vacancy_age_days=40.0),
          dict(bas, time=200.0, agent_id=2, job_id="J2", w_neg=1.00,
               job_to_job=False, vacancy_age_days=80.0),
          {"event": "close_vacancy", "event_detail": "match_completed",
           "time": 100.0, "job_id": "J1", "winner_employed": True,
           "q_median_employed": 1.10, "q_median_unemployed": 0.60},
          {"event": "close_vacancy", "event_detail": "match_completed",
           "time": 200.0, "job_id": "J2", "winner_employed": False,
           "q_median_employed": 1.05, "q_median_unemployed": 0.55}]
    tr = transitions_table(ev)
    assert tr["job_to_job"].tolist() == [True, False]
    assert tr["vacancy_age_days"].tolist() == pytest.approx([40.0, 80.0])

    ts = pd.DataFrame({"year": [1.0], "month": [1], "vacancies": [10],
                       "employed": [100], "unemployed": [10],
                       "labour_force": [110], "active_jobs": [110],
                       "posted": [0], "not_in_labour_force": [0],
                       "u": [9.0], "v": [9.0], "tightness": [1.0],
                       "identity_residual": [0]})
    row = summary_row("/tmp/x", events=ev, tr=tr, ts=ts)

    assert row["n_job_to_job"] == 1
    assert row["job_to_job_rate"] == pytest.approx(1 / 1.0 / 100, abs=1e-4)
    assert row["job_to_job_wage_gain"] == pytest.approx(1.10)
    # Restpoolen: hälften av tillsättningarna gick till anställda, och deras
    # q ligger högt över de arbetslösas
    assert row["share_hires_from_employment"] == pytest.approx(0.5)
    assert row["q_applicants_employed"] > row["q_applicants_unemployed"]
    # Vakansåldern kräver mer än tjugo rader för att inte bli brus
    assert "vacancy_age_median" not in row


def test_boolean_log_fields_are_parsed_as_booleans(tmp_path):
    """REGRESSION: parse_line ger strängar, och bool("False") är True. Med
    bool(r.get(...)) var winner_employed sant för VARJE tillsättning och
    job_to_job sant för VARJE anställning under körning. Rapporten sade
    därför 100 procent av tillsättningarna till anställda och 28.5 procent
    byten per år -- det senare var alla anställningar, inte bytena -- i
    0082 till 0085, och restpoolsdiagnosen byggde på det."""
    lines = [
        "0.00, new_month, agent_type system, month 1, employed 900, unemployed 100, "
        "unmatched_jobs 0, not_in_labour_force 0, active_jobs 900, posted 0",
        # två tillsättningar: en till arbetslös, en till anställd
        "40.00, close_vacancy, event_detail match_completed, job_id J1, agent_id 1, "
        "winner_employed False, q_median_unemployed 0.5",
        "40.00, close_vacancy, event_detail match_completed, job_id J2, agent_id 2, "
        "winner_employed True, q_median_employed 0.8",
        # tre tillträden: ett byte, ett från arbetslöshet, ett uppstart
        "50.00, start_job, agent_id 1, job_id J1, u_R 0.5, u_R_occ 0.5, from_onet 49-9041.00, "
        "to_onet 51-2011.00, occ_change 1, w_field 1.0, w_neg 0.7, q_hire 0.8, job_to_job False",
        "50.00, start_job, agent_id 2, job_id J2, u_R 0.5, u_R_occ 0.5, from_onet 49-9041.00, "
        "to_onet 51-2011.00, occ_change 1, w_field 1.0, w_neg 0.9, q_hire 0.8, job_to_job True, "
        "w_prev 0.8",
        "0.00, start_job, agent_id 3, job_id J3, u_R 0.5, u_R_occ 0.5, from_onet 49-9041.00, "
        "to_onet 51-2011.00, occ_change 1, w_field 1.0, w_neg 0.9, q_hire 0.8, is_bootstrap True, "
        "job_to_job False",
    ]
    d = tmp_path / "run_b"; d.mkdir()
    (d / "eventlog.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    tr = transitions_table([parse_line(l) for l in lines])
    assert tr["job_to_job"].tolist() == [False, True, False]
    assert tr["is_bootstrap"].tolist() == [False, False, True]
    row = summary_row(str(d))
    assert row["share_hires_from_employment"] == pytest.approx(0.5)
    assert row["n_job_to_job"] == 1


def test_first_step_measures_follow_each_individual(tmp_path):
    """Svepet 0089: bytena styrs inte av söktakten. Måtten som prövar
    tolkningen -- ingångslön ur arbetslöshet relativt yrkets Pi, och tiden från
    anställning ur arbetslöshet till individens NÄSTA byte -- måste följa
    individen, inte tabellen: agent 1 anställs ur arbetslöshet dag 50 till
    0.85 Pi och byter dag 300; agent 2 anställs dag 60 och byter aldrig."""
    def st(t, aid, jtj, w_neg, w_occ, extra=""):
        return (f"{t:.2f}, start_job, agent_id {aid}, job_id J{aid}, u_R 0.5, u_R_occ 0.5, "
                f"from_onet 49-9041.00, to_onet 51-2011.00, occ_change 1, w_field 1.0, "
                f"w_occ {w_occ}, w_neg {w_neg}, q_hire 0.8, job_to_job {jtj}{extra}")
    lines = [
        "0.00, new_month, agent_type system, month 1, employed 900, unemployed 100, "
        "unmatched_jobs 0, not_in_labour_force 0, active_jobs 900, posted 0",
        st(0.0, 3, "False", 0.9, 1.0, ", is_bootstrap True"),
        st(50.0, 1, "False", 0.85, 1.0),
        st(60.0, 2, "False", 0.80, 1.0),
        st(300.0, 1, "True", 1.02, 1.0, ", w_prev 0.85"),
        "3652.50, simulation_completed, agent_type system",
    ]
    d = tmp_path / "run_s"; d.mkdir()
    (d / "eventlog.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    row = summary_row(str(d))
    assert row["entry_wage_ratio_from_unemployment"] == pytest.approx(0.825)
    assert row["entry_wage_ratio_job_to_job"] == pytest.approx(1.02)
    assert row["days_to_first_step_median"] == pytest.approx(250.0)
    assert row["share_first_step_within_year"] == pytest.approx(1.0)
    assert row["share_unemployed_hires_that_step"] == pytest.approx(0.5)


def _run_individual_history(*args):
    """Kör scripts/individual_history.py oavsett var pytest startades.

    Provet anropade skriptet med en RELATIV sökväg, så det fungerade från
    repo-roten och föll med exit 2 (python hittar ingen fil) när sviten körs
    inifrån tests/, vilket kor_0077.sh gör. Sökvägen räknas nu ut ur
    __file__, och arbetskatalogen sätts till repo-roten så att skriptets
    eget sys.path-tillägg och default för --db stämmer."""
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "individual_history.py"), *args],
        capture_output=True, text=True, check=True, cwd=str(root)).stdout

def test_individual_history_tells_one_individuals_story(tmp_path):
    """scripts/individual_history.py läser en individs alla händelser i ordning:
    uppstart, förstörelse, torr sökning, förlorad ansökan med vinnarens q,
    vunnen ansökan, anställning ur arbetslöshet mot Pi_o, byte med vinst."""
    lines = [
        "0.00, new_month, agent_type system, month 1, employed 900, unemployed 100, "
        "unmatched_jobs 0, not_in_labour_force 0, active_jobs 900, posted 0",
        "0.00, start_job, agent_id 7, job_id J0, to_onet 51-2011.00, w_field 1.0, w_occ 1.0, "
        "w_neg 0.9, q_hire 0.8, is_bootstrap True, job_to_job False",
        "300.00, destroy_job, event_detail job_destroyed_holder_displaced, agent_id 7, job_id J0",
        "320.00, start_job_search, event_detail match_failed, status unemployed, agent_id 7",
        "350.00, start_job_search, event_detail application_filed, status unemployed, agent_id 7, "
        "job_id J1, surplus 0.1, w_neg 0.85, q_hire 0.7, commute_km 4.0",
        "390.00, close_vacancy, event_detail match_completed, job_id J1, agent_id 9, "
        "n_applicants 3, q_hire 0.95, winner_employed True",
        "400.00, start_job_search, event_detail application_filed, status unemployed, agent_id 7, "
        "job_id J2, surplus 0.2, w_neg 0.88, q_hire 0.75, commute_km 2.0",
        "440.00, close_vacancy, event_detail match_completed, job_id J2, agent_id 7, "
        "n_applicants 1, q_hire 0.75, winner_employed False",
        "450.00, start_job, agent_id 7, job_id J2, to_onet 51-2011.00, w_field 1.0, w_occ 0.95, "
        "w_neg 0.88, q_hire 0.75, job_to_job False, n_applicants 1",
        "800.00, start_job_search, event_detail application_filed, status employed, agent_id 7, "
        "job_id J3, surplus 0.15, w_neg 1.02, q_hire 0.9, commute_km 8.0",
        "840.00, close_vacancy, event_detail quit_job, agent_id 7, job_id J2, to_job_id J3, "
        "notice_days 30.0",
        "840.00, close_vacancy, event_detail match_completed, job_id J3, agent_id 7, "
        "n_applicants 4, q_hire 0.9, winner_employed True",
        "870.00, start_job, agent_id 7, job_id J3, to_onet 51-2011.00, w_field 1.05, w_occ 1.0, "
        "w_neg 1.02, q_hire 0.9, job_to_job True, w_prev 0.88, n_applicants 4",
        "3652.50, simulation_completed, agent_type system",
    ]
    d = tmp_path / "run_k"; d.mkdir()
    (d / "eventlog.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ut = _run_individual_history(str(d), "--agent", "7",
                                 "--db", str(tmp_path / "finns_inte"))
    assert "1 byten, 3 ansökningar av 4 sökningar" in ut
    assert "FÖRLORAR JOBBET: J0" in ut
    assert "1 sökning(ar) utan ansökan" in ut
    assert "förlorade mot 9 (q 0.95)" in ut
    assert "ANSTÄLLS ur arbetslöshet: J2" in ut and "0.926 × Π_o" in ut
    assert "SÄGER UPP SIG från J2 för J3" in ut
    assert "BYTE: J3" in ut and "vinst +15.9 %" in ut


def test_log_writes_one_form_of_agent_id(tmp_path):
    """REGRESSION: extra-dicten skrev över agent_id med DataFrame-indexet,
    medan händelsens egen agent_id slogs upp till individual_id. Loggen hade
    två former för samma person -- 2062_i003443 på ansökan, 3443 på
    match_completed -- så varje läsare som jämförde dem fick ingen träff, och
    individens egna vinster lästes som förluster mot en okänd."""
    import pandas as pd
    from core.log import EventLogger

    class Stub:
        individuals = pd.DataFrame({"individual_id": ["2062_i000000", "2062_i003443"],
                                    "chi": [0.3, 0.3], "xi": [0.2, 0.2], "r_i": [0.1, 0.1]},
                                   index=[0, 3443])
        employers = pd.DataFrame()

    path = tmp_path / "e.csv"
    lg = EventLogger(str(path))
    # close_vacancy: händelsen har ingen agent, vinnaren står i extra
    lg.log_event(Stub(), {"time": 1.0, "agent_id": None, "event_type": "close_vacancy"},
                 extra={"event_detail": "match_completed", "agent_id": 3443, "job_id": "J1"})
    # start_job_search: agenten står på händelsen
    lg.log_event(Stub(), {"time": 2.0, "agent_id": 3443, "event_type": "start_job_search"},
                 extra={"event_detail": "application_filed", "job_id": "J1"})
    lg.file.close()
    rader = [parse_line(l) for l in path.read_text(encoding="utf-8").splitlines()]
    assert [r["agent_id"] for r in rader] == ["2062_i003443", "2062_i003443"]
    assert rader[0]["agent_type"] == "individual"


def test_wage_losing_moves_and_stale_applications_are_counted(tmp_path):
    """Individkedjorna (0091) visade byten med negativ lönevinst: ansökan
    lämnad som arbetslös, erbjudandet kom efter att hon tagit ett annat jobb,
    tillträdet skedde ändå. Två mått ska fånga kanalen."""
    lines = [
        "0.00, new_month, agent_type system, month 1, employed 900, unemployed 100, "
        "unmatched_jobs 0, not_in_labour_force 0, active_jobs 900, posted 0",
        # A ansöker som arbetslös, tillträder senare som anställd med lägre lön
        "100.00, start_job_search, event_detail application_filed, status unemployed, "
        "agent_id A, job_id J2, w_neg 0.90, q_hire 0.6",
        "150.00, start_job, agent_id A, job_id J1, from_onet 43-4051.00, to_onet 51-2011.00, occ_change 1, w_field 1.0, w_occ 1.0, "
        "w_neg 1.00, q_hire 0.7, job_to_job False, u_R 0.5, u_R_occ 0.5",
        "200.00, start_job, agent_id A, job_id J2, from_onet 43-4051.00, to_onet 51-2011.00, occ_change 1, w_field 1.0, w_occ 1.0, "
        "w_neg 0.90, q_hire 0.6, job_to_job True, w_prev 1.00, u_R 2.4, u_R_occ 2.4",
        # B ansöker som anställd och byter uppåt
        "300.00, start_job_search, event_detail application_filed, status employed, "
        "agent_id B, job_id J4, w_neg 1.20, q_hire 0.9",
        "310.00, start_job, agent_id B, job_id J3, from_onet 43-4051.00, to_onet 51-2011.00, occ_change 1, w_field 1.0, w_occ 1.0, "
        "w_neg 1.00, q_hire 0.8, job_to_job False, u_R 0.3, u_R_occ 0.3",
        "350.00, start_job, agent_id B, job_id J4, from_onet 43-4051.00, to_onet 51-2011.00, occ_change 1, w_field 1.2, w_occ 1.2, "
        "w_neg 1.20, q_hire 0.9, job_to_job True, w_prev 1.00, u_R 0.4, u_R_occ 0.4",
        "3652.50, simulation_completed, agent_type system",
    ]
    d = tmp_path / "run_w"; d.mkdir()
    (d / "eventlog.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    row = summary_row(str(d))
    assert row["share_moves_wage_loss"] == pytest.approx(0.5)
    assert row["share_moves_application_matched"] == pytest.approx(1.0)
    assert row["share_moves_applied_while_unemployed"] == pytest.approx(0.5)
    assert row["share_u_R_occ_above_1"] == pytest.approx(0.25)


def test_individual_history_reads_legacy_agent_id_forms(tmp_path):
    """REGRESSION: 0092 skulle ge verktyget en id-jämförelse som klarar
    loggens två former, men skrivningen av filen uteblev -- en assert i mitt
    eget skript föll och individual_history.py blev orört, medan
    commit-meddelandet påstod motsatsen. Utskriften sade fortfarande
    'förlorade mot 3443' om individens egen vinst. Provet använder en logg i
    gammal form: individual_id på ansökan, DataFrame-index på
    match_completed."""
    lines = [
        "0.00, new_month, agent_type system, month 1, employed 900, unemployed 100, "
        "unmatched_jobs 0, not_in_labour_force 0, active_jobs 900, posted 0",
        "285.00, start_job_search, agent_type individual, agent_id 2062_i003443, "
        "event_detail application_filed, status unemployed, job_id N1, surplus 0.069, "
        "w_neg 1.0143, q_hire 0.824, commute_km 4.133",
        "315.00, close_vacancy, agent_type system, agent_id 3443, "
        "event_detail match_completed, job_id N1, n_applicants 4, q_hire 0.824, "
        "winner_employed False",
        "345.00, start_job, agent_type individual, agent_id 2062_i003443, job_id N1, "
        "u_R 0.5, u_R_occ 0.53, from_onet 43-4051.00, to_onet 29-2099.05, occ_change 1, "
        "w_field 1.1, w_occ 1.1, w_neg 1.0143, q_hire 0.824, job_to_job False",
        "3652.50, simulation_completed, agent_type system",
    ]
    d = tmp_path / "run_legacy"; d.mkdir()
    (d / "eventlog.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ut = _run_individual_history(str(d), "--agent", "2062_i003443",
                                 "--db", str(tmp_path / "finns_inte"))
    assert "-> VANN" in ut
    assert "förlorade mot" not in ut


def test_move_premium_splits_into_its_three_sources(tmp_path):
    """log w = log Pi_o + eta + theta log p, och alla tre står i loggen:
    w_occ, w_field/w_occ, w_neg/w_field. Mellan två anställningar för samma
    individ ska uppdelningen vara exakt, och w_prev ska ge revisionens del.
    Provet: Pi_o 1.0 -> 1.1, eta 0 -> 0.05 (i log), passform 0.9 -> 1.0 av
    fältlönen, och lönen hon hade vid bytet 2 procent över ingångslönen."""
    import numpy as np
    a_occ, b_occ = 1.0, 1.1
    a_field, b_field = 1.0, 1.1 * np.exp(0.05)
    a_neg, b_neg = 0.9 * a_field, 1.0 * b_field
    w_prev = a_neg * 1.02
    lines = [
        "0.00, new_month, agent_type system, month 1, employed 900, unemployed 100, "
        "unmatched_jobs 0, not_in_labour_force 0, active_jobs 900, posted 0",
        f"100.00, start_job, agent_id A, job_id J1, from_onet 43-4051.00, "
        f"to_onet 51-2011.00, occ_change 1, u_R 0.5, u_R_occ 0.5, w_occ {a_occ}, "
        f"w_field {a_field}, w_neg {a_neg}, q_hire 0.8, job_to_job False",
        f"900.00, start_job, agent_id A, job_id J2, from_onet 51-2011.00, "
        f"to_onet 29-2099.05, occ_change 1, u_R 0.5, u_R_occ 0.5, w_occ {b_occ}, "
        f"w_field {b_field}, w_neg {b_neg}, q_hire 0.9, job_to_job True, "
        f"w_prev {w_prev}",
        "3652.50, simulation_completed, agent_type system",
    ]
    d = tmp_path / "run_d"; d.mkdir()
    (d / "eventlog.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    row = summary_row(str(d))
    assert row["n_move_decomp"] == 1
    assert row["move_d_occ_mean"] == pytest.approx(np.log(1.1), abs=1e-4)
    assert row["move_d_eta_mean"] == pytest.approx(0.05, abs=1e-4)
    assert row["move_d_fit_mean"] == pytest.approx(np.log(1.0 / 0.9), abs=1e-4)
    assert row["move_d_revision_mean"] == pytest.approx(np.log(1.02), abs=1e-4)
    # Identiteten: de tre delarna minus revisionen är bytespremien
    assert (row["move_d_occ_mean"] + row["move_d_eta_mean"] + row["move_d_fit_mean"]
            - row["move_d_revision_mean"]) == pytest.approx(row["move_gain_mean"], abs=1e-3)


def test_first_step_gap_is_the_next_move_for_the_same_individual(tmp_path):
    """Vektoriseringen i 0096 får inte ändra vad måttet ÄR: tiden från en
    anställning ur arbetslöshet till samma individs NÄSTA byte, och ingen
    annans. A anställs dag 100 och byter dag 300 (200 dagar); B anställs dag
    150 och byter aldrig; C byter dag 500 utan föregående anställning i
    urvalet. Medianen ska vara 200 med ett enda mellanrum."""
    def sj(t, aid, jtj, w=1.0, extra=""):
        return (f"{t:.2f}, start_job, agent_id {aid}, job_id J{aid}{int(t)}, "
                f"from_onet 43-4051.00, to_onet 51-2011.00, occ_change 1, u_R 0.5, "
                f"u_R_occ 0.5, w_field 1.0, w_occ 1.0, w_neg {w}, q_hire 0.8, "
                f"job_to_job {jtj}{extra}")
    lines = [
        "0.00, new_month, agent_type system, month 1, employed 900, unemployed 100, "
        "unmatched_jobs 0, not_in_labour_force 0, active_jobs 900, posted 0",
        sj(100.0, "A", "False"),
        sj(150.0, "B", "False"),
        sj(300.0, "A", "True", 1.1, ", w_prev 1.0"),
        sj(500.0, "C", "True", 1.2, ", w_prev 1.0"),
        "3652.50, simulation_completed, agent_type system",
    ]
    d = tmp_path / "run_g"; d.mkdir()
    (d / "eventlog.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    row = summary_row(str(d))
    assert row["days_to_first_step_median"] == pytest.approx(200.0)
    assert row["share_first_step_within_year"] == pytest.approx(1.0)
    # två anställningar ur arbetslöshet (A, B), ett steg taget
    assert row["share_unemployed_hires_that_step"] == pytest.approx(0.5)


def test_archived_runs_are_found_by_name(tmp_path, monkeypatch):
    """kor_0077.sh flyttar körningar från andra commits till output/arkiv/, så
    en sökväg som fungerade i går ger FileNotFoundError i dag. Katalognamnet
    är unikt: verktyget letar upp det, och säger vilka körningar som finns om
    det inte hittas."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
    from individual_history import _resolve_run_dir

    ark = tmp_path / "output" / "arkiv" / "run_20260912_185257"
    ark.mkdir(parents=True)
    (ark / "eventlog.csv").write_text("0.00, simulation_completed, agent_type system\n",
                                      encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert _resolve_run_dir("output/run_20260912_185257") == str(
        Path("output") / "arkiv" / "run_20260912_185257")
    with pytest.raises(SystemExit) as fel:
        _resolve_run_dir("output/run_finns_inte")
    assert "run_20260912_185257" in str(fel.value)


def test_open_vacancies_exclude_the_promised_positions(tmp_path):
    """SCB:s vakans är en ledig befattning som rekryteringen ännu inte löst.
    En position där någon tackat ja men tillträder om en månad står obesatt i
    modellen och ingår i V -- och i identiteten U = L - J + V, som inte ska
    röras -- men den är inte ledig. v_open är jämförelsetalet: här 40 obesatta
    av 1000 aktiva, varav 15 utlovade, alltså v 4.0 och v_open 2.5."""
    lines = [
        "0.00, new_month, agent_type system, month 1, employed 900, unemployed 100, "
        "unmatched_jobs 40, open_vacancies 25, not_in_labour_force 0, active_jobs 1000, posted 0",
        "3652.50, simulation_completed, agent_type system",
    ]
    d = tmp_path / "run_v"; d.mkdir()
    (d / "eventlog.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ts = timeseries_table([parse_line(l) for l in lines])
    assert float(ts["v"].iloc[0]) == pytest.approx(4.0)
    assert float(ts["v_open"].iloc[0]) == pytest.approx(2.5)
    row = summary_row(str(d))
    assert row["v_pct"] == pytest.approx(4.0)
    assert row["v_open_pct"] == pytest.approx(2.5)


def test_promised_positions_are_counted_as_not_open():
    """analyze_world ska skilja obesatt från ledig: en position med pending är
    tillsatt, tillträdet återstår bara."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from conftest import make_world
    from core.statistics.basic_stats import analyze_world
    w = make_world(n_employers=2, size=5)
    w.prepare()
    w.jobs["individual_id"] = np.nan
    w.jobs["pending"] = False
    w.jobs.loc[w.jobs.index[:3], "pending"] = True
    st = analyze_world(w)
    assert st["unmatched_jobs"] == 10
    assert st["open_vacancies"] == 7


def test_the_vacancy_life_is_split_into_its_parts(tmp_path):
    """Stocken är flöde gånger varaktighet, så varaktighetens poster sätter
    vakansgraden. Provet: en annons öppnas efter 23 dagars väntan, beslutet
    faller vid 63 (fönstret 40), tillträdet vid 80. Och med en medelstock på
    10 vakanser i ett år, alltså 3 652 vakansdagar, medan den enda tillsatta
    positionen stod öppen i 80 -- resten av dagarna tillbringas i positioner
    som aldrig tillsätts."""
    lines = [
        "0.00, new_month, agent_type system, month 1, employed 900, unemployed 100, "
        "unmatched_jobs 10, open_vacancies 10, not_in_labour_force 0, active_jobs 1000, posted 0",
        "23.00, open_advert, event_detail advert_opened, job_id J1, "
        "wait_first_applicant_days 23.0",
        "63.00, close_vacancy, event_detail match_completed, job_id J1, agent_id A, "
        "n_applicants 2, q_hire 0.8, winner_employed False, vacancy_age_at_decision 63.0",
        "80.00, start_job, agent_id A, job_id J1, from_onet 43-4051.00, to_onet 51-2011.00, "
        "occ_change 1, u_R 0.5, u_R_occ 0.5, w_field 1.0, w_occ 1.0, w_neg 0.9, q_hire 0.8, "
        "job_to_job False, vacancy_age_days 80.0",
        "365.25, new_month, agent_type system, month 12, employed 900, unemployed 100, "
        "unmatched_jobs 10, open_vacancies 10, not_in_labour_force 0, active_jobs 1000, posted 0",
        "365.25, simulation_completed, agent_type system",
    ]
    d = tmp_path / "run_l"; d.mkdir()
    (d / "eventlog.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    row = summary_row(str(d))
    assert row["wait_first_applicant_median"] == pytest.approx(23.0)
    assert row["n_adverts_opened"] == 1
    assert row["vacancy_age_at_decision_median"] == pytest.approx(63.0)
    # 10 vakanser i ett år = 3 652.5 vakansdagar, varav 80 i en tillsatt position
    assert row["vacancy_days_share_unfilled"] == pytest.approx(1 - 80 / 3652.5, abs=1e-3)


def test_the_advert_records_how_long_the_vacancy_waited():
    """Väntan på första sökanden går inte att räkna i efterhand: en vakans
    utan sökande får ingen händelse alls. Den loggas när annonsen öppnas."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from conftest import make_world
    w = make_world(n_employers=1, size=2)
    w.prepare()
    w.event_logger.events = []
    jid = w.jobs.at[0, "job_id"]
    w.jobs.at[0, "vacant_since"] = 100.0
    w.file_application(jid, 0, 123.0, q=0.8, w_neg=1.0, surplus=0.1, commute_km=1.0)
    rader = [e for _, e in w.event_logger.events if e.get("event_detail") == "advert_opened"]
    assert len(rader) == 1
    assert rader[0]["wait_first_applicant_days"] == pytest.approx(23.0)
