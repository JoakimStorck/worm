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
