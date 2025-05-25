
# WORM Scripts

Detta är din **scenariomapp** för att köra simuleringar med WORM – Worker-Occupation-Region Model.

## 🏃‍♂️ Köra ett scenario

Använd Python för att köra valfritt script i denna mapp. Exempel:

```bash
python scripts/worm_demo.py
```

## 📄 Exempelfiler

- `worm_demo.py`: Grundläggande exempel som genererar arbetsgivare, arbetare, klustrar dem och matchar dem.
- `scenario_dalarna.py`: (kommande) Empiriskt baserad simulering för Dalarnas arbetsmarknad.
- `scenario_shock.py`: (kommande) Visar effekten av att en stor arbetsgivare lägger ned.

## 🧩 Struktur

Alla scripts importerar logik från `worm/`-paketet. Du kan kombinera geografi, kompetens, matchning och visualisering.

## 🧠 Tips

- Skapa ett script per forskningsfråga
- Lägg in `matplotlib`-visualiseringar direkt i dina körningar
- Spara experimentresultat till `.csv` eller `.json` om du vill analysera dem i Excel eller pandas

---
Författare: Joakim Storck  
Projektstart: 2025
