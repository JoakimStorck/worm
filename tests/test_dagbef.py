"""Läsaren för TAB4436 (core/database/load_dagbef.py), mot en fil i det
format fetch_data.py skriver."""
import pytest

from core.database.load_dagbef import las_dagbef_yrke_bransch

RUBRIK = '"Region","Yrke2012","SNI2007","Kon","Tid","000006XZ"\n'


def _fil(tmp_path, rader, rubrik=RUBRIK):
    p = tmp_path / "dagbef.csv"
    p.write_text(rubrik + "".join(f'"{r}","{y}","{s}","{k}","2024",{n}\n'
                                  for r, y, s, k, n in rader), encoding="utf-8")
    return p


def test_kommunnivan_valjs_och_ovriga_nivaer_slapps(tmp_path):
    """Regionerna är en hierarki utan totalrader. Riket, länet och kommunen
    bär samma anställda; summeras nivåerna räknas varje person tre gånger."""
    rader = [("00", "532", "Q", "1", 30), ("20", "532", "Q", "1", 30),
             ("2062", "532", "Q", "1", 20), ("2034", "532", "Q", "1", 10),
             ("99", "532", "Q", "1", 3), ("9999", "532", "Q", "1", 3)]
    df = las_dagbef_yrke_bransch(_fil(tmp_path, rader))
    assert sorted(df["municipal_code"]) == ["2034", "2062"]
    assert df["employed"].sum() == 30


def test_restposter_behalls_och_nollor_slapps(tmp_path):
    rader = [("2062", "0002", "Q", "1", 4), ("2062", "532", "00", "2", 2),
             ("2062", "532", "Q", "2", 0)]
    df = las_dagbef_yrke_bransch(_fil(tmp_path, rader))
    assert set(zip(df.ssyk_code, df.sni_code)) == {("0002", "Q"), ("532", "00")}
    assert set(df["year"]) == {2024}
    assert set(df["sex"]) == {"1", "2"}


def test_fel_rubrik_kastar(tmp_path):
    fel = '"Region","Yrke2012","SNI2007","Tid","000006XZ","extra"\n'
    with pytest.raises(ValueError, match="Kon"):
        las_dagbef_yrke_bransch(_fil(tmp_path, [], rubrik=fel))
