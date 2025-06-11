# === Scenario Metadata ===
scenario_name: str              # Obligatoriskt. Unikt och beskrivande namn för scenariot.
description: str                # (Valfritt) Fri beskrivning av syfte, antaganden, region etc.
start_year: int                 # Obligatoriskt. År då simuleringen startar.
end_year: int                   # (Valfritt) Sista år, om simulering över tid.

seed: int                       # (Valfritt) Slumptalsfrö för reproducerbarhet.

# === Kommunurval ===
municipalities:                 # Lista av kommunnummer (str eller int), eller namn. Krävs!
  - 2080                        # Ex: Falun
  - 2081                        # Ex: Borlänge

# === Globala Default-parametrar (”defaults”) ===
defaults:
  # Demografi och arbetsmarknad
  population: int | "auto"      # Kommunbefolkning. Kan vara explicit, per år, eller "auto" från databas.
  workforce_ratio: float        # Andel av befolkning som är arbetskraft (0–1). Kan tidsvarieras.
  education_levels:             # Andelar, antingen fasta, kurvor eller ”by_year”
    low: float | {by_year: {...}} | {curve: ...}
    medium: ...
    high: ...
  sex_ratio: float | {curve: ...}   # Andel kvinnor (0–1)
  occupation_distribution: str      # T.ex. "random", "realistic", "synthetic"

  # Arbetsgivare, arbetsställen och fördelning
  employer_distribution:
    n_employers: int | "auto"               # Antal arbetsgivare, explicit eller auto-beräknat.
    employer_ratio_per_population: float    # Nyckeltal för auto-beräkning, ex 0.09.
    allocation_order: [str, ...]            # Lista: prioriterad ordning av lager.
    layer_configs:                          # Per lager: vilket fält som viktningsbas.
      business_zones: {weight_field: str}
      commercial_zones: {weight_field: str}
      small_localities: {weight_field: str}
      urban_areas: {weight_field: str}
    employer_size_distribution:             # Fördelning av storlekar (klasser, ratio)
      micro:        {max_size: int,  ratio: float}
      small:        {min_size: int, max_size: int, ratio: float}
      medium_large: {min_size: int, max_size: int, ratio: float}
      very_large:   {min_size: int, max_size: int, ratio: float}

# === Kommun- eller gruppvisa overrides ===
municipality_overrides:
  2080:  # Falun
    # Endast det som ska skilja från defaults!
    workforce_ratio: 0.56
    education_levels:
      low: {curve: linear, start: 0.26, end: 0.20, start_year: 2024, end_year: 2030}
      medium: 0.60
      high: {by_year: {2024: 0.14, 2027: 0.18, 2030: 0.20}}
    employer_distribution:
      employer_ratio_per_population: 0.11
  [2081, 2082]:
    workforce_ratio: 0.50
    # ...osv

# === Policys och regler ===
hiring_policy: str              # T.ex. "seniority_first", "random", "custom" etc.
wage_policy: str                # T.ex. "market_adjust", "fixed", etc.

# === Eventlista (händelser under simulerad period) ===
events:
  - year: int
    type: str                   # Exempel: "firm_entry", "firm_exit", "policy_change"
    municipality: int           # (valfritt) – kan styra händelser per kommun
    employer:                   # (vid firm_entry)
      name: str
      size: int
      sni_code: str
    employer_name: str          # (vid firm_exit)
  # ...ytterligare events

# === EXEMPEL PÅ TIDSVARIERADE PARAMETRAR ===
# Alla parametrar (ex workforce_ratio, education_levels, employer_ratio_per_population) 
# kan anges på tre sätt:
#
# 1. Fasta värden: 0.52
# 2. By year:
#      by_year: {2024: 0.52, 2027: 0.54, 2030: 0.56}
# 3. Kurva:
#      curve: linear
#      start: 0.52
#      end: 0.56
#      start_year: 2024
#      end_year: 2030
#
# För stepfunktion:
#      curve: step
#      changes:
#        - {year: 2026, value: 0.53}
#        - {year: 2029, value: 0.56}
#      default: 0.52

# === YTTERLIGARE FÖRSLAG/RESERVFÄLT ===
# - Möjlighet att lägga till "regions" eller kommungrupper som kan få overrides.
# - Förberett för ”synthetic” population om man vill skapa helt konstgjorda regioner.
# - Möjlighet att peka på särskilda datafiler om man vill exkludera delar av autoimporten.

