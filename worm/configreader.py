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

# --- Slut på ConfigReader ---
