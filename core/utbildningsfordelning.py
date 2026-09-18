"""P(yrke, nivå, inriktning | ålder, kön) för anställda, genom raking av tre
tvåvägsmarginaler (docs/utbildningsmodell.md, "Data för dragningen", steg 4b).

MARGINALERNA.
    yrke x inriktning   TAB4359, anställda, femårsklasser    (exakt)
    yrke x nivå         TAB4360, samma anställda              (exakt)
    nivå x inriktning   TAB655, BEFOLKNINGEN, tioårsklasser  (form)

DEN TREDJE ÄR EN FORM, INTE EN MARGINAL. TAB655 räknar hela befolkningen, och
dess nivå- och inriktningstotaler skiljer sig från de anställdas, som de två
andra tabellerna redan bestämmer. Med motstridiga marginaler konvergerar
IPF inte; den pendlar. Därför tas bara sambandet ur TAB655 -- oddskvoterna
mellan nivå och inriktning -- genom att tabellen först anpassas med
tvådimensionell IPF till de anställdas nivå- och inriktningstotaler. Det
bevarar dess strukturella nollor: förgymnasial nivå har bara allmän
inriktning, och uppgift saknas på nivå går ihop med okänd inriktning.

ÅLDERSKLASSERNA. De anställdas femårsklass får TAB655:s tioårsklass som
innehåller den: 25-29 och 30-34 får 25-34, och så vidare; 65-69 får 65-74.
16-24 är samma i båda. Nationell bakgrund summeras.

Det raking inte kan veta är trevägssamspelet utöver marginalerna: om
vårdutbildade med kort eftergymnasial utbildning hamnar i andra yrken än
vårdutbildade med lång. Den skillnaden finns bara i det som marginalerna
bär.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TIOARSKLASS = {"16-24": "16-24", "25-29": "25-34", "30-34": "25-34",
               "35-39": "35-44", "40-44": "35-44", "45-49": "45-54",
               "50-54": "45-54", "55-59": "55-64", "060-64": "55-64",
               "60-64": "55-64", "065-69": "65-74", "65-69": "65-74"}
HAMTA = ("Utbildningstabellerna saknas. Hämta med python scripts/fetch_data.py "
         "--only \"Anstallda yrke utbildning\" och --only \"Befolkning utbildning\", "
         "och kör python scripts/create_database.py.")


def ipf_2d(form, rader, kolumner, tol=1e-9, max_iter=1000):
    """Anpassar form (l x f) till rad- och kolumnsummorna med bevarade
    oddskvoter. Totalerna måste vara lika."""
    x = np.asarray(form, dtype=float).copy()
    rader, kolumner = np.asarray(rader, float), np.asarray(kolumner, float)
    if not np.isclose(rader.sum(), kolumner.sum(), rtol=1e-9):
        raise ValueError(f"radsummorna {rader.sum()} och kolumnsummorna "
                         f"{kolumner.sum()} har olika total")
    for _ in range(max_iter):
        rs = x.sum(axis=1)
        x *= np.divide(rader, rs, out=np.zeros_like(rs), where=rs > 0)[:, None]
        ks = x.sum(axis=0)
        x *= np.divide(kolumner, ks, out=np.zeros_like(ks), where=ks > 0)[None, :]
        if np.abs(x.sum(axis=1) - rader).max() <= tol * max(rader.sum(), 1.0):
            break
    return x


def raka(m_of, m_ol, m_lf, tol=1e-7, max_iter=2000):
    """Tredimensionell IPF: X[o, l, f] med marginalerna m_of (o x f), m_ol
    (o x l) och m_lf (l x f). Returnerar (X, största relativa avvikelse per
    marginal)."""
    m_of, m_ol, m_lf = (np.asarray(m, float) for m in (m_of, m_ol, m_lf))
    x = np.ones((m_ol.shape[0], m_ol.shape[1], m_of.shape[1]))
    tot = m_of.sum()

    def skala(x, mal, axel):
        nu = x.sum(axis=axel)
        f = np.divide(mal, nu, out=np.zeros_like(nu), where=nu > 0)
        return x * np.expand_dims(f, axel)

    for _ in range(max_iter):
        x = skala(x, m_of, 1)
        x = skala(x, m_ol, 2)
        x = skala(x, m_lf, 0)
        fel = (np.abs(x.sum(axis=1) - m_of).max(), np.abs(x.sum(axis=2) - m_ol).max(),
               np.abs(x.sum(axis=0) - m_lf).max())
        if max(fel) <= tol * max(tot, 1.0):
            break
    return x, tuple(float(e) / max(tot, 1.0) for e in fel)


def bygg_fordelning(conn, ar=None):
    """Den rakade fördelningen för alla ålders- och könsklasser, i långt
    format: age_class, sex, ssyk_code, level, field, employed (skattat, ej
    heltal). Nollceller släpps. Kastar om tabellerna saknas."""
    for t in ("employment_occupation_field", "employment_occupation_level",
              "population_level_field"):
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (t,)).fetchone() is None:
            raise ValueError(f"Tabellen {t} saknas. " + HAMTA)
    of = pd.read_sql("SELECT * FROM employment_occupation_field", conn)
    ol = pd.read_sql("SELECT * FROM employment_occupation_level", conn)
    lf = pd.read_sql("SELECT * FROM population_level_field", conn)
    if of.empty or ol.empty or lf.empty:
        raise ValueError("En av utbildningstabellerna är tom. " + HAMTA)
    if ar is None:
        ar = int(of["year"].max())
    of, ol, lf = (d[d["year"] == ar] for d in (of, ol, lf))
    yrken = sorted(set(of.ssyk_code) | set(ol.ssyk_code))
    nivaer = sorted(set(ol.level) | set(lf.level))
    inr = sorted(set(of.field) | set(lf.field))

    ut, diagnos = [], []
    for (alder, kon), g_of in of.groupby(["age_class", "sex"]):
        tio = TIOARSKLASS.get(alder)
        if tio is None:
            raise ValueError(f"Åldersklassen {alder} har ingen tioårsklass i TAB655.")
        g_ol = ol[(ol.age_class == alder) & (ol.sex == kon)]
        g_lf = lf[(lf.age_class == tio) & (lf.sex == kon)]
        if g_lf.empty:
            raise ValueError(f"TAB655 saknar {tio}, kön {kon}. " + HAMTA)
        M_of = g_of.pivot_table(index="ssyk_code", columns="field", values="employed",
                                aggfunc="sum").reindex(index=yrken, columns=inr).fillna(0).to_numpy()
        M_ol = g_ol.pivot_table(index="ssyk_code", columns="level", values="employed",
                                aggfunc="sum").reindex(index=yrken, columns=nivaer).fillna(0).to_numpy()
        form = g_lf.pivot_table(index="level", columns="field", values="population",
                                aggfunc="sum").reindex(index=nivaer, columns=inr).fillna(0).to_numpy()
        M_lf = ipf_2d(form, M_ol.sum(axis=0), M_of.sum(axis=0))
        X, fel = raka(M_of, M_ol, M_lf)
        diagnos.append({"age_class": alder, "sex": kon, "employed": float(M_of.sum()),
                        "fel_of": fel[0], "fel_ol": fel[1], "fel_lf": fel[2]})
        o, l, f = np.nonzero(X > 0)
        ut.append(pd.DataFrame({"age_class": alder, "sex": kon,
                                "ssyk_code": np.asarray(yrken)[o],
                                "level": np.asarray(nivaer)[l],
                                "field": np.asarray(inr)[f],
                                "employed": X[o, l, f]}))
    return pd.concat(ut, ignore_index=True), pd.DataFrame(diagnos)
