# worm/configreader.py
# Reader for WORM configuration files.
## Reads YAML files and provides access to configuration data.
# worm/configreader.py

import pandas as pd
import numpy as np
import sqlite3

class ConfigReader:
    def __init__(self, config, conn=None):
        """
        config: laddad YAML (dict)
        conn: sqlite-connection (kan behövas för att läsa default-data)
        """
        self.config = config
        self.conn = conn

        self.municipalities = config.get("municipalities", [])

    @staticmethod
    def parse_time_with_unit(val, days_per_year=365.25):
        """
        Convert a string like '0.083y', '12d', '3w' to number of days.
        Accepts float/int with no unit as days.
        """
        if isinstance(val, (float, int)):
            return float(val)
        if isinstance(val, str):
            val = val.strip().lower()
            if val.endswith('y'):
                return float(val[:-1]) * days_per_year
            elif val.endswith('w'):
                return float(val[:-1]) * 7
            elif val.endswith('d'):
                return float(val[:-1])
            else:
                raise ValueError(f"Unknown time unit in {val}, use 'd', 'w', or 'y'")
        raise ValueError(f"Unsupported time value: {val}")

    # Defaultvärden i dagar. Ett scenario som saknar event_timings ska ge en
    # varning och köra vidare, inte KeyError: 'dist' mitt i _init_events.
    # falun_baseline.yml saknar blocket helt.
    DEFAULT_EVENT_TIMINGS = {
        "quit_job":                {"dist": "normal", "mean": 1461.0, "std": 730.5},
        "start_job_search":        {"dist": "exponential", "mean": 28.0},
        "start_education":         {"dist": "uniform", "min": 30.0, "max": 365.0},
        "end_education":           {"dist": "uniform", "min": 365.0, "max": 1095.0},
        "start_internal_training": {"dist": "uniform", "min": 90.0, "max": 730.0},
        "internal_job_change":     {"dist": "uniform", "min": 365.0, "max": 1461.0},
        "career_break":            {"dist": "uniform", "min": 365.0, "max": 2190.0},
    }

    def get_event_timing(self, event_name):
        """
        Return timing config for a given event (e.g. 'start_job_search'), all units converted to days.
        Returns a dict with all relevant keys converted.

        Saknar scenariot posten helt används ett default, med varning en gång
        per händelsetyp. Nycklar som finns i scenariot går före defaulten.
        """
        timing = self.config.get("simulation", {}).get("event_timings", {}).get(event_name, {})
        result = {}
        for k, v in timing.items():
            if k in ("mean", "min", "max", "duration", "std"):  # keys to parse as time
                result[k] = self.parse_time_with_unit(v)
            else:
                result[k] = v

        if "dist" not in result:
            default = self.DEFAULT_EVENT_TIMINGS.get(event_name)
            if default is None:
                return result
            if not hasattr(self, "_timing_warned"):
                self._timing_warned = set()
            if event_name not in self._timing_warned:
                self._timing_warned.add(event_name)
                print(f"VARNING: scenariot saknar event_timings.{event_name} — "
                      f"använder default {default}.")
            merged = dict(default)
            merged.update(result)          # scenariots egna nycklar vinner
            return merged
        return result

    def _to_list(self, item):
        # Hjälpmetod: alltid lista
        return item if isinstance(item, (list, tuple)) else [item]

    def _get_from_db_population(self, municipal_code):
        # Hämta verklig befolkning från DB (om population: 'auto' eller saknas)
        query = "SELECT population FROM municipalities WHERE municipal_code = ?"
        df = pd.read_sql(query, self.conn, params=[municipal_code])
        if not df.empty:
            return int(df.iloc[0]["population"])
        raise ValueError(f"Ingen population hittades för kommun {municipal_code}")

    def get_population(self, municipal_codes):
        codes = self._to_list(municipal_codes)
        overrides = self.config.get("municipality_overrides", {})
        defaults = self.config.get("defaults", {})
        result = []
        for code in codes:
            pop = None
            # 1. Municipality-specific override
            if code in overrides and "population" in overrides[code]:
                pop = overrides[code]["population"]
            # 2. Default for all
            elif "population" in defaults:
                pop = defaults["population"]
            # 3. Fallback: fetch from db
            if pop == "auto" or pop is None:
                pop = self._get_from_db_population(code)
            result.append(int(pop))
        return result

    def get_unemployment_rate(self, municipal_codes, year=None):
        codes = self._to_list(municipal_codes)
        overrides = self.config.get("municipality_overrides", {})
        defaults = self.config.get("defaults", {})
        result = []
        for code in codes:
            rate = None
            # 1. Municipality-specific override
            if code in overrides and "unemployment_rate" in overrides[code]:
                val = overrides[code]["unemployment_rate"]
                # Om det är tidsserie: {by_year: {2024: 0.07, 2027: 0.08, ...}}
                if isinstance(val, dict) and "by_year" in val and year is not None:
                    # Hitta närmaste år bakåt eller exakt
                    years = sorted(int(k) for k in val["by_year"].keys())
                    rate = val["by_year"].get(str(year))
                    if rate is None:
                        # Hitta senaste tillgängliga år innan det aktuella
                        past_years = [y for y in years if y <= year]
                        if past_years:
                            rate = val["by_year"][str(max(past_years))]
                        else:
                            rate = 0.0
                else:
                    rate = val
            # 2. Default för alla
            elif "unemployment_rate" in defaults:
                val = defaults["unemployment_rate"]
                if isinstance(val, dict) and "by_year" in val and year is not None:
                    years = sorted(int(k) for k in val["by_year"].keys())
                    rate = val["by_year"].get(str(year))
                    if rate is None:
                        past_years = [y for y in years if y <= year]
                        if past_years:
                            rate = val["by_year"][str(max(past_years))]
                        else:
                            rate = 0.0
                else:
                    rate = val
            # 3. Fallback – om inget finns, default = 0.0
            if rate is None:
                rate = 0.0
            result.append(float(rate))
        return result


    def get_workforce_ratio(self, municipal_codes):
        codes = self._to_list(municipal_codes)
        overrides = self.config.get("municipality_overrides", {})
        defaults = self.config.get("defaults", {})
        result = []
        for code in codes:
            val = None
            if code in overrides and "workforce_ratio" in overrides[code]:
                val = overrides[code]["workforce_ratio"]
            elif "workforce_ratio" in defaults:
                val = defaults["workforce_ratio"]
            if val is None:
                val = 0.5
            result.append(float(val))
        return result

    def get_education_levels(self, municipal_codes, year=None):
        """
        Returnerar lista med dicts för low/medium/high per kommun. Tar hänsyn till by_year och curve om de finns.
        """
        codes = self._to_list(municipal_codes)
        overrides = self.config.get("municipality_overrides", {})
        defaults = self.config.get("defaults", {})
        result = []
        for code in codes:
            entry = None
            if code in overrides and "education_levels" in overrides[code]:
                entry = overrides[code]["education_levels"]
            elif "education_levels" in defaults:
                entry = defaults["education_levels"]
            else:
                entry = {"low": 0.3, "medium": 0.5, "high": 0.2}
            levels = {}
            for level in ["low", "medium", "high"]:
                val = entry.get(level, 0.0)
                # Årsbaserad upplösning
                levels[level] = self.resolve_year_param(val, year)
            result.append(levels)
        return result

    def get_sex_ratio(self, municipal_codes, year=None):
        codes = self._to_list(municipal_codes)
        overrides = self.config.get("municipality_overrides", {})
        defaults = self.config.get("defaults", {})
        result = []
        for code in codes:
            val = None
            if code in overrides and "sex_ratio" in overrides[code]:
                val = overrides[code]["sex_ratio"]
            elif "sex_ratio" in defaults:
                val = defaults["sex_ratio"]
            if val is None:
                val = 0.5
            result.append(float(self.resolve_year_param(val, year)))
        return result

    def get_occupation_distribution(self, municipal_codes):
        codes = self._to_list(municipal_codes)
        overrides = self.config.get("municipality_overrides", {})
        defaults = self.config.get("defaults", {})
        result = []
        for code in codes:
            val = None
            if code in overrides and "occupation_distribution" in overrides[code]:
                val = overrides[code]["occupation_distribution"]
            elif "occupation_distribution" in defaults:
                val = defaults["occupation_distribution"]
            else:
                val = "random"
            result.append(val)
        return result

    def get_employer_distribution(self, municipal_code):
        """
        Returnerar full dict med employer_distribution för given kommun (override, annars default).
        """
        overrides = self.config.get("municipality_overrides", {})
        defaults = self.config.get("defaults", {})
        # Årshantering kan läggas till om det behövs
        if municipal_code in overrides and "employer_distribution" in overrides[municipal_code]:
            return overrides[municipal_code]["employer_distribution"]
        elif "employer_distribution" in defaults:
            return defaults["employer_distribution"]
        else:
            raise ValueError("employer_distribution saknas i scenario-config.")

    def resolve_year_param(self, param, year):
        """
        Returnerar korrekt värde utifrån param som kan vara konstant, dict med by_year, eller curve.
        """
        if isinstance(param, dict):
            if "by_year" in param:
                # Gör om år till strängar
                by_year = {str(k): v for k, v in param["by_year"].items()}
                years = sorted(map(int, by_year.keys()))
                values = [by_year[str(y)] for y in years]
                if year <= years[0]:
                    return values[0]
                if year >= years[-1]:
                    return values[-1]
                # Linjär interpolation mellan närliggande år
                for i in range(1, len(years)):
                    if years[i-1] <= year < years[i]:
                        x0, x1 = years[i-1], years[i]
                        y0, y1 = values[i-1], values[i]
                        return y0 + (y1 - y0) * (year - x0) / (x1 - x0)
            elif "curve" in param:
                # Endast stöd för linjärt/step
                if param["curve"] == "linear":
                    return self.interpolate_linear(param["start"], param["end"], param.get("start_year", 2024), param.get("end_year", 2030), year)
                elif param["curve"] == "step":
                    return self.step_value(param["changes"], param.get("default", 0.0), year)
            else:
                return param.get("constant", 0.0)
        return param

    @staticmethod
    def interpolate_linear(start, end, start_year, end_year, year):
        if year is None:
            return start
        if year <= start_year:
            return start
        if year >= end_year:
            return end
        return start + (end - start) * (year - start_year) / (end_year - start_year)

    @staticmethod
    def step_value(changes, default, year):
        val = default
        for change in sorted(changes, key=lambda c: c["year"]):
            if year >= change["year"]:
                val = change["value"]
            else:
                break
        return val

    # Exempel på generisk parameterhämtare om du vill ha full flexibilitet
    def get_param(self, param, municipal_code, year=None, default=None):
        """
        Hämtar valfri parameter på korrekt nivå.
        param: ex. 'workforce_ratio'
        """
        overrides = self.config.get("municipality_overrides", {})
        defaults = self.config.get("defaults", {})
        if municipal_code in overrides and param in overrides[municipal_code]:
            val = overrides[municipal_code][param]
        elif param in defaults:
            val = defaults[param]
        else:
            val = default
        return self.resolve_year_param(val, year)


    def validate_scenario(self, strict=True):
        """
        Validerar att scenariot är logiskt och konsistent.
        Upptäcker bl a:
        - Tvetydiga eller motsägande perioddefinitioner (start_year, end_year, n_years)
        - Saknade nödvändiga fält (ex: municipalities, defaults)
        - Orimliga värden (negativa populationer, ratio > 1, etc)
        - Dubbeldefinitioner på flera nivåer
        - Kända fält i employer/individuals-sektioner
        Skriv ut VARNING eller FEL beroende på strict.
        """
        err = []
        warn = []

        # === Kolla simuleringsperiod ===
        sim = self.config.get("simulation", {})
        sy = sim.get("start_year", self.config.get("start_year"))
        ey = sim.get("end_year", self.config.get("end_year"))
        ny = sim.get("n_years", self.config.get("n_years"))

        try:
            sy = int(sy) if sy is not None else None
            ey = int(ey) if ey is not None else None
            ny = int(ny) if ny is not None else None
        except Exception as e:
            err.append(f"Felaktigt format på start_year, end_year eller n_years: {e}")

        # Kontrollera period
        if sy is not None and ey is not None and ny is not None and ny != (ey - sy + 1):
            err.append(f"Konflikt: n_years={ny} men (end_year - start_year + 1) = {ey-sy+1}.")
        if sy is not None and ey is not None and ey < sy:
            err.append(f"end_year ({ey}) < start_year ({sy})!")
        if ny is not None and ny < 1:
            err.append("n_years måste vara minst 1.")
        if (sy is None and ey is None) or (sy is None and ny is None) or (ey is None and ny is None):
            err.append("Du måste ange minst två av: start_year, end_year, n_years.")

        # === Nödvändiga huvudsektioner ===
        for section in ["municipalities", "defaults"]:
            if section not in self.config or self.config[section] is None:
                err.append(f"Sektionen '{section}' saknas i scenariot.")
            elif section == "municipalities" and not self.config[section]:
                err.append("Listan över municipalities är tom.")

        # === Validera defaults ===
        defaults = self.config.get("defaults", {})
        pop = defaults.get("population", None)
        if pop is not None and (isinstance(pop, (int, float)) and pop < 0):
            err.append("Population kan inte vara negativ.")

        # Ratio-kontroller
        ratios = {
            "workforce_ratio": defaults.get("workforce_ratio"),
            "sex_ratio": defaults.get("sex_ratio"),
            "unemployment_rate": defaults.get("unemployment_rate")
        }
        for k, v in ratios.items():
            if v is not None:
                try:
                    val = float(v)
                    if not (0 <= val <= 1):
                        err.append(f"{k} ska vara mellan 0 och 1.")
                except Exception:
                    warn.append(f"{k} kan inte tolkas som tal: '{v}'")

        # === Education levels ska summera till 1.0 (+/- 0.01) ===
        edu = defaults.get("education_levels", {})
        if edu and isinstance(edu, dict):
            total = sum(float(edu.get(level, 0.0)) for level in ["low", "medium", "high"])
            if abs(total - 1.0) > 0.01:
                warn.append(f"education_levels summerar till {total}, ej 1.0.")

        # === Kolla employer_distribution ===
        emp_dist = defaults.get("employer_distribution", {})
        size_dist = emp_dist.get("employer_size_distribution", {})
        size_sum = sum(float(cls.get("ratio", 0.0)) for cls in size_dist.values())
        if size_dist and abs(size_sum - 1.0) > 0.01:
            warn.append(f"employer_size_distribution ratio summerar till {size_sum}, ej 1.0.")

        # === Dubbletter: Warn om param finns på flera nivåer ===
        overrides = self.config.get("municipality_overrides", {})
        for mcode, ovr in overrides.items():
            for key in ovr:
                if key in defaults:
                    warn.append(f"Parameter '{key}' finns både i defaults och i override för {mcode}.")

        # === Kända sektioner individuals/employer (felstavar eller dubbletter) ===
        known_indiv = {"propensities", "initial_r", "initial_H"}
        indv = defaults.get("individuals", {})
        for k in indv.keys():
            if k not in known_indiv:
                warn.append(f"Okänt attribut '{k}' i defaults.individuals.")

        # === Rapportera allt ===
        for w in warn:
            print("[SCENARIO CONFIG VARNING]", w)
        if err:
            for e in err:
                print("[SCENARIO CONFIG FEL]", e)
            if strict:
                raise ValueError("Felaktig scenario-config (se ovan).")

        return True


# --- Slut på ConfigReader ---
