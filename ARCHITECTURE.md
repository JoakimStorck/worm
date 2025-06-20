Utmärkt. Då får du en **ARCHITECTURE.md** med en genomgående röd tråd: vi börjar i pipelineflödet (”från scenario till analys”) och låter det strukturera dokumentet. Jag integrerar samtliga teman, så varje komponent sätts in i sitt sammanhang.

Nedan följer **struktur + utkast till varje sektion**. Jag föreslår att vi utgår från denna grund och sedan itererar – när du vill ha mer detaljer eller kodexempel är det bara att säga till.
Jag skriver på engelska och med en inledande överblick.

---

# ARCHITECTURE.md

## WORM: System Architecture

### Overview

WORM (Worker-Occupation-Region Model) is a modular, event-driven simulation platform for analyzing labor markets, commuting, and structural change. The architecture is organized around a pipeline pattern, enabling scenario-based simulations, stateful replay, and interactive exploration through a dashboard UI. The codebase is designed for extensibility, rapid iteration, and robust analysis of large synthetic labor market populations.

---

## 1. Pipeline-Driven System Design

**Everything starts with the pipeline.**
A scenario definition (YAML) enters the system and drives a chain of processes: world generation, simulation, logging, result collection, and dashboard visualization.

**Key Steps:**

1. **Scenario Selection:** User selects or provides a scenario configuration file.
2. **World & Data Generation:** The scenario is parsed to generate synthetic data (municipalities, employers, jobs, individuals).
3. **Simulation (Event-Driven):** Agents interact in an event-driven engine, producing a detailed event log.
4. **Result Packaging:** All data (individuals, jobs, employers, event logs, metadata) is saved under a unique run directory.
5. **Interactive Exploration:** The dashboard loads any run, replays simulation state, and enables interactive analysis via modular panels.

**Benefits:**

* Fully reproducible research (every run is logged with all inputs/outputs)
* Rapid switching between scenarios and results
* Extensible at each stage

---

## 2. Data Model: Employers, Jobs, Individuals

**Entities:**

* **Employers:** Organizations, each with a position in occupation space, size (number of jobs), and location.
* **Jobs:** Individual job positions, typed by skills, linked to employers.
* **Individuals:** Simulated people, each with skills (χ, ξ), history, and status (employed, searching, etc).

**Data Flow:**
Entities are generated deterministically from scenario parameters. The relationships are clear:

* Each job is assigned to an employer.
* Each individual is matched to jobs through occupation space proximity (skills).

**Storage:**
Data for each run is saved in separate CSVs, making it easy to analyze or reload at any point.

---

## 3. Occupation Space & Matching Algorithm

**Occupation Space:**
A multi-dimensional skill/competence space. Each job and individual is represented as a “bubble” (center + radius), making similarity and matching a geometric problem.

**Matching:**

* Individuals and jobs are matched based on proximity in occupation space (e.g., χ, ξ coordinates, possibly with H for skill breadth).
* Matching can be strict or allow for “soft constraints” (tolerance, elasticity).

**Algorithmic Note:**
Matching is flexible and can be extended (to multi-skill dimensions, sector-specific restrictions, etc).

---

## 4. Event-Driven Simulation Engine

**Core Principle:**
Rather than timestep-based evolution, WORM uses an **event-driven simulation**.

* Agents (individuals, employers) generate events (job search, match, quit, hire, etc).
* An event log is produced, containing every state change in the simulation.

**Replayability:**
The entire state of the system at any time can be reconstructed by replaying the event log.

**Advantages:**

* Accurate modeling of asynchronous dynamics
* Easy to implement intervention/”what if” scenarios by branching from any event
* Efficient scaling to large agent populations

---

## 5. Results Packaging & Run Management

Every simulation run is:

* **Saved in its own directory** (with timestamp and scenario name)
* **Packaged with:**

  * individuals.csv
  * jobs.csv
  * employers.csv
  * eventlog.csv
  * meta.yaml/metadata.txt

A central **run registry/index** keeps track of all available runs for selection in the dashboard.

**Why?**

* Ensures reproducibility and auditing
* Allows users to switch and compare results seamlessly

---

## 6. Visualization & Dashboard Architecture

**Panel-Based Modular UI:**

* **Panel Classes:**
  Each visualization/analysis component (”panel”) is a class with a standard interface:

  * Receives shared `replay_controller`, `ui_state`, and (if needed) extra arguments
  * Provides a `.layout` property (Bokeh LayoutDOM)

* **Panel Registry:**
  A dictionary mapping panel names to classes. This makes it easy to add new panels or replace existing ones without modifying dashboard logic.

* **PanelManager:**
  The orchestrator. Manages panel slots, lets users select panels to display, instantiates and swaps panels live (“hot-swap”), and keeps everything in sync with simulation state.

* **Plug-and-Play:**
  All panels listen to a shared replay/state, so selections, filters, or replay are always reflected across all views.

**Benefits:**

* Fast development of new visualizations
* Flexibility for users (any mix of panels can be shown, e.g. two stats panels)
* Separation of UI logic from business logic

---

## 7. State, Replay, and Filtering

**ReplayController:**
The linchpin for dashboard interaction. It replays the event log, reconstructs any simulation state, and exposes state to all panels.

**Filtering:**
Panels can implement interactive filters (by occupation, region, etc), and these filters are propagated across all visualizations.

**Consistent State:**
Selections, highlights, and user actions are synchronized through `ui_state`.

---

## 8. Database and Storage Layer

**Sqlite3 Database:**

* Holds static geographic and administrative data (municipalities, regions, etc).
* Used for scenario/world-building, not for dynamic simulation state.

**CSV & YAML/Metadata:**

* All dynamic simulation output is stored as flat files.
* Metadata ensures every run can be audited and reproduced.

**Design Rationale:**

* Flat files = easy to archive, version, and share
* DB only used for lookups needed at scenario-build time

---

## 9. Extensibility and Customization

**Adding a New Panel:**

1. Implement a new panel class (inherits shared interface, exposes `.layout`)
2. Add it to `PANEL_REGISTRY`
3. Optionally, declare required arguments in `KWARGS`
4. Instantly available for plug-and-play/hotswap in the UI

**Custom Simulation Logic:**

* New event types, agent behaviors, or matching logics can be added with minimal impact on the rest of the system.

---

## 10. Design Decisions

**Why event-driven?**

* Realistic modeling of agent actions and asynchronous dynamics

**Why occupation space?**

* Flexible abstraction for skill similarity, cluster analysis, and visualization

**Why plug-and-play dashboard?**

* Research evolves—new metrics and visualizations should be easy to add

---

## 11. Example Workflow

1. **Author a scenario:** YAML config, defines municipalities, employer/job/individual distributions, etc.
2. **Run the simulation:** World and agents generated, simulation runs, event log written.
3. **Explore in dashboard:** Select the run, replay events, switch between map/occupation/statistics panels, analyze results.
4. **Export:** Download filtered data, export visualizations.

---

## 12. File and Module Layout (for Developers)

* `pipeline/`: Entry point, pipeline and GUI logic.
* `core/`: Simulation logic, event system, scenario/world/data models, panel manager, etc.
* `core/visualization/`: Panel classes (occupation space, map, statistics, etc.)
* `data/`: Static data (sqlite3, geo files)
* `output/`: All run directories and registry
* `scenarios/`: Scenario YAML files

---

**This document is a living summary of WORM’s architectural intent.
Pull requests that extend or update core architecture should update this file.**

---

Vill du ha hela detta direkt i fil (med filnamn) eller vill du ha nästa steg/utveckling av någon sektion först – t.ex. ett fördjupat diagram, datamodell, eller kodlänkar till nyckelklasser?

Du kan när som helst säga till att jag ska läsa in mer ur kodbasen och utveckla varje avsnitt med kodreferenser, exempel, eller UML-liknande diagram.


# WORM Dashboard Architecture – Panel Module System and Hot-Swap

## Overview

The WORM interface is built on a **modular panel architecture** where all visual components (“panels”) are interchangeable and decoupled through a central manager system. This enables dynamic dashboard composition and real-time “hot-swapping” of panels during use—without restarting the app or hard-coding layouts.

The system is designed for:

* **Extensibility:** Add new panels or features without touching the core logic.
* **Reusability:** Panels implement a shared API and are constructed from standardized parameters.
* **Interactivity:** All panels update based on a common replay/state object, ensuring synchronized data and selections.

---

## Main Components

### 1. Panels (Panel Classes)

Each panel is a class following a unified interface. Examples:

* `OccupationSpacePanel`
* `MapPanel`
* `StatisticsPanel`

Panels receive (in `__init__`):

* **`replay_controller`**: access to current simulation state
* **`ui_state`**: shared state for things like selection and hover
* Panel-specific arguments (e.g., map data)

All panel classes must expose a **`layout`** attribute (a Bokeh LayoutDOM), which is the actual UI shown in the dashboard.

Each panel class may declare **`KWARGS`**—a list of parameter names it expects—enabling generic instantiation.

---

### 2. Panel Registry

A **panel registry** (`PANEL_REGISTRY`) gathers all available panels in a name-to-class mapping:

```python
PANEL_REGISTRY = {
    "Occupation Space": OccupationSpacePanel,
    "Map": MapPanel,
    "Statistics": StatisticsPanel,
    # Add more here…
}
```

---

### 3. PanelManager

**PanelManager** is the central controller handling which panels are displayed and active in the dashboard.

Features:

* Handles panel selection via dropdowns/selectors for each panel slot.
* Instantiates and initializes the correct panel class, using the registry and each panel’s KWARGS.
* Swaps panels live without disrupting the rest of the UI.
* Keeps the active panel set in sync and dynamically builds the dashboard layout (`self.layout`).

PanelManager is the key to the **plug-and-play** and **hot-swap** architecture: you can add, remove, or swap panels—and configure the number of panel slots—without changing any surrounding logic.

---

### 4. Dashboard Layout

Both PanelManager and the dashboard are built using **Bokeh’s layouts** (row, column), making the panel arrangement flexible and the UI directly reflect user choices.

---

### 5. Replay/State System

All panels are connected to a shared **ReplayController/state object**.
This guarantees all views, filters, selections, and statistics remain in sync and update as the simulation is replayed, stepped, or filtered.

---

## Benefits

* **Rapid development:** Add new analyses, maps, or visualizations with a single line in the registry and by implementing a panel class.
* **High flexibility:** Users can swap panels dynamically, e.g., display two different statistics panels side-by-side.
* **Robustness:** Shared data/state prevents inconsistency between panels.
* **Separation of concerns:** Panels, registry, and manager cleanly separate logic—making the system maintainable and testable.

---

## Example Usage

```python
# PanelRegistry
from core.visualization.occupation_space_panel import OccupationSpacePanel
from core.visualization.map_panel import MapPanel
from core.visualization.statistics_panel import StatisticsPanel

PANEL_REGISTRY = {
    "Occupation Space": OccupationSpacePanel,
    "Map": MapPanel,
    "Statistics": StatisticsPanel,
}

# Instantiate PanelManager with desired number of slots:
panel_manager = PanelManager(
    replay_controller,
    ui_state,
    PANEL_REGISTRY,
    panel_kwargs={...},   # e.g., muni_gdf, map data, etc.
    n_panels=2            # or more!
)

dashboard_layout.children[3:] = [panel_manager.layout]
```

---

## Extending

* Add new panels to `PANEL_REGISTRY` and implement the corresponding class.
* PanelManager can be easily adapted to more or fewer slots.
* Each panel can be made configurable and can communicate with others via shared state.

---

Want this as a ready-to-use file?
Need a diagram or extra code examples?
