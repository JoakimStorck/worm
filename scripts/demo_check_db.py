import sqlite3
import pandas as pd

db_path = "data/worm.sqlite3"

def show_table_info(conn, table_name):
    # Kolla att tabellen finns
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name} LIMIT 3", conn)
        count = pd.read_sql(f"SELECT COUNT(*) as n FROM {table_name}", conn).iloc[0,0]
        print(f"\nTable: {table_name} ({count} rows)")
        print(df)
    except Exception as e:
        print(f"\nTable: {table_name} – Error: {e}")

conn = sqlite3.connect(db_path)
# Lista tabeller i databasen
tables = pd.read_sql(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name", conn
)["name"].tolist()

print("All tables in database:")
for t in tables:
    print(f"  - {t}")

# Visa kort info om alla tabeller
for t in tables:
    show_table_info(conn, t)

conn.close()

