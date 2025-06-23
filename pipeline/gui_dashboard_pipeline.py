import os
import sys
import glob
import pandas as pd
import traceback

from bokeh.io import curdoc
from bokeh.models import Tabs, Select, Button, Div
from bokeh.layouts import column
from bokeh.models import ColumnDataSource

# Gör projektets root path tillgänglig för imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.configreader import ConfigReader
from core.scenario_result import ScenarioResult
from core.replay_controller import ReplayController
from core.geography.geoworld import GeoWorld
from core.scenario_runner import run_and_log_scenario
from core.ui_state import UIState

# Panel-funktioner
from core.visualization.occupation_space_panel import make_panel as occspace_panel
from core.visualization.map_panel import make_panel as map_panel

# --- 1. Säkerställ registry för simuleringskörningar ---
REGISTRY_PATH = "output/runs_registry.csv"
REGISTRY_HEADER = "run_id,output_path,scenario_name,timestamp\n"
if not os.path.exists(REGISTRY_PATH):
    os.makedirs(os.path.dirname(REGISTRY_PATH), exist_ok=True)
    with open(REGISTRY_PATH, "w") as f:
        f.write(REGISTRY_HEADER)

def load_registry():
    if os.path.exists(REGISTRY_PATH):
        return pd.read_csv(REGISTRY_PATH)
    else:
        return pd.DataFrame(columns=["run_id", "output_path", "scenario_name", "timestamp"])

# --- 2. Ladda geografidata och lager ---
db_path = "data/worm.sqlite3"
geoworld = GeoWorld(db_path)
muni_gdf = geoworld.municipalities
layers = ["municipalities"]
gdf_layers = {}

# --- 3. Scenario-väljare och startknapp ---
scenario_files = glob.glob("scenarios/*.yml") + glob.glob("scenarios/*.yaml")
scenario_options = [os.path.basename(f) for f in scenario_files]
scenario_select = Select(title="Välj scenario/config-fil att köra:", value=None, options=scenario_options)
run_button = Button(label="Kör simulering", button_type="success")
info_div = Div(text="<b>Ingen simulering vald.</b>")

# --- 4. Bygg run-selector dynamiskt utifrån registry ---
def build_run_selector():
    df = load_registry()
    if not df.empty:
        run_options = [
            f"{row['timestamp']} - {row['scenario_name']} ({row['run_id']})"
            for _, row in df.iterrows()
        ]
        run_paths = [row['output_path'] for _, row in df.iterrows()]
    else:
        run_options = []
        run_paths = []
    select = Select(title="Välj simulering (run):", value=None, options=run_options)
    return select, run_paths

run_selector, run_selector_paths = build_run_selector()

# --- 5. Dela centrala datakällor (för synk och interaktivitet) ---
indiv_source = ColumnDataSource(data=dict())  # Individer
job_source = ColumnDataSource(data=dict())    # Jobb
emp_source = ColumnDataSource(data=dict())    # Arbetsgivare

# --- 6. Hantera UI-state och replay ---
ui_state = UIState()
replay = None

# --- 7. Bygg paneler för tabs ---
def build_panels():
    occ_panel = occspace_panel(
        replay_controller=replay,
        ui_state=ui_state,
        indiv_source=indiv_source,
        job_source=job_source,
        emp_source=emp_source
    )
    map_pnl = map_panel(
        replay_controller=replay,
        muni_gdf=muni_gdf,
        selected_codes_or_names=[],
        layers=layers,
        gdf_layers=gdf_layers,
        ui_state=ui_state,
        indiv_source=indiv_source,
        emp_source=emp_source
    )
    return [occ_panel, map_pnl]

# --- 8. Tabs-widget som fylls på dynamiskt ---
tabs = Tabs(tabs=[], sizing_mode="stretch_both")  # <-- Här!

# --- 9. Kör simulering och uppdatera registry och UI ---
def run_simulation():
    global run_selector_paths
    scenario = scenario_select.value
    if not scenario:
        info_div.text = "<b>Välj ett scenario först!</b>"
        return
    full_scenario_path = os.path.join("scenarios", scenario)
    try:
        output_text = run_and_log_scenario(full_scenario_path)
        info_div.text = f"<b>Simulering klar!</b><br>Scenario: {scenario}<br>Utdata:<pre>{output_text}</pre>"
        # Uppdatera run-selector så ny simulering syns direkt
        updated_selector, updated_paths = build_run_selector()
        run_selector.options = updated_selector.options
        run_selector.value = None  # Reset selection
        run_selector_paths = updated_paths
    except Exception as e:
        info_div.text = f"<b>Fel vid körning av simulering:</b><br>{e}"

run_button.on_click(run_simulation)

# --- 10. Välj run och ladda paneler/datakällor från rätt körning ---
def _cds_data(obj):
    # Returnerar alltid en _kopierad_ dict
    from bokeh.models import ColumnDataSource
    import pandas as pd
    if isinstance(obj, ColumnDataSource):
        return dict(obj.data)  # Viktigt! Skapar en vanlig dict
    elif isinstance(obj, pd.DataFrame):
        return obj.to_dict("list")
    elif isinstance(obj, dict):
        return dict(obj)  # Säkerställer kopia även här
    else:
        return {}

import ast  # Glöm inte!

def load_config_from_metadata(metadata_path):
    with open(metadata_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    config_line = next((line for line in lines if line.startswith("Config: ")), None)
    if config_line:
        config_str = config_line[len("Config: "):].strip()
        # Om dict-strängen är fördelad över flera rader, slå ihop dem
        lines_iter = iter(lines)
        while not config_str.endswith("}"):
            next_line = next(lines_iter)
            config_str += next_line.strip()
        config = ast.literal_eval(config_str)
        return config
    else:
        raise FileNotFoundError("Ingen 'Config:'-rad hittad i metadata.txt")

def on_run_selected(attr, old, new):
    global replay
    global run_selector_paths
    if run_selector.value is None:
        return
    try:
        idx = run_selector.options.index(run_selector.value)
        run_path = run_selector_paths[idx]
        result = ScenarioResult.from_run(run_path)
        replay = ReplayController(result)
        if hasattr(ui_state, "reset"):
            ui_state.reset()
        indiv_source.data = _cds_data(replay.get_indiv_source())
        if hasattr(replay, "get_job_source"):
            job_source.data = _cds_data(replay.get_job_source())
        if hasattr(replay, "get_emp_source"):
            emp_source.data = _cds_data(replay.get_emp_source())
        else:
            emp_source.data = {}

        # -------- Återställ logik för urval av kommuner från metadata --------
        metadata_path = os.path.join(run_path, "metadata.txt")
        selected_codes = []
        muni_gdf_selected = muni_gdf
        if os.path.exists(metadata_path):
            try:
                config = load_config_from_metadata(metadata_path)
                cfg = ConfigReader(config)
                selected_codes = [str(code) for code in getattr(cfg, "municipalities", [])]
                if selected_codes:
                    muni_gdf_selected = muni_gdf[muni_gdf["municipal_code"].isin(selected_codes)]
            except Exception as config_e:
                print(f"Fel vid läsning av config ur metadata: {config_e}")
                # Faller tillbaka på att visa alla kommuner
        # Om ingen metadata, eller inget urval – visa allt

        # ---- Panel rebuild och layout fixar ----
        def build_panels_with_selected():
            occ_panel = occspace_panel(
                replay_controller=replay,
                ui_state=ui_state,
                indiv_source=indiv_source,
                job_source=job_source,
                emp_source=emp_source
            )
            map_pnl = map_panel(
                replay_controller=replay,
                muni_gdf=muni_gdf_selected,
                selected_codes_or_names=selected_codes,
                layers=layers,
                gdf_layers=gdf_layers,
                ui_state=ui_state,
                indiv_source=indiv_source,
                emp_source=emp_source
            )
            return [occ_panel, map_pnl]

        new_tabs = build_panels_with_selected()
        tabs.tabs = new_tabs
        tabs.sizing_mode = "stretch_both"
        info_div.text = "<b>Dashboard uppdaterad!</b>"
    except Exception as e:
        tb = traceback.format_exc()
        info_div.text = f"<b>Kunde inte ladda run:</b><br>{e}<br><pre>{tb}</pre>"
        print(tb)


run_selector.on_change('value', on_run_selected)

# --- 11. Slutlig layout och app-init ---
layout = column(
    scenario_select,
    run_button,
    run_selector,
    info_div,
    tabs,
    sizing_mode="stretch_both"   # <-- Också här!
)
curdoc().add_root(layout)
curdoc().title = "WORM Dashboard (NY)"

print("NY PIPELINE IMPORTERAD!")
