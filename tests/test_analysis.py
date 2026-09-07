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
