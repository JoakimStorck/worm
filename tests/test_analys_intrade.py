"""Rapportens avsnitt om de ungas inträde och pensionsåldern
(scripts/figures.py fig_intrade, scripts/analysis.py)."""
import json
import os
import sqlite3

import pandas as pd
import pytest


def _korning(tmp_path, med_studerande=True):
    d = tmp_path / "run_x"
    d.mkdir()
    (d / "run_meta.json").write_text(json.dumps({"municipalities": [2062]}))
    rader = []
    for ar in range(3):
        t = ar * 365.25
        rader.append(f"{t:.2f}, new_year, agent_type system, new_students {10 * ar}, retired {5 * ar}")
        rader.append(f"{t + 1:.2f}, new_month, agent_type system, month 1, employed {900 + ar}, "
                     f"unemployed 100, unmatched_jobs 10, active_jobs 1000")
    rader += [f"{400 + k:.2f}, intrade, agent_type individual, agent_id {k}, "
              f"event_detail entered_labour_force" for k in range(3)]
    rader += ["401.00, intrade, agent_type individual, agent_id 9, event_detail never_entered"]
    (d / "eventlog.csv").write_text("\n".join(rader) + "\n")
    start = pd.DataFrame({"status": ["student", "employed", "employed", "unemployed"],
                          "age": [17.0, 17.0, 26.0, 26.0], "extern": False})
    slut = pd.DataFrame({"status": ["employed", "student", "employed", "employed"] + ["student"] * 10,
                         "age": [17.0, 17.0, 26.0, 26.0] + [18.0] * 10, "extern": False})
    if med_studerande:
        slut["studerande"] = [True, True, False, False] + [True] * 10
    start.to_csv(d / "initial_state_individuals.csv", index=False)
    slut.to_csv(d / "final_state_individuals.csv", index=False)
    db = tmp_path / "db.sqlite3"
    conn = sqlite3.connect(db)
    lf = pd.DataFrame({"municipal_code": "2062", "year": 2024,
                       "age_group": ["16-19", "20-24", "25-29", "30-34"],
                       "in_labour_force": [40, 80, 86, 88], "total": [100] * 4})
    # en kommun utanför scenariot, som inte ska räknas in
    pd.concat([lf, lf.assign(municipal_code="2034", in_labour_force=0)]).to_sql(
        "labour_force_by_age", conn, index=False)
    # icke-studerande arbetar i högre grad; de ska inte räknas in
    pd.DataFrame([(str(a), st, f, n) for a in range(16, 25)
                  for st, f, n in (("1", "FÖRV", 30), ("1", "EJFÖRV", 70),
                                   ("0", "FÖRV", 90), ("0", "EJFÖRV", 10))],
                 columns=["age", "study", "employment", "population"]).to_sql(
        "population_study_education", conn, index=False)
    conn.close()
    return str(d), str(db)


def test_intradesfiguren_raknar_deltagande_floden_och_arbetande_studerande(tmp_path):
    import scripts.figures as F
    rd, db = _korning(tmp_path)
    r = F.fig_intrade([rd], str(tmp_path / "fig"), db=db)
    d = r["deltagande"].set_index("ålder")
    assert d.loc["16-19", "start"] == pytest.approx(0.5)      # en av två 17-åringar
    assert d.loc["25-29", "slut"] == pytest.approx(1.0)
    assert d.loc["25-29", "start"] == pytest.approx(1.0), "den arbetslösa är i arbetskraften"
    assert d.loc["16-19", "BAS"] == pytest.approx(0.40)
    f = r["floden"].set_index("år")
    assert f.loc[1, "gick in"] == 3 and f.loc[1, "aldrig in"] == 1
    assert f.loc[2, "nya studenter"] == 20 and f.loc[2, "arbetskraft"] == 1002
    a = r["studerande_arbetar"].set_index("ålder")
    assert a.loc[18, "modellen"] == pytest.approx(0.0) and a.loc[18, "TAB3731"] == pytest.approx(0.3)
    assert os.path.isfile(tmp_path / "fig" / "intrade.pdf")


def test_utan_inträden_ingen_figur_och_det_star_i_rapporten(tmp_path):
    import scripts.figures as F
    from scripts.analysis import _avsnitt_intrade
    assert F.fig_intrade([], str(tmp_path)) is None
    assert "Ingen körning har inträden" in "".join(_avsnitt_intrade(None))


def test_pensionsavsnittet_sager_var_underlaget_kommer_ifran(tmp_path, monkeypatch):
    import scripts.analys_pensionsalder as P
    from scripts.analysis import _avsnitt_pensionsalder
    monkeypatch.setattr(P.rapportfigur, "__defaults__",
                        (str(tmp_path / "saknas.csv"), P.YRKESFIL, P.DB))
    text = "".join(_avsnitt_pensionsalder(str(tmp_path)))
    assert "saknas" in text and "Pensionsmyndighetens" in text
