import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


import sqlite3

conn = sqlite3.connect("data/worm.sqlite3")
cur = conn.cursor()

# Lista alla tabeller
log("Tabeller i databasen:")
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
log([r[0] for r in cur.fetchall()])

# Titta på några rader i employment_deso_sni
log("\nFörsta 5 rader i employment_deso_sni:")
for row in cur.execute("SELECT * FROM employment_deso_sni LIMIT 5;"):
    log(row)

# Titta på några rader i employment_municipality_sni
log("\nFörsta 5 rader i employment_municipality_sni:")
for row in cur.execute("SELECT * FROM employment_municipality_sni LIMIT 5;"):
    log(row)

conn.close()
