"""SNI-koden för totalraden.

SCB:s uttag har en rad "A-U+US Total" -- summan över alla näringsgrenar.
extract_sni_code matchade ^([A-U\\+\\d]+), vilket stannade vid bindestrecket och
gav "A": samma kod som näringsgren A, jordbruk och skogsbruk. Raderna
kolliderade, drop_duplicates behöll den som låg först i filen -- totalen --
och jordbruksraden försvann.

Kod A i employment_deso_sni bar därmed hela kommunens sysselsättning: 10 184
för Mora, med beskrivningen "Total". fetch_sni_distribution läser tabellen för
att välja bransch åt varje arbetsgivare, så en stor andel av arbetsgivarna
placerades i jordbruk och skogsbruk och drog yrkesfördelningen mot den delen
av uppgiftsrummet. Ingenting i kedjan klagade.
"""
import pandas as pd
import pytest

from core.database.loader import SNI_TOTAL, extract_sni_code, extract_sni_description


def test_totalraden_far_egen_kod():
    assert extract_sni_code("A-U+US Total") == SNI_TOTAL
    assert extract_sni_code("A-U Total") == SNI_TOTAL


def test_naringsgren_a_ar_kvar_som_a():
    assert extract_sni_code("A företag inom jordbruk, skogsbruk och fiske") == "A"


def test_totalen_krockar_inte_med_nagon_naringsgren():
    """Kärnan: ingen näringsgren får dela nyckel med totalen."""
    etiketter = [
        "A-U+US Total",
        "A företag inom jordbruk, skogsbruk och fiske",
        "B+C tillverkningsindustri",
        "D+E energi och miljö",
        "F byggindustri",
        "G handel; reparation av motorfordon",
        "H transport och magasinering",
        "I hotell- och restaurangverksamhet",
        "J informations- och kommunikationsverksamhet",
        "K finans- och försäkringsverksamhet",
        "L fastighetsverksamhet",
        "M+N företagstjänster",
        "O offentlig förvaltning och försvar",
        "P utbildning",
        "Q vård och omsorg",
        "R+S+T+U personliga och kulturella tjänster",
    ]
    koder = [extract_sni_code(e) for e in etiketter]
    assert len(set(koder)) == len(koder), dict(zip(etiketter, koder))
    assert koder.count(SNI_TOTAL) == 1


def test_beskrivningen_avslojar_kollisionen():
    """Det var beskrivningen som avslöjade felet i databasen: kod A hade
    sni_description 'Total'."""
    assert extract_sni_description("A-U+US Total") == "Total"
    assert extract_sni_description(
        "A företag inom jordbruk, skogsbruk och fiske").startswith("företag")


def test_kolliderande_koder_far_inte_tystas():
    """drop_duplicates dolde kollisionen i två år: två olika näringsgrenar med
    samma nyckel såg ut som en dublett och den första vann tyst. En sådan
    krock ska stoppa laddningen."""
    import inspect

    from core.database import loader

    kalla = inspect.getsource(loader.load_employment_deso_sni)
    assert "duplicated(" in kalla
    assert "raise ValueError" in kalla
    # och drop_duplicates får bara köras när ingen kollision finns
    i_kontroll = kalla.index("duplicated(")
    i_drop = kalla.index("drop_duplicates(")
    assert i_kontroll < i_drop


@pytest.mark.parametrize("etikett,vantat", [
    ("A-U+US Total", SNI_TOTAL),
    ("TOTAL", SNI_TOTAL),
    ("Total", SNI_TOTAL),
    ("B+C tillverkningsindustri", "B+C"),
    ("", ""),
])
def test_varianter(etikett, vantat):
    assert extract_sni_code(etikett) == vantat
