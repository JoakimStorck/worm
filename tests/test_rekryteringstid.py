"""Rekryteringstid mot position i uppgiftsrummet.

Modellen säger att specialiserade yrken är svårare att fylla: en
kompetenscirkel av given radie täcker färre jobb längre ut i rummet. SCB mäter
rekryteringstiden per näringsgren utan att känna till uppgiftsrummet, så ett
samband är en oberoende bekräftelse och inte en kalibrering.

SCB:s tal är Littles lag, inte en uppmätt varaktighet: genomsnittlig
rekryteringstid definieras som antalet lediga jobb i relation till antalet
nyanställningar (kvalitetsdeklaration AM0701, avsnitt 1.2.2). 81 dagar för IT
betyder därför inte att en IT-rekrytering tar längre tid, utan att branschen
bär fler öppna tjänster per anställning.
"""
import sqlite3

import numpy as np
import pandas as pd
import pytest

from scripts.rekryteringstid_mot_uppgiftsrum import (_bokstaver, anpassa_ytor,
                                                     branschernas_position,
                                                     designmatris, harmonisera,
                                                     las_rekryteringstid,
                                                     yrkesvikter_per_bransch)


def _scbfil(path, per_bransch, ar="2023", kodning="iso-8859-1"):
    rader = []
    for etikett, dagar in per_bransch.items():
        for k in (1, 2, 3, 4):
            rader.append({"näringsgren SNI 2007": etikett, "kvartal": f"{ar}K{k}",
                          "tabellinnehåll": "Rekryteringstid",
                          "Rekryteringstid, genomsnittlig i månader":
                              round(dagar / 30.44, 3)})
            rader.append({"näringsgren SNI 2007": etikett, "kvartal": f"{ar}K{k}",
                          "tabellinnehåll": "Felmarignal",
                          "Rekryteringstid, genomsnittlig i månader": 0.1})
    pd.DataFrame(rader).to_csv(path, index=False, quoting=1, encoding=kodning)


# ---------------------------------------------------------------------------
# Läsaren
# ---------------------------------------------------------------------------
def test_manader_blir_dagar(tmp_path):
    p = str(tmp_path / "scb.csv")
    _scbfil(p, {"I hotell och restauranger": 12.0})
    d = las_rekryteringstid(p)
    assert d.dagar.iloc[0] == pytest.approx(12.0, abs=0.5)


def test_felmarginalen_raknas_inte_med(tmp_path):
    """Kolumnen tabellinnehåll har två värden, Rekryteringstid och
    Felmarignal. Summeras båda halveras talet."""
    p = str(tmp_path / "scb.csv")
    _scbfil(p, {"F byggindustri": 33.0})
    assert las_rekryteringstid(p).dagar.iloc[0] == pytest.approx(33.0, abs=0.5)


def test_sni_kod_med_plustecken(tmp_path):
    p = str(tmp_path / "scb.csv")
    _scbfil(p, {"B+C tillverkningsindustri; gruvor": 47.0,
                "P+Q enheter inom utbildning, vård och omsorg": 25.0})
    d = las_rekryteringstid(p).set_index("sni_code")
    assert set(d.index) == {"B+C", "P+Q"}


def test_fel_ar_kastar(tmp_path):
    p = str(tmp_path / "scb.csv")
    _scbfil(p, {"F byggindustri": 33.0}, ar="2023")
    with pytest.raises(ValueError):
        las_rekryteringstid(p, ar="2019")


# ---------------------------------------------------------------------------
# Harmoniseringen
# ---------------------------------------------------------------------------
def test_bokstaver():
    assert _bokstaver("M+N") == {"M", "N"}
    assert _bokstaver("R+S+T+U") == {"R", "S", "T", "U"}
    assert _bokstaver("B+C") == {"B", "C"}


def _tid(rader):
    return pd.DataFrame([{"sni_code": k, "dagar": v, "etikett": k}
                         for k, v in rader.items()])


def _pos(rader):
    return pd.DataFrame([{"sni_code": k, "chi": c, "r_o": 0.3, "r_req": c * 0.8,
                          "syss": n, "n_yrken": 3, "tackning": 1.0}
                         for k, (c, n) in rader.items()])


def test_grovre_grupp_pa_ena_sidan_slas_ihop():
    """TAB4307 har P+Q; yrkesregistret har P och Q var för sig. En ren
    strängmatchning tappar vård och utbildning tyst -- den bransch som betyder
    mest i en glesbygdskommun."""
    d = harmonisera(_tid({"P+Q": 25.0}), _pos({"P": (0.30, 1000), "Q": (0.20, 3000)}))
    assert len(d) == 1
    # Positionen vägs med sysselsättningen: Q är tre gånger så stor.
    assert d.chi.iloc[0] == pytest.approx((0.30 * 1000 + 0.20 * 3000) / 4000)
    assert d.dagar.iloc[0] == pytest.approx(25.0)


def test_grovre_grupp_pa_andra_sidan_slas_ihop():
    """TAB4307 har M och N var för sig; yrkesregistret har M+N. Då är det
    rekryteringstiden som ska vägas ihop."""
    d = harmonisera(_tid({"M": 68.0, "N": 31.0}), _pos({"M+N": (0.50, 2000)}))
    assert len(d) == 1
    # Ovägt hade gett 49.5; här väger båda lika eftersom de delar en enda
    # positionsgrupp.
    assert d.dagar.iloc[0] == pytest.approx(49.5)
    assert d.n_kallgrupper.iloc[0] == 2


def test_identiska_grupper_lamnas_i_fred():
    d = harmonisera(_tid({"F": 33.0, "I": 12.0}),
                    _pos({"F": (0.38, 1000), "I": (0.16, 1000)}))
    assert len(d) == 2
    assert set(d.grupp) == {"F", "I"}


def test_ingen_grupp_forsvinner():
    """Varje källgrupp ska hamna i exakt en jämförbar grupp."""
    tid = _tid({"P+Q": 25.0, "K+L": 40.0, "M": 68.0, "N": 31.0, "I": 12.0})
    pos = _pos({"P": (0.30, 900), "Q": (0.20, 3000), "K": (0.55, 400),
                "L": (0.45, 300), "M+N": (0.50, 2000), "I": (0.16, 1200)})
    d = harmonisera(tid, pos)
    bokstaver = set()
    for g in d.grupp:
        bokstaver |= _bokstaver(g)
    assert bokstaver == set("PQKLMNI")


# ---------------------------------------------------------------------------
# Hela mätningen
# ---------------------------------------------------------------------------
def _db(tmp_path, mix, chi_per_yrke):
    db = str(tmp_path / "t.sqlite3")
    conn = sqlite3.connect(db)
    pd.DataFrame([{"ssyk_code": y, "sni_code": s, "employed": n}
                  for s, m in mix.items() for y, n in m.items()]
                 ).to_sql("occupation_by_industry", conn, index=False)
    pd.DataFrame([{"occupation_code": y, "onet_code": f"O{y}", "share": 1.0}
                  for y in chi_per_yrke]
                 ).to_sql("ssyk3_onet_crosswalk", conn, index=False)
    pd.DataFrame([{"onet_code": f"O{y}", "chi": c, "xi": 1.0, "r_o": 0.3,
                   "r_req": c * 0.8, "Job Family": "x"}
                  for y, c in chi_per_yrke.items()]
                 ).to_sql("onet_occupation_space", conn, index=False)
    conn.close()
    return db


def test_branschens_position_vags_med_sysselsattningen(tmp_path):
    db = _db(tmp_path, {"F": {"a": 900, "b": 100}}, {"a": 0.20, "b": 0.80})
    conn = sqlite3.connect(db)
    pos = branschernas_position(conn)
    conn.close()
    assert pos.chi.iloc[0] == pytest.approx(0.26)


def test_planterat_samband_aterfinns(tmp_path):
    """Kontrollen att mätningen mäter rätt sak: med rekryteringstiden satt
    proportionell mot chi ska Spearman bli 1."""
    chi = {"a": 0.15, "b": 0.30, "c": 0.50, "d": 0.75}
    db = _db(tmp_path, {"I": {"a": 1000}, "F": {"b": 1000},
                        "B+C": {"c": 1000}, "J": {"d": 1000}}, chi)
    conn = sqlite3.connect(db)
    pos = branschernas_position(conn)
    conn.close()
    tid = _tid({"I": 12.0, "F": 30.0, "B+C": 50.0, "J": 75.0})
    d = harmonisera(tid, pos).sort_values("chi")
    rho = d["chi"].corr(d["dagar"], method="spearman")
    assert rho == pytest.approx(1.0)


def test_inget_samband_ger_ingen_korrelation(tmp_path):
    """Och motsatsen: slumpmässiga tider ska inte ge ett samband."""
    chi = {"a": 0.15, "b": 0.30, "c": 0.50, "d": 0.75}
    db = _db(tmp_path, {"I": {"a": 1000}, "F": {"b": 1000},
                        "B+C": {"c": 1000}, "J": {"d": 1000}}, chi)
    conn = sqlite3.connect(db)
    pos = branschernas_position(conn)
    conn.close()
    tid = _tid({"I": 50.0, "F": 12.0, "B+C": 75.0, "J": 30.0})
    d = harmonisera(tid, pos)
    assert abs(d["chi"].corr(d["dagar"], method="spearman")) < 0.9


# ---------------------------------------------------------------------------
# Ytorna
# ---------------------------------------------------------------------------
def _yrken(rader):
    """En rad per bransch och yrke, med vikt och position."""
    d = pd.DataFrame(rader)
    d["x_occ"] = d.chi * np.cos(d.xi)
    d["y_occ"] = d.chi * np.sin(d.xi)
    d["r_o"] = 0.3
    return d


def test_branschen_bidrar_med_sin_fordelning_inte_sin_tyngdpunkt():
    """Kärnan i konstruktionen: raden i designmatrisen är ett vägt MEDELVÄRDE
    av basfunktionen över branschens yrken. Två branscher med samma tyngdpunkt
    men olika spridning ger därför olika rader för en olinjär basfunktion."""
    smal = _yrken([{"grupp": "A", "chi": 0.5, "xi": 0.0, "v": 1.0, "r_req": 0.4},
                   {"grupp": "A", "chi": 0.5, "xi": 0.0, "v": 1.0, "r_req": 0.4}])
    bred = _yrken([{"grupp": "B", "chi": 0.1, "xi": 0.0, "v": 1.0, "r_req": 0.4},
                   {"grupp": "B", "chi": 0.9, "xi": 0.0, "v": 1.0, "r_req": 0.4}])
    d = pd.concat([smal, bred], ignore_index=True)
    bas = lambda t: {"1": np.ones(len(t)), "chi2": t["chi"] ** 2}  # noqa: E731
    M, namn = designmatris(d, ["A", "B"], bas)
    # Samma tyngdpunkt i chi...
    Mlin, _ = designmatris(d, ["A", "B"], lambda t: {"chi": t["chi"]})
    assert Mlin[0, 0] == pytest.approx(Mlin[1, 0])
    # ...men olika rad för chi^2.
    assert M[0, 1] == pytest.approx(0.25)
    assert M[1, 1] == pytest.approx(0.41)


def test_vikterna_normaliseras_per_bransch():
    """Utan normalisering hade en stor bransch predicerat en längre tid bara
    för att den är stor."""
    d = _yrken([{"grupp": "A", "chi": 0.4, "xi": 0.0, "v": 1.0, "r_req": 0.4},
                {"grupp": "B", "chi": 0.4, "xi": 0.0, "v": 9000.0, "r_req": 0.4}])
    M, _ = designmatris(d, ["A", "B"], lambda t: {"chi": t["chi"]})
    assert M[0, 0] == pytest.approx(M[1, 0])


def test_planterad_radiell_yta_aterfinns():
    rng = np.random.default_rng(0)
    rader, matt = [], []
    for i, c in enumerate([0.15, 0.25, 0.40, 0.55, 0.70, 0.85]):
        g = f"G{i}"
        for d_ in (-0.05, 0.0, 0.05):
            rader.append({"grupp": g, "chi": c + d_, "xi": rng.uniform(0, 6.28),
                          "v": 1.0, "r_req": c})
        matt.append({"grupp": g, "dagar": 10 + 80 * c})
    r = anpassa_ytor(_yrken(rader), pd.DataFrame(matt))
    bast = {x["yta"]: x for x in r}
    assert bast["radiell"]["R2"] > 0.99
    assert bast["radiell"]["koef"]["chi"] == pytest.approx(80, abs=5)


def test_konstant_yta_ger_noll_r2():
    """Baslinjen: en yta utan struktur ska ge R2 = 0, inte något annat."""
    rader = [{"grupp": g, "chi": c, "xi": 0.0, "v": 1.0, "r_req": c}
             for g, c in (("A", 0.2), ("B", 0.5), ("C", 0.8))]
    matt = pd.DataFrame([{"grupp": "A", "dagar": 10.0},
                         {"grupp": "B", "dagar": 40.0},
                         {"grupp": "C", "dagar": 70.0}])
    r = {x["yta"]: x for x in anpassa_ytor(_yrken(rader), matt)}
    assert r["konstant"]["R2"] == pytest.approx(0.0, abs=1e-9)


def test_korsvalideringen_ar_utelamna_en_och_inte_insample():
    """R2 kan bara växa med fler parametrar, så cv_rmse behövs som motvikt.
    Måttet måste vara UTELÄMNA-EN: anpassa på tio, predicera den elfte. Räknas
    det i stället på samma data som anpassningen mäter det ingenting, och den
    största modellen vinner alltid.

    Kontrollen är därför att cv_rmse ligger ÖVER residualernas
    in-sample-spridning -- en utelämnad punkt predikteras sämre än en
    inkluderad -- och inte att en viss modell vinner, vilket beror på draget.
    """
    rng = np.random.default_rng(3)
    rader, matt = [], []
    for i, c in enumerate(np.linspace(0.15, 0.85, 7)):
        g = f"G{i}"
        for d_ in (-0.03, 0.0, 0.03):
            rader.append({"grupp": g, "chi": c + d_, "xi": rng.uniform(0, 6.28),
                          "v": 1.0, "r_req": c})
        matt.append({"grupp": g, "dagar": 10 + 80 * c + rng.normal(0, 12)})
    r = {x["yta"]: x for x in anpassa_ytor(_yrken(rader), pd.DataFrame(matt))}
    for namn in ("radiell", "radiell + plan"):
        res = np.array(list(r[namn]["residual"].values()), dtype=float)
        insample = float(np.sqrt(np.mean(res ** 2)))
        assert r[namn]["cv_rmse"] > insample, namn
    # Och R2 växer monotont med parametrarna, vilket är skälet till motvikten.
    assert r["radiell + plan"]["R2"] >= r["radiell"]["R2"] - 1e-9


# ---------------------------------------------------------------------------
# Modellens egen harmonik, ur körningen
# ---------------------------------------------------------------------------
def _korning(tmp_path, topp_grader, amplitud, n=400, brus=6.0, seed=1):
    """Syntetisk körning: jobb spridda över skivan, vakansålder vid
    tillsättning som en planterad första harmonik plus brus."""
    import os

    rng = np.random.default_rng(seed)
    R = str(tmp_path / "run")
    os.makedirs(R)
    xi = rng.uniform(0, 2 * np.pi, n)
    chi = rng.uniform(0.1, 0.7, n)
    jobb = pd.DataFrame({"job_id": [f"J{i:05d}" for i in range(n)],
                         "xi": xi, "chi": chi,
                         "x_occ": chi * np.cos(xi), "y_occ": chi * np.sin(xi)})
    jobb.to_csv(os.path.join(R, "initial_state_jobs.csv"), index=False)
    t = np.radians(topp_grader)
    T = 40 + chi * amplitud * np.cos(xi - t) + rng.normal(0, brus, n)
    rader = ["0.00, new_month, month 1, year 2024, employed 0, unemployed 0, "
             "unmatched_jobs 0, active_jobs 0"]
    for i, (j, v) in enumerate(zip(jobb.job_id, T)):
        rader.append(f"{10 + i:.2f}, start_job, agent_type individual, "
                     f"agent_id 2062_i{i:06d}, chi 1.0, xi 1.0, r_i 0.3, "
                     f"job_id {j}, is_bootstrap False, "
                     f"vacancy_age_days {max(v, 1):.1f}")
    with open(os.path.join(R, "eventlog.csv"), "w", encoding="utf-8") as f:
        f.write("\n".join(rader) + "\n")
    return R


def test_toppriktningen_aterfinns(tmp_path):
    from scripts.analysis import riktningsharmonik

    r = riktningsharmonik(_korning(tmp_path, 90.0, 120.0))
    assert abs(((r["topp"] - 90.0 + 180) % 360) - 180) < 5
    assert r["R2"] > 0.85
    assert r["R2_radiell"] < 0.1       # ingen riktning i chi ensamt


def test_en_annan_toppriktning_aterfinns_ocksa(tmp_path):
    """Testet får inte råka bli grönt bara för att 90 grader är svaret vi
    väntar oss."""
    from scripts.analysis import riktningsharmonik

    r = riktningsharmonik(_korning(tmp_path, 225.0, 120.0))
    assert abs(((r["topp"] - 225.0 + 180) % 360) - 180) < 5


def test_bootstrap_och_misslyckade_starter_raknas_inte(tmp_path):
    """Uppstartens tillsättningar har ingen vakansålder som betyder något,
    och job_gone_before_start-raderna är inga anställningar (0118)."""
    import os

    from scripts.analysis import riktningsharmonik

    R = _korning(tmp_path, 90.0, 120.0, n=200)
    with open(os.path.join(R, "eventlog.csv"), "a", encoding="utf-8") as f:
        for i in range(300):
            f.write(f"{1000 + i:.2f}, start_job, agent_type individual, "
                    f"agent_id x{i}, chi 1.0, xi 1.0, r_i 0.3, job_id J00001, "
                    f"is_bootstrap True, vacancy_age_days 900\n")
            f.write(f"{2000 + i:.2f}, start_job, agent_type individual, "
                    f"agent_id y{i}, chi 1.0, xi 1.0, r_i 0.3, job_id J00002, "
                    f"event_detail job_gone_before_start, vacancy_age_days 900\n")
    r = riktningsharmonik(R)
    assert r["n"] == 200
    assert r["medel"] < 100


def test_for_fa_tillsattningar_ger_none(tmp_path):
    from scripts.analysis import riktningsharmonik

    assert riktningsharmonik(_korning(tmp_path, 90.0, 120.0, n=10)) is None


# ---------------------------------------------------------------------------
# Misslyckade rekryteringar
# ---------------------------------------------------------------------------
def _korning_med_svans(tmp_path, n_gamla=40, n_lediga=100, n=300, t_slut=3650.0):
    """Slutläge där n_gamla av n_lediga lediga positioner är äldre än 180
    dagar, med högre krav och norrut i rummet, och hälften av dem aldrig fått
    en sökande."""
    import os

    R = str(tmp_path / "run")
    os.makedirs(R)
    jobb = pd.DataFrame({
        "job_id": [f"J{i:05d}" for i in range(n)],
        "individual_id": [None if i < n_lediga else f"i{i}" for i in range(n)],
        "active": True, "pending": False,
        "vacant_since": [t_slut - 400 if i < n_gamla else t_slut - 30 for i in range(n)],
        "r_req": [0.6 if i < n_gamla else 0.3 for i in range(n)],
        "y_occ": [0.3 if i < n_gamla else -0.2 for i in range(n)],
        "municipal_code": ["2039" if i < 30 else "2062" for i in range(n)],
        "employer_size": [8] * n})
    jobb.to_csv(os.path.join(R, "final_state_jobs.csv"), index=False)
    rader = [f"{t_slut:.2f}, new_month, month 12, year 2033, employed 200, "
             "unemployed 10, unmatched_jobs 100, active_jobs 300"]
    for i in range(n_gamla // 2, n_gamla):      # hälften har fått sökande
        rader.append(f"100.00, open_advert, agent_type system, agent_id None, "
                     f"event_detail advert_opened, job_id J{i:05d}, "
                     f"wait_first_applicant_days 5")
        for k in range(3):
            rader.append(f"{200 + k * 50}.00, close_vacancy, agent_type individual, "
                         f"agent_id x, event_detail vacancy_closed_unfilled, "
                         f"job_id J{i:05d}")
    with open(os.path.join(R, "eventlog.csv"), "w", encoding="utf-8") as f:
        f.write("\n".join(rader) + "\n")
    return R


def test_svansen_raknas(tmp_path):
    from scripts.analysis import misslyckade_rekryteringar

    r = misslyckade_rekryteringar(_korning_med_svans(tmp_path))
    assert r["n_lediga"] == 100 and r["n_lang"] == 40
    assert r["andel_lang"] == pytest.approx(0.4)
    assert r["alder_median_lang"] == pytest.approx(400.0)


def test_aldrig_sokta_och_tomma_fonster(tmp_path):
    """Skiljer positioner som ingen söker från positioner som söks men inte
    fylls. De två kräver olika åtgärder."""
    from scripts.analysis import misslyckade_rekryteringar

    r = misslyckade_rekryteringar(_korning_med_svans(tmp_path))
    assert r["aldrig_sokt_lang"] == pytest.approx(0.5)
    # Hälften har tre tomma fönster, hälften noll: medianen ligger emellan.
    assert 0 < r["tomma_median_lang"] < 3


def test_kravniva_och_riktning_for_svansen(tmp_path):
    from scripts.analysis import misslyckade_rekryteringar

    r = misslyckade_rekryteringar(_korning_med_svans(tmp_path))
    assert r["r_req_lang"] == pytest.approx(0.6)
    assert r["r_req_kort"] == pytest.approx(0.3)
    assert r["andel_norr_lang"] == pytest.approx(1.0)
    assert r["andel_norr_alla"] == pytest.approx(0.4)


def test_per_kommun_mot_kommunens_egen_stock(tmp_path):
    from scripts.analysis import misslyckade_rekryteringar

    r = misslyckade_rekryteringar(_korning_med_svans(tmp_path))
    assert r["per_kommun"] == {"2039": 30, "2062": 10}
    assert r["stock_per_kommun"]["2039"] == 30       # alla Älvdalens lediga är gamla
    assert r["stock_per_kommun"]["2062"] == 70


def test_utan_lediga_positioner_ger_none(tmp_path):
    import os

    from scripts.analysis import misslyckade_rekryteringar

    R = str(tmp_path / "run")
    os.makedirs(R)
    pd.DataFrame({"job_id": ["J1"], "individual_id": ["i1"], "active": True,
                  "pending": False, "vacant_since": [0.0]}
                 ).to_csv(os.path.join(R, "final_state_jobs.csv"), index=False)
    with open(os.path.join(R, "eventlog.csv"), "w") as f:
        f.write("10.00, new_month, month 1\n")
    assert misslyckade_rekryteringar(R) is None
