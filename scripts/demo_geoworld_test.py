import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from worm.geography.geoworld import GeoWorld

gw = GeoWorld("data/worm.sqlite3")
falun_code = "2080"  # Kommunnummer Falun
falun = gw.municipalities[falun_code]
log(falun)

