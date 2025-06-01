import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import matplotlib.pyplot as plt

def plot_selected_municipalities(geoworld, codes_or_names, layers=("municipalities",)):
    """
    Rita en eller flera kommuner, och overlaya andra lager för samma kommun(er).
    All matchning sker på kommunnummer (municipal_code) om möjligt.
    Debugutskrifter visar matchningen per lager!
    """
    if isinstance(codes_or_names, (str,)):
        codes_or_names = [codes_or_names]

    # Hitta valda kommuner (matcha kod ELLER namn, case-insensitive)
    selected = []
    selected_codes = set()
    selected_names = set()
    print("SÖKER EFTER:", codes_or_names)
    for val in codes_or_names:
        # Matcha alltid på kod eller exakt/substring i namn
        match = [m for m in geoworld.municipalities.values()
                 if m.code == val or val.lower() in m.name.lower()]
        selected.extend(match)
        selected_codes.update([m.code for m in match])
        selected_names.update([m.name.lower() for m in match])

    print(f"VALDA KOMMUNER (kod): {selected_codes}")
    print(f"VALDA KOMMUNER (namn): {selected_names}")

    if not selected:
        print("Inga matchande kommuner hittades!")
        return

    plt.figure(figsize=(8, 8))
    colors = {
        "municipalities": "#ECECEC",     # Ljus neutralgrå (bakgrund, gles struktur)
        "urban_areas": "#FF7F0E",        # Orange – tydligt “hett”, urbanitet, aktivitet
        "small_localities": "#FFD700",   # Guldgul – mellanting, små tätorter men ändå liv
        "business_zones": "#D62728",     # Röd – stark närvaro av arbetsplatser, industri
        "commercial_zones": "#2CA02C",   # Grön – kommersiella områden, ofta mer spritt, “svalare”
        "leisure_house_zones": "#9467BD" # Lila – fritidsområden, perifert/annorlunda
    }

    ax = plt.gca()

    # Rita kommunpolygoner
    print(f"\nRitar kommuner ({len(selected)} st):")
    for m in selected:
        print(f" - {m.code} {m.name}")
        poly = m.polygon
        if poly.geom_type == "Polygon":
            x, y = poly.exterior.xy
            ax.fill(x, y, color=colors["municipalities"], label=f"{m.name} ({m.code})")
        elif poly.geom_type == "MultiPolygon":
            for subpoly in poly.geoms:
                x, y = subpoly.exterior.xy
                ax.fill(x, y, color=colors["municipalities"], label=f"{m.name} ({m.code})")

    # Rita övriga lager där de matchar vald kommun (bara på municipal_code)
    # Rita övriga lager där de matchar vald kommun (bara på kommunnummer)
    for layer in layers:
        if layer == "municipalities":
            continue  # Redan ritat!
        if not hasattr(geoworld, layer):
            print(f"Warning: GeoWorld does not have layer '{layer}'.")
            continue
        entities = getattr(geoworld, layer).values()
        hits = []
        miss = 0
        for entity in entities:
            # Testa båda möjliga kommunnummer-attribut
            muni_code = getattr(entity, "municipality_code", None)
            if muni_code is None:
                muni_code = getattr(entity, "municipal_code", None)
            if muni_code and muni_code in selected_codes:
                hits.append(entity)
            else:
                miss += 1
        print(f"\nLayer: {layer}, hittade {len(hits)} objekt att rita (missade {miss})")
        if hits:
            print("Exempel på objekt som ritas:")
            for e in hits[:5]:
                muni_code = getattr(e, "municipality_code", None) or getattr(e, "municipal_code", None)
                print(f"  - code: {muni_code}, name: {getattr(e, 'municipality', None) or getattr(e, 'municipal_name', None)}")

        if not hits:
            print(f"  (Inga träffar för valda kommuner i lager '{layer}')")

        for entity in hits:
            poly = entity.polygon
            if poly is None:
                print(f"  OBS: Polygon saknas för entity: {entity}")
                continue
            if poly.geom_type == "Polygon":
                x, y = poly.exterior.xy
                ax.fill(x, y, color=colors.get(layer, "#88888844"), label=layer)
            elif poly.geom_type == "MultiPolygon":
                for subpoly in poly.geoms:
                    x, y = subpoly.exterior.xy
                    ax.fill(x, y, color=colors.get(layer, "#88888844"), label=layer)

    ax.set_aspect("equal")
    # Bara unika labels i legend
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    ax.legend(by_label.values(), by_label.keys(), loc="upper right")
    ax.axis("off")
    plt.title("Valda kommuner och lager")
    plt.tight_layout()
    plt.show()

# Exempel på användning:
from worm.geography.geoworld import GeoWorld
gw = GeoWorld("data/worm.sqlite3")

print(f"Testar business_zones:")
#for e in list(gw.business_zones.values())[:10]:
#    print(f"{e.code} - muni_code={getattr(e, 'municipality_code', None)} muni={getattr(e, 'municipality', None)}")

# Sök manuellt efter Falun
falun_bz = [e for e in gw.business_zones.values() if getattr(e, 'municipality_code', None) == "2080"]
print(f"Antal bz Falun: {len(falun_bz)}")
for bz in falun_bz:
    print(f"bz.code={bz.code} muni_code={bz.municipality_code!r} (type={type(bz.municipality_code)})")


plot_selected_municipalities(gw, ["Falun","Borlänge"], layers=("municipalities","urban_areas","small_localities","commercial_zones","business_zones"))

