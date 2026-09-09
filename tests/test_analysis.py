"""Exportlagret: en parser, tre tabeller.

Tidigare hade validate_mobility, convergence och figures varsin kopia av
samma parser, och check_invariants och compare_municipalities läste
tillståndsfilerna med varsin logik. Fem tolkningar av samma data."""
import os

import numpy as np
import pandas as pd
import pytest

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
        })
    st = _wage_stock_stats(W())
    assert st["stock_n"] == 100
    assert st["stock_w_p50"] == pytest.approx(1.0, abs=0.02)
    assert st["stock_w_p90p10"] == pytest.approx(1.4 / 0.6, rel=0.05)
    assert st["stock_sd_log_w"] > 0

    # För få anställda ger inget mått i stället för ett brusigt
    class Tiny:
        individuals = pd.DataFrame({"status": ["employed"] * 3,
                                    "w_neg": [1.0, 1.1, 0.9]})
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


