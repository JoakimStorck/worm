"""Uppgiftsrummets tabell och dess kolumner.

onet_occupation_space hade tre skrivare med två olika kolumnuppsättningar, alla
med if_exists="replace". scripts/load_task_geometry.py skriver den modellen
läser; loader.load_onet_occupation_space och
occupational_profiles.transform_onet_skills_scaled_from_db skrev en
PCA-klustring med helt andra kolumner till samma namn, och den förra anropades
av create_database.py. En körning av databasbygget raderade alltså geometrin.

Att det inte märktes beror på att scenariobuilder.get_geom_for_onet_code
fångar undantag och faller tillbaka på reservvärden. Simuleringen hade inte
stannat -- den hade producerat en körning som ser riktig ut. Testet gör det
till ett rött test i stället.
"""
import sqlite3

import pandas as pd
import pytest

# De kolumner scenariobuilder.get_geom_for_onet_code och
# get_geom_for_onet_codes faktiskt läser ur tabellen.
KRAVDA = {"onet_code", "x_occ", "y_occ", "r_o", "chi", "xi",
          "geom_source", "w_rel", "pi_rel", "r_req"}

# Kolumner som avslöjar att PCA-klustringen skrivit över geometrin.
KLUSTER = {"pc1", "pc2", "cluster_name", "n_clusters", "h"}


def _skriv(db, kolumner, n=3):
    conn = sqlite3.connect(db)
    pd.DataFrame({k: ([0.1] * n if k not in ("onet_code", "geom_source", "Title",
                                             "Job Family", "cluster_name")
                      else ["x"] * n)
                  for k in kolumner}).to_sql("onet_occupation_space", conn,
                                             if_exists="replace", index=False)
    conn.close()


def kolumner(db_path):
    conn = sqlite3.connect(db_path)
    try:
        df = pd.read_sql("SELECT * FROM onet_occupation_space LIMIT 1", conn)
    finally:
        conn.close()
    return set(df.columns)


def test_geometrikolumnerna_kravs(tmp_path):
    db = str(tmp_path / "geom.sqlite3")
    _skriv(db, KRAVDA | {"Title", "Job Family", "n_tasks", "code_system"})
    assert KRAVDA <= kolumner(db)
    assert not (KLUSTER & kolumner(db))


def test_klustertabellen_kanns_igen_som_fel_innehall(tmp_path):
    """Så här såg tabellen ut efter en körning av create_database.py: rätt
    namn, fel innehåll, och inget som stannar en simulering."""
    db = str(tmp_path / "kluster.sqlite3")
    _skriv(db, {"onet_code", "n_clusters", "title", "pc1", "pc2", "cluster",
                "cluster_name", "chi", "xi", "h"})
    k = kolumner(db)
    saknas = KRAVDA - k
    assert "x_occ" in saknas and "r_o" in saknas and "r_req" in saknas
    assert KLUSTER & k


def test_pca_klustringen_skriver_till_eget_tabellnamn():
    """De två PCA-skrivarna får inte längre peka på geometritabellen."""
    import inspect

    from core.database import loader
    from core.occupations import occupational_profiles

    for fn in (loader.load_onet_occupation_space,
               occupational_profiles.transform_onet_skills_scaled_from_db):
        kalla = inspect.getsource(fn)
        assert 'to_sql("onet_occupation_space"' not in kalla, (
            f"{fn.__name__} skriver till geometritabellen")
        assert 'to_sql("onet_skill_clusters"' in kalla


def test_create_database_bygger_inte_uppgiftsrummet():
    """Databasbygget ska inte röra tabellen alls. Den laddas separat med
    scripts/load_task_geometry.py --write."""
    import os
    rot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    kalla = open(os.path.join(rot, "scripts", "create_database.py"),
                 encoding="utf-8").read()
    assert "loader.load_onet_occupation_space(" not in kalla
    assert "load_task_geometry" in kalla
