# database/utils.py

import pandas as pd
from core.log import log 

def kommunkod(serie):
    """Kommunkoder som fyrsiffriga strängar med bevarad inledande nolla.

    SCB:s koder är fyra siffror och hundratjugosju av dem börjar med nolla --
    hela Stockholms, Uppsala, Södermanlands, Östergötlands, Jönköpings,
    Kronobergs och Kalmar län. Läses ett lager ur en gpkg där kolumnen är
    numerisk blir 0180 till 180, och varje uppslag mot kommunkod faller tyst:
    ingen tabell klagar, raden finns bara inte. Dalarnas koder börjar på 2 och
    överlever, vilket är varför felet kan ligga i en kodbas i åratal utan att
    märkas.

    to_sql med if_exists="replace" släpper dessutom kolumntypen ur schema.py
    och sätter den efter dataframens dtype, så TEXT i CREATE TABLE räcker
    inte: typen måste vara rätt redan i ramen.
    """
    return (pd.Series(serie).astype("string").str.strip()
            .str.replace(r"\.0$", "", regex=True)
            .str.zfill(4))


def fetch_with_fallback(conn, table, filters, year_col='year', desired_year=None, columns='*'):
    """
    Hämtar rader från valfri tabell med dynamiska filter och fallback till senaste tillgängliga år.
    filters: dict, t.ex. {'municipal_code': '2080'}
    year_col: namn på år-kolumnen (default 'year')
    desired_year: året du helst vill ha (kan vara None)
    columns: str, t.ex. '*' eller 'sni_code, workplaces'
    """
    # Bygg WHERE-villkor för övriga filter (utom år)
    filter_sql = " AND ".join([f"{k} = ?" for k in filters.keys()])
    filter_vals = list(filters.values())

    # Hämta alla år tillgängliga (filtrerat)
    years_sql = f"SELECT DISTINCT {year_col} FROM {table}"
    if filter_sql:
        years_sql += f" WHERE {filter_sql}"
    years_sql += f" ORDER BY {year_col} DESC"
    years_df = pd.read_sql(years_sql, conn, params=filter_vals)

    if years_df.empty:
        raise ValueError(f"Ingen data i {table} med filter {filters}")

    available_years = years_df[year_col].tolist()
    if desired_year is not None:
        fallback_year = max([y for y in available_years if y <= desired_year], default=available_years[0])
    else:
        fallback_year = available_years[0]

    # Hämta faktiska data för rätt år
    full_filter_sql = filter_sql + (f" AND {year_col} = ?" if year_col else "")
    params = filter_vals + [fallback_year]
    sql = f"SELECT {columns} FROM {table} WHERE {full_filter_sql}"
    df = pd.read_sql(sql, conn, params=params)
    if df.empty:
        raise ValueError(f"Ingen data i {table} för år {fallback_year} med filter {filters}")
    if desired_year is not None and fallback_year != desired_year:
        log(f"Varning: Fallback till år {fallback_year} i {table} för filter {filters} (önskat år var {desired_year})")
    return df, fallback_year



# SCB:s uttag kommer i mer än en teckenkodning. Statistikdatabasens CSV är
# latin-1 när svaret bär klartext, medan ett rent kodat uttag råkar vara
# giltig UTF-8 eftersom det inte innehåller några å, ä eller ö alls. Ordningen
# är inte godtycklig: utf-8 prövas först, eftersom en UTF-8-fil avkodad som
# cp1252 INTE ger fel utan tyst fel text ("fÃ¶delseregion"), medan en
# latin-1-fil avkodad som UTF-8 alltid ger UnicodeDecodeError. Fel ordning
# gömmer alltså felet i stället för att visa det.
KODNINGAR = ("utf-8-sig", "cp1252", "iso-8859-1")


def las_rader(path, kodningar=KODNINGAR):
    """Filens rader som text, med den kodning som faktiskt fungerar."""
    for kodning in kodningar:
        try:
            with open(path, encoding=kodning) as f:
                return f.read().splitlines(), kodning
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Kan inte avkoda {path} med någon av {kodningar}")
