# database/utils.py

import pandas as pd
from core.statistics.log import log 

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

