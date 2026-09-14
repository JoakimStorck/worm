"""Uppspelningen i scripts/export_viz.py.

Rekonstruktionen är det enda stället i kodbasen som härleder tillstånd ur
loggen i stället för att läsa det. Går de två isär -- en händelsetyp som
flyttar en individ utan att uppspelningen känner den -- syns det inte som ett
fel utan som en figur där sysselsättningen inte följer kurvan bredvid. Testet
ställer panelens rekonstruerade stock mot new_month-radens.
"""
import json
import os

import pandas as pd
import pytest

from scripts.export_viz import exportera, spela_upp


def _skriv_slutlage(dir_, jobb, nya=None):
    """final_state_jobs.csv: hela stocken vid slutet, inklusive jobb som
    postats under körningen."""
    import pandas as _pd
    df = jobb.copy()
    df["created_time"] = 0.0
    if nya is not None:
        df = _pd.concat([df, nya], ignore_index=True)
    df.to_csv(os.path.join(dir_, "final_state_jobs.csv"), index=False)


def _skriv_korning(dir_, n_ind=40):
    os.makedirs(dir_, exist_ok=True)
    ind = pd.DataFrame([{
        "individual_id": f"2062_i{i:06d}" if i < n_ind // 2 else f"2034_i{i:06d}",
        "x": 400000.0 + i, "y": 6700000.0 + i,
        "xi": 1.0, "chi": 1.0, "r_o_home": 0.27,
        "onet_code": "41-2031", "job_id": None, "municipal_code": "2062",
    } for i in range(n_ind)])
    jobb = pd.DataFrame([{
        "job_id": f"J{j:07d}", "employer_id": "2062_e000001",
        "individual_id": None, "municipal_code": "2062" if j % 2 else "2034",
        "x": 400000.0, "y": 6700000.0, "xi": 1.0, "chi": 1.0,
        "r_o": 0.3, "r_req": 0.4, "wage": 30000.0, "onet_code": "41-2031",
    } for j in range(n_ind)])
    ind.to_csv(os.path.join(dir_, "initial_state_individuals.csv"), index=False)
    jobb.to_csv(os.path.join(dir_, "initial_state_jobs.csv"), index=False)
    return ind, jobb


def _logg(dir_, rader):
    with open(os.path.join(dir_, "eventlog.csv"), "w", encoding="utf-8") as f:
        f.write("\n".join(rader) + "\n")


def _rad(t, h, **kv):
    return ", ".join([f"{t:.2f}", h] + [f"{k} {v}" for k, v in kv.items()])


def test_anstallning_och_forstorelse_speglas_i_panelen(tmp_path):
    d = str(tmp_path / "run_a")
    _skriv_korning(d, n_ind=40)
    rader = [
        _rad(0.0, "new_month", month=1, year=2020, employed=0, unemployed=40,
             unmatched_jobs=40, active_jobs=40, not_in_labour_force=0),
        _rad(5.0, "start_job", agent_type="individual", agent_id="2062_i000000",
             chi=1.0, xi=1.0, r_i=0.27, job_id="J0000001", is_bootstrap=False,
             home_municipality="2062", job_municipality="2062", u_R=0.8,
             from_onet="41-2031", to_onet="41-2031", vacancy_age_days=40),
        _rad(30.0, "new_month", month=2, year=2020, employed=1, unemployed=39,
             unmatched_jobs=39, active_jobs=40, not_in_labour_force=0),
        _rad(35.0, "destroy_job", agent_type="individual", agent_id="2062_i000000",
             chi=1.0, xi=1.0, r_i=0.27,
             event_detail="job_destroyed_holder_displaced", job_id="J0000001"),
        _rad(60.0, "new_month", month=3, year=2020, employed=0, unemployed=40,
             unmatched_jobs=39, active_jobs=39, not_in_labour_force=0),
    ]
    _logg(d, rader)

    panel, panel_jobb, frames, ticker, _ = spela_upp(d, 40, 40, seed=0)

    assert [f["month"] for f in frames] == [1, 2, 3]
    assert sum(frames[0]["workers"]["state"]) == 0
    assert sum(frames[1]["workers"]["state"]) == 1      # anställd
    assert sum(frames[2]["workers"]["state"]) == 0      # och utslagen igen

    # Jobbet ska vara besatt i ruta 2 och inaktivt i ruta 3.
    pos = list(panel_jobb["job_id"]).index("J0000001")
    assert frames[1]["jobs"]["state"][pos] == 0
    assert frames[2]["jobs"]["state"][pos] == 2

    # Uppstartens tillsättningar hör inte hemma i händelseströmmen.
    assert len(ticker) == 1 and ticker[0]["worker"] == "2062_i000000"


def test_uppstartens_anstallningar_las_ur_starttillstandet(tmp_path):
    """initial_state skrivs EFTER bootstrap_matching. Läses job_id-kolumnen
    inte in börjar hela panelen som arbetslös och den första bildrutan visar
    en marknad som aldrig funnits."""
    d = str(tmp_path / "run_b")
    ind, jobb = _skriv_korning(d, n_ind=10)
    ind.loc[0:4, "job_id"] = [f"J{j:07d}" for j in range(5)]
    jobb.loc[0:4, "individual_id"] = list(ind.loc[0:4, "individual_id"])
    ind.to_csv(os.path.join(d, "initial_state_individuals.csv"), index=False)
    jobb.to_csv(os.path.join(d, "initial_state_jobs.csv"), index=False)
    _logg(d, [_rad(0.0, "new_month", month=1, year=2020, employed=5,
                   unemployed=5, unmatched_jobs=5, active_jobs=10,
                   not_in_labour_force=0)])

    _, _, frames, _, _ = spela_upp(d, 10, 10, seed=0)
    assert sum(frames[0]["workers"]["state"]) == 5
    assert frames[0]["jobs"]["state"].count(0) == 5


def test_aggregaten_kommer_ur_loggen_och_rakas_inte_om(tmp_path):
    """Talen i rutan ska vara new_month-radens, inte panelens. Panelen är ett
    urval; räknades u om på den skulle figuren säga något annat än tabellen."""
    d = str(tmp_path / "run_c")
    _skriv_korning(d, n_ind=20)
    _logg(d, [_rad(0.0, "new_month", month=1, year=2020, employed=800,
                   unemployed=200, unmatched_jobs=50, active_jobs=850,
                   not_in_labour_force=0)])
    _, _, frames, _, _ = spela_upp(d, 20, 20, seed=0)
    assert frames[0]["agg"]["employed"] == 800
    assert frames[0]["agg"]["u"] == pytest.approx(20.0, abs=0.01)


def test_panelen_tacker_varje_kommun(tmp_path):
    """Den minsta kommunen är den tunnheten ska synas i. Ett obundet urval
    riskerar att inte ta med den alls."""
    d = str(tmp_path / "run_d")
    _skriv_korning(d, n_ind=40)
    _logg(d, [_rad(0.0, "new_month", month=1, year=2020, employed=0,
                   unemployed=40, unmatched_jobs=40, active_jobs=40,
                   not_in_labour_force=0)])
    panel, _, _, _, _ = spela_upp(d, 6, 10, seed=0)
    kommuner = {str(i).split("_i")[0] for i in panel["individual_id"]}
    assert kommuner == {"2062", "2034"}


def test_pendlingsmatrisen_raknas_pa_hela_populationen(tmp_path):
    """Matrisen ska ställas mot SCB:s tabell `commuting`. Räknas den på
    panelen är nämnaren en annan än SCB:s och kvoten saknar tolkning.
    Summan ska därför vara oberoende av --panel."""
    d = str(tmp_path / "run_f")
    ind, jobb = _skriv_korning(d, n_ind=20)
    ind.loc[0:9, "job_id"] = [f"J{j:07d}" for j in range(10)]
    jobb.loc[0:9, "individual_id"] = list(ind.loc[0:9, "individual_id"])
    ind.to_csv(os.path.join(d, "initial_state_individuals.csv"), index=False)
    jobb.to_csv(os.path.join(d, "initial_state_jobs.csv"), index=False)
    _logg(d, [_rad(0.0, "new_month", month=1, year=2020, employed=10,
                   unemployed=10, unmatched_jobs=10, active_jobs=20,
                   not_in_labour_force=0)])

    summor = []
    for n in (4, 20):
        _, _, frames, _, _ = spela_upp(d, n, 20, seed=0)
        summor.append(sum(frames[0]["commuting"].values()))
    assert summor == [10, 10]


def test_json_gar_att_lasa_och_bar_harkomst(tmp_path):
    d = str(tmp_path / "run_e")
    _skriv_korning(d, n_ind=12)
    _logg(d, [_rad(0.0, "new_month", month=1, year=2020, employed=0,
                   unemployed=12, unmatched_jobs=12, active_jobs=12,
                   not_in_labour_force=0)])
    with open(os.path.join(d, "run_meta.json"), "w", encoding="utf-8") as f:
        json.dump({"scenario": "siljan_3_kommuner.yml", "seed": 7,
                   "git_commit": "0123456789", "municipalities": ["2062", "2034"]}, f)
    ut = str(tmp_path / "viz" / "e.json")
    exportera(d, ut, panel_n=12, panel_jobb_n=12, seed=0, db_path=None)
    with open(ut, encoding="utf-8") as f:
        data = json.load(f)
    assert data["meta"]["scenario"] == "siljan_3_kommuner.yml"
    assert data["meta"]["commit"] == "01234567"
    assert data["meta"]["n_months"] == 1
    assert len(data["workers"]["id"]) == len(data["workers"]["x"]) == 12


def test_jobb_postade_under_korningen_kommer_med(tmp_path):
    """post_vacancies_batch skapar jobb med id-prefix N under körningen. De
    finns bara i final_state_jobs.csv. Läses de inte syns panelens medlemmar
    som anställda utan jobb att peka på, och pendlingsmatrisen tappar deras
    kommun."""
    import pandas as pd

    d = str(tmp_path / "run_n")
    ind, jobb = _skriv_korning(d, n_ind=10)
    nytt = pd.DataFrame([{
        "job_id": "N0000001", "employer_id": "2062_e000001",
        "individual_id": None, "municipal_code": "2034",
        "x": 400000.0, "y": 6700000.0, "xi": 1.0, "chi": 1.0,
        "r_o": 0.3, "r_req": 0.4, "wage": 30000.0, "onet_code": "41-2031",
        "created_time": 40.0,
    }])
    _skriv_slutlage(d, jobb, nytt)
    _logg(d, [
        _rad(0.0, "new_month", month=1, year=2020, employed=0, unemployed=10,
             unmatched_jobs=10, active_jobs=10, not_in_labour_force=0),
        _rad(45.0, "start_job", agent_type="individual",
             agent_id="2062_i000000", chi=1.0, xi=1.0, r_i=0.27,
             job_id="N0000001", is_bootstrap=False, u_R=0.8,
             home_municipality="2062", job_municipality="2034",
             from_onet="41-2031", to_onet="41-2031", vacancy_age_days=10),
        _rad(60.0, "new_month", month=3, year=2020, employed=1, unemployed=9,
             unmatched_jobs=10, active_jobs=11, not_in_labour_force=0),
    ])

    panel, panel_jobb, frames, _, _ = spela_upp(d, 10, 20, seed=0)

    assert "N0000001" in set(panel_jobb["job_id"])
    pos = list(panel_jobb["job_id"]).index("N0000001")
    # Månad 1: jobbet är inte fött än.
    assert frames[0]["jobs"]["state"][pos] == 3
    # Månad 3: fött och besatt, och pendlingen över kommungräns räknad.
    assert frames[1]["jobs"]["state"][pos] == 0
    assert frames[1]["commuting"] == {"2062>2034": 1}


def test_slutlagets_innehavare_smittar_inte_startlaget(tmp_path):
    """final_state_jobs.csv bär den som håller jobbet vid SLUTET. Ärvs den
    börjar uppspelningen i slutläget."""
    import pandas as pd

    d = str(tmp_path / "run_s")
    ind, jobb = _skriv_korning(d, n_ind=10)
    slut = jobb.copy()
    slut["created_time"] = 0.0
    slut.loc[0, "individual_id"] = "2062_i000003"     # innehavare vid slutet
    slut.to_csv(os.path.join(d, "final_state_jobs.csv"), index=False)
    _logg(d, [_rad(0.0, "new_month", month=1, year=2020, employed=0,
                   unemployed=10, unmatched_jobs=10, active_jobs=10,
                   not_in_labour_force=0)])

    _, _, frames, _, _ = spela_upp(d, 10, 20, seed=0)
    assert sum(frames[0]["workers"]["state"]) == 0
    assert frames[0]["jobs"]["state"].count(0) == 0


def test_career_break_och_utbildning_avslutar_anstallningen(tmp_path):
    """Varken handle_career_break eller handle_start_education skriver en
    destroy_job-rad, men båda nollar individens job_id och släpper
    positionen. Känner uppspelningen dem inte räknas personen som anställd
    tills hon anställs igen."""
    d = str(tmp_path / "run_cb")
    ind, jobb = _skriv_korning(d, n_ind=10)
    ind.loc[0:1, "job_id"] = ["J0000000", "J0000001"]
    jobb.loc[0:1, "individual_id"] = list(ind.loc[0:1, "individual_id"])
    ind.to_csv(os.path.join(d, "initial_state_individuals.csv"), index=False)
    jobb.to_csv(os.path.join(d, "initial_state_jobs.csv"), index=False)
    i0, i1 = ind.loc[0, "individual_id"], ind.loc[1, "individual_id"]
    _logg(d, [
        _rad(0.0, "new_month", month=1, year=2020, employed=2, unemployed=8,
             unmatched_jobs=8, active_jobs=10, not_in_labour_force=0),
        _rad(10.0, "career_break", agent_type="individual", agent_id=i0,
             chi=1.0, xi=1.0, r_i=0.27, event_detail="career_break"),
        _rad(30.0, "new_month", month=2, year=2020, employed=1, unemployed=8,
             unmatched_jobs=9, active_jobs=10, not_in_labour_force=1),
        _rad(40.0, "start_education", agent_type="individual", agent_id=i1,
             chi=1.0, xi=1.0, r_i=0.27, event_detail="education_started"),
        _rad(60.0, "new_month", month=3, year=2020, employed=0, unemployed=8,
             unmatched_jobs=10, active_jobs=10, not_in_labour_force=2),
    ])

    _, panel_jobb, frames, _, _ = spela_upp(d, 10, 20, seed=0)

    assert [sum(f["workers"]["state"]) for f in frames] == [2, 1, 0]
    # Positionerna ska stå som vakanser, inte som inaktiva: jobben förstörs
    # inte, de blir lediga.
    for jid in ("J0000000", "J0000001"):
        pos = list(panel_jobb["job_id"]).index(jid)
        assert frames[2]["jobs"]["state"][pos] == 1


def test_artalet_hamtas_fran_new_year(tmp_path):
    """handle_new_month loggar month men inte year. Utan new_year-raden blir
    varje bildruta year: null och tidsaxeln kan inte visa årtal."""
    d = str(tmp_path / "run_ar")
    _skriv_korning(d, n_ind=10)
    _logg(d, [
        _rad(0.0, "new_year", year=2024),
        _rad(0.0, "new_month", month=1, employed=0, unemployed=10,
             unmatched_jobs=10, active_jobs=10, not_in_labour_force=0),
        _rad(334.0, "new_month", month=12, employed=0, unemployed=10,
             unmatched_jobs=10, active_jobs=10, not_in_labour_force=0),
        _rad(365.0, "new_year", year=2025),
        _rad(365.0, "new_month", month=1, employed=0, unemployed=10,
             unmatched_jobs=10, active_jobs=10, not_in_labour_force=0),
    ])
    _, _, frames, _, _ = spela_upp(d, 10, 20, seed=0)
    assert [(f["year"], f["month"]) for f in frames] == [
        (2024, 1), (2024, 12), (2025, 1)]


def test_start_job_som_inte_blev_nagon_anstallning(tmp_path):
    """handle_start_job returnerar utan att anställa om positionen hunnit
    förstöras eller tas mellan beslut och tillträde. Båda utgångarna loggas
    som start_job och skiljs bara av event_detail."""
    d = str(tmp_path / "run_gone")
    ind, jobb = _skriv_korning(d, n_ind=10)
    ind.loc[1, "job_id"] = "J0000005"
    jobb.loc[5, "individual_id"] = ind.loc[1, "individual_id"]
    ind.to_csv(os.path.join(d, "initial_state_individuals.csv"), index=False)
    jobb.to_csv(os.path.join(d, "initial_state_jobs.csv"), index=False)
    i0, i1 = ind.loc[0, "individual_id"], ind.loc[1, "individual_id"]
    _logg(d, [
        _rad(0.0, "new_month", month=1, year=2020, employed=1, unemployed=9,
             unmatched_jobs=9, active_jobs=10, not_in_labour_force=0),
        # Arbetslös: jobbet var borta, hon förblir arbetslös.
        _rad(10.0, "start_job", agent_type="individual", agent_id=i0,
             chi=1.0, xi=1.0, r_i=0.27, job_id="J0000001",
             event_detail="job_gone_before_start"),
        # Anställd: jobbet var borta, hon behåller sitt gamla.
        _rad(15.0, "start_job", agent_type="individual", agent_id=i1,
             chi=1.0, xi=1.0, r_i=0.27, job_id="J0000002",
             event_detail="job_gone_before_start_kept_previous"),
        _rad(30.0, "new_month", month=2, year=2020, employed=1, unemployed=9,
             unmatched_jobs=9, active_jobs=10, not_in_labour_force=0),
    ])

    _, panel_jobb, frames, ticker, _ = spela_upp(d, 10, 20, seed=0)

    assert sum(frames[1]["workers"]["state"]) == 1
    # Hon som behöll sitt jobb ska fortfarande stå på det, och de jobb som
    # aldrig tillträddes ska inte vara besatta.
    besatta = {jid for jid, st in zip(panel_jobb["job_id"],
                                      frames[1]["jobs"]["state"]) if st == 0}
    assert besatta == {"J0000005"}
    # Och raden hör inte hemma i händelseströmmen: ingen fick något jobb.
    assert ticker == []
