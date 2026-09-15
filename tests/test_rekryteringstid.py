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

from scripts.rekryteringstid_mot_uppgiftsrum import (_bokstaver,
                                                     branschernas_position,
                                                     harmonisera,
                                                     las_rekryteringstid)


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
