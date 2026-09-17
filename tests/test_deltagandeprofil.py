"""Deltagandeprofilen: data upp till 65, antagande däröver.

BAS publicerar inte klasserna över 65 år på kommunnivå -- 16-66, 65-69 och
70-74 är tomma i alla 290 kommuner, alla år och båda tabellerna. Profilen
byggs därför av femårsgrupperna plus 65 år ur differensen mellan aggregaten,
och ovanför 65 av ett antagande med riktåldern som parameter.
"""
import numpy as np
import pandas as pd
import pytest

from core.participation import (GRUPPER, grupptal, profil, utträdeshasard)


BEF_PER_ALDER = 250.0


def _rader(q_per_grupp=None, a65=149.0, n65=BEF_PER_ALDER, med_aggregat=True,
           bef_per_alder=BEF_PER_ALDER):
    """En kommuns rader i labour_force_by_age. Deltagandet per grupp följer
    en rimlig svensk profil: lågt bland de yngsta, högt i mitten, fallande
    mot slutet.

    Gruppens befolkning sätts till pyramidens summa över samma åldrar. De två
    källorna avgränsar nästan lika i verkligheten, och en testdata där de
    skiljer sig gör q till något annat än deltagandegrad."""
    standard = {"16-19": 0.30, "20-24": 0.73, "25-29": 0.85, "30-34": 0.88,
                "35-39": 0.90, "40-44": 0.90, "45-49": 0.90, "50-54": 0.89,
                "55-59": 0.86, "60-64": 0.70}
    q = dict(standard, **(q_per_grupp or {}))
    rader = []
    for namn, lo, hi in GRUPPER:
        n = bef_per_alder * (hi - lo + 1)
        rader.append({"age_group": namn, "in_labour_force": q[namn] * n,
                      "total": n})
    if med_aggregat:
        bas_a, bas_n = 9000.0, 12000.0
        rader.append({"age_group": "16-64", "in_labour_force": bas_a,
                      "total": bas_n})
        rader.append({"age_group": "16-65", "in_labour_force": bas_a + a65,
                      "total": bas_n + n65})
    return pd.DataFrame(rader)


def _befolkning(per_alder=BEF_PER_ALDER):
    return pd.Series({a: per_alder for a in range(16, 80)})


# ----------------------------------------------------------------------
# Grupperna och 65 år
# ----------------------------------------------------------------------

def test_sextiofemaringarna_ur_differensen():
    """Den enda vägen till 65 år: 16-65 minus 16-64. Klassen 65-69 är tom på
    kommunnivå."""
    g = dict((namn, (a, n)) for namn, _, _, a, n in grupptal(_rader()))
    assert g["65"] == (149.0, 250.0)


def test_negativ_differens_nollas():
    """Röjandeskyddet gör att redovisade totaler inte alltid är lika med
    summan av delarna, så differensen kan bli negativ i en liten kommun."""
    g = dict((namn, (a, n)) for namn, _, _, a, n in grupptal(_rader(a65=-12.0)))
    assert g["65"][0] == 0.0


def test_saknad_grupp_kastar():
    r = _rader()
    with pytest.raises(ValueError, match="30-34"):
        grupptal(r[r.age_group != "30-34"])


# ----------------------------------------------------------------------
# Profilen
# ----------------------------------------------------------------------

def test_gruppens_arbetskraft_bevaras():
    """En interpolation som inte bevarar gruppsumman ändrar arbetskraftens
    storlek, och då stämmer modellen inte längre mot SCB."""
    r = _rader()
    N = _befolkning()
    q = profil(r, N)
    for namn, lo, hi in GRUPPER:
        rad = r[r.age_group == namn].iloc[0]
        summa = sum(q[a] * N[a] for a in range(lo, hi + 1))
        assert summa == pytest.approx(float(rad["in_labour_force"]), rel=1e-6)


def test_de_yngsta_deltar_minst():
    """Formen ska överleva interpolationen: de yngsta lägst, mitten högst."""
    q = profil(_rader(), _befolkning())
    assert q[16] < q[25] and q[17] < q[30]
    assert q[40] == pytest.approx(0.90, abs=0.03)
    assert q[62] < q[45]


def test_sextiofem_kommer_fran_data_inte_interpolation():
    """Differensen ska slå igenom även när den avviker kraftigt från vad
    kurvan hade gett."""
    q = profil(_rader(a65=40.0, n65=250.0), _befolkning())
    assert q[65] == pytest.approx(40.0 / 250.0)


def test_antagandet_ansluter_till_data_vid_65():
    """Kurvan ska vara kontinuerlig i skarven: inget hopp mellan sista mätta
    åldern och första antagna."""
    q = profil(_rader(), _befolkning(), retirement_age=67.0,
               retirement_spread=0.8)
    assert q[66] < q[65]
    assert q[66] > 0.3 * q[65]


def test_riktaldern_flyttar_kurvan():
    """Hela poängen med att göra antagandet explicit: riktåldern ska gå att
    svepa."""
    lag = profil(_rader(), _befolkning(), retirement_age=65.0)
    hog = profil(_rader(), _befolkning(), retirement_age=70.0)
    assert hog[68] > lag[68]
    assert hog[67] > hog[70]


def test_bredden_styr_hur_skarp_overgangen_ar():
    skarp = profil(_rader(), _befolkning(), retirement_age=67.0,
                   retirement_spread=0.3)
    mjuk = profil(_rader(), _befolkning(), retirement_age=67.0,
                  retirement_spread=2.0)
    assert skarp[69] < mjuk[69]


def test_deltagandet_ligger_mellan_noll_och_ett():
    q = profil(_rader(q_per_grupp={"40-44": 0.99}, bef_per_alder=10.0),
               _befolkning(per_alder=10.0))
    assert (q >= 0).all() and (q <= 1).all()


# ----------------------------------------------------------------------
# Hasarden
# ----------------------------------------------------------------------

def test_hasarden_foljer_fallet():
    """Faller deltagandet från q(a) till q(a+1) har andelen 1 - q(a+1)/q(a)
    av dem som var kvar lämnat."""
    q = pd.Series({60: 0.80, 61: 0.60, 62: 0.30, 63: 0.0})
    h = utträdeshasard(q)
    assert h[60] == pytest.approx(0.25)
    assert h[61] == pytest.approx(0.5)


def test_stigande_deltagande_ger_ingen_hasard():
    """Ingen kommer tillbaka in i arbetskraften av åldersskäl, och en negativ
    hasard hade varit just det."""
    h = utträdeshasard(pd.Series({20: 0.5, 21: 0.7, 22: 0.9}))
    assert (h >= 0).all()
    assert h[20] == 0.0


def test_sista_aldern_tommer_arbetskraften():
    """Annars blir det hundraåringar kvar i arbetskraften."""
    h = utträdeshasard(profil(_rader(), _befolkning(), max_alder=74))
    assert h[74] == 1.0


def test_utträdet_fordelas_over_flera_ar():
    """Poängen med hasarden: klippan vid riktåldern lät alla lämna samma dag,
    vilket överdrev ersättningsflödet."""
    h = utträdeshasard(profil(_rader(), _befolkning(), retirement_age=67.0))
    over_noll = [a for a in range(64, 74) if h[a] > 0.05]
    assert len(over_noll) >= 4
