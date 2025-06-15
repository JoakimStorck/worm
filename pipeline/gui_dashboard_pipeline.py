# pipeline/gui_dashboard_pipeline.py

import os
import sys
import glob
import pandas as pd
import yaml

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.configreader import ConfigReader

from core.scenario_result import ScenarioResult
from core.replay_controller import ReplayController
from core.visualization.occupation_space_panel import OccupationSpacePanel
from core.visualization.map_panel import MapPanel
from core.geography.geoworld import GeoWorld
from core.scenario_runner import run_and_log_scenario

from bokeh.layouts import row, column
from bokeh.io import curdoc
from bokeh.models import Select, Div, Button
from bokeh.events import ButtonClick

# --- 1. Registry-säkerställning ---
REGISTRY_PATH = "output/runs_registry.csv"
REGISTRY_HEADER = "run_id,output_path,scenario_name,timestamp\n"
if not os.path.exists(REGISTRY_PATH):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        f.write(REGISTRY_HEADER)

# --- 2. GEO ---
db_path = "data/worm.sqlite3"
geoworld = GeoWorld(db_path)
muni_gdf = geoworld.municipalities
selected_codes_or_names = muni_gdf["municipal_code"].unique().tolist()
gdf_layers = {}
layers = ["municipalities"]

# --- 3. Scenarioväljare ---
scenario_files = glob.glob("scenarios/*.yml") + glob.glob("scenarios/*.yaml")
scenario_options = [os.path.basename(f) for f in scenario_files]
scenario_select = Select(title="Välj scenario/config-fil att köra:", value=None, options=scenario_options)
run_button = Button(label="Kör simulering", button_type="success")

# --- 4. Funktion för registry-laddning ---
def load_registry():
    if os.path.exists(REGISTRY_PATH):
        return pd.read_csv(REGISTRY_PATH)
    else:
        return pd.DataFrame(columns=["run_id", "output_path", "scenario_name", "timestamp"])

# --- 5. Kör-simulering callback (nu RÄTT version) ---
def run_simulation():
    scenario = scenario_select.value
    if not scenario:
        info_div.text = "<b>Välj ett scenario först!</b>"
        return
    full_scenario_path = os.path.join("scenarios", scenario)
    try:
        output_text = run_and_log_scenario(full_scenario_path)
        info_div.text = f"<b>Simulering klar!</b> <br>Scenario: {scenario}<br>Utdata:<pre>{output_text}</pre>"
        reload_registry()
    except Exception as e:
        info_div.text = f"<b>Fel vid körning av simulering:</b><br>{e}"

def on_run_button_click(event):
    run_simulation()
run_button.on_event(ButtonClick, on_run_button_click)

# --- 6. Initial registry och väljare ---
def build_run_selector():
    global registry_df, run_options, run_paths
    registry_df = load_registry()
    if not registry_df.empty:
        run_options = [
            f"{row['timestamp']} - {row['scenario_name']} ({row['run_id']})"
            for _, row in registry_df.iterrows()
        ]
        run_paths = [
            row['output_path']
            for _, row in registry_df.iterrows()
        ]
    else:
        run_options = []
        run_paths = []
    select_label = "Välj simulering (run):"
    select = Select(title=select_label, value=None, options=run_options)
    return select

# --- 7. Panelval och layout (initial) ---
info_div = Div(text="<b>Ingen simulering vald.</b><br>Välj en run för att visa dashboarden.")
select = build_run_selector()

def reload_registry():
    # Bygg om run-väljaren och ersätt i layouten
    global select
    old_value = select.value
    new_select = build_run_selector()
    new_select.on_change('value', on_run_selected)
    dashboard_layout.children[2] = new_select
    select = new_select
    select.value = old_value  # återställ val om möjligt


import ast

def load_config_from_metadata(metadata_path):
    with open(metadata_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    config_line = next((line for line in lines if line.startswith("Config: ")), None)
    if config_line:
        config_str = config_line[len("Config: "):].strip()
        # Om dict-strängen är fördelad över flera rader, slå ihop dem
        while not config_str.endswith("}"):
            next_line = lines.pop(0)
            config_str += next_line.strip()
        # Konvertera sträng till dict på ett säkert sätt
        config = ast.literal_eval(config_str)
        return config
    else:
        raise FileNotFoundError("Ingen 'Config:'-rad hittad i metadata.txt")


# --- 8. Callback för att visa dashboard ---
def on_run_selected(attr, old, new):
    if select.value is None:
        info_div.text = "<b>Ingen simulering vald.</b><br>Välj en run för att visa dashboarden."
        return
    idx = run_options.index(select.value)
    run_path = run_paths[idx]
    result = ScenarioResult.from_run(run_path)
    replay = ReplayController(result)

    # Läs in config och plocka ut valda kommuner via ConfigReader
    metadata_path = os.path.join(run_path, "metadata.txt")
    if os.path.exists(metadata_path):
        config = load_config_from_metadata(metadata_path)
        cfg = ConfigReader(config)
        selected_codes = cfg.municipalities
        # ...vidare kod...
    else:
        # Hantera fallback, t.ex. sök .yml-fil som tidigare
        print(f"on_run_selected: Filen {metadata_path} existerar ej")


    muni_gdf_selected = geoworld.municipalities[
        geoworld.municipalities["municipal_code"].isin(selected_codes)
    ]

    occ_panel = OccupationSpacePanel(replay)
    map_panel = MapPanel(
        replay,
        muni_gdf=muni_gdf_selected,
        selected_codes_or_names=selected_codes,
        layers=layers,
        gdf_layers=gdf_layers
    )
    new_panel_row = row(occ_panel.layout, map_panel.layout)
    dashboard_layout.children[3:] = [new_panel_row]


select.on_change('value', on_run_selected)

# --- 9. Slutgiltig layout ---
dashboard_layout = column(
    scenario_select,
    run_button,
    select,
    info_div
)
curdoc().clear()
curdoc().add_root(dashboard_layout)
curdoc().title = "WORM Dashboard"

print("PIPELINE FILE IMPORTERAD!")
