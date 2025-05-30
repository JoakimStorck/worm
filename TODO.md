# TODO – WORM Project

## Project Goals (summary)

- Build a synthetic, agent-based labor market model with individuals, occupations, and regions
- Integrate SCB and O*NET data for both real and synthetic geographies
- Enable flexible modeling at multiple geographical scales (nation, region, municipality, zone)
- Store all data and results in a local SQLite database for reproducibility
- Provide tools for matching, commuting, and analysis of labor market dynamics
- Support scenario testing and stepwise demos for each core function

## Data Collection and Storage

* [x] Retrieve data on number of workplaces and employees per SNI code and municipality (2020)
* [x] **Demo:** Read and display number of municipalities and variables from SCB data
* [ ] Retrieve complementary data on demography, education level, and municipality area (from SCB)
* [ ] **Demo:** Read and display population, area, and education level per municipality
* [x] Use SQLite as a local database
* [x] Build a database structure to store SCB data, O\*NET transformations, and metadata
* [x] **Demo:** Save and load data to/from SQLite – display contents as DataFrame
* [ ] Save transformed O\*NET data to SQLite
* [x] Link SCB data to municipality type classification (SCB municipal groups)

---

### A) Geography Modeling and Structure

* [x] Define YAML-based structure for municipalities, urban areas, small towns, and regions
* [x] Implement corresponding Python classes: Nation, Region, Municipality, Zone

  * [ ] **Demo:** Load and visualize the structure of a municipality (e.g., Falun) from YAML
* [ ] Implement import/export to/from YAML (including support for variable granularity)
* [ ] Build SQL tables for nation, region, municipality, and zone – with code, name, area, centroid (and optionally bounding box/polygon)
* [ ] Link locations (workplaces/residences) to all relevant geographical levels (municipality, region, zone)
* [ ] Enable a variable number of zones per municipality (scalable granularity, one or many zones possible)

  * [ ] **Demo:** Visualize a municipality with both 1 and N zones
* [ ] Enable modeling and analysis at all geographical levels (nation, region, municipality, zone)
* [ ] Ensure table and class design allows for future extensions (additional levels, polygons, etc.)

  * [ ] **Demo:** Create and save a region combining multiple municipalities

---

### B) Generation of Typmunicipalities and Regions

* [ ] Create and load YAML profiles for typmunicipalities (e.g., “industrial inland town, 30,000 inhabitants”) and regions

  * [ ] **Demo:** Load a typmunicipality from YAML and display its key attributes
* [ ] Train a KNN model on Swedish municipality data (and optionally zone data) to generate new synthetic municipalities based on real statistics

  * [ ] **Demo:** Run KNN and display nearest real municipalities to a given profile
  * [ ] **Demo:** Generate a synthetic municipality profile via KNN from YAML specification
* [ ] Generate regions by combining multiple synthetic municipalities
* [ ] Create semantic profiles in YAML for different types of municipalities (e.g., metropolitan, suburb, small town, rural)
* [ ] Implement a pipeline to randomly generate synthetic regions/labor market areas from profiles and KNN

---

### C) Stepwise Allocation of Workplaces and Residences to Zones

* [ ] **Step 1: Random allocation**

  * Implement random allocation (e.g., Dirichlet) of workplaces/residences to zones (always summing to the municipality total)
  * **Demo:** Generate and visualize such a random allocation
* [ ] **Step 2: Rule-based/static allocation**

  * Define and use standard weights for zone types (e.g., CBD, industrial, residential)
  * **Demo:** Show difference compared to random allocation
* [ ] **Step 3: KNN-based allocation**

  * Collect statistics on real-world zone distributions per typmunicipality
  * Implement a KNN-based method to generate realistic zone weights based on similar municipalities
  * **Demo:** Generate a synthetic municipality with KNN-based zone allocation

---

### D) Integration and Documentation

* [ ] Always allocate workplaces and residences to both zone and municipality so that totals match at the municipality level
* [ ] Document the structure and logic for geography and zone allocation (README or a dedicated data dictionary)
* [ ] Make it easy to switch allocation strategy (random, rule-based, KNN) via parameter or config
* [ ] Integrate new geography and allocation logic with the SQLite database structure

  * [ ] **Demo:** Visualize (simply) the generated municipalities/regions and their distribution of workplaces/residences

---

## Matching and Simulation

* [ ] Model matching between workers and occupations based on O\*NET positions

  * [ ] **Demo:** Simulate simple labor market matching in one municipality
* [ ] Implement function to simulate commuting patterns between municipalities

  * [ ] **Demo:** Show commuting flows between two municipalities/regions
* [ ] Allow overlap between workforce and residence location (commuting)

---

## Visualization and Analysis

* [ ] **Demo:** Visualize municipality distribution and labor market structure with matplotlib/seaborn
* [ ] Develop tools to visualize simulated labor markets and commuting flows
* [ ] **Demo:** Export data to GeoJSON/CSV and show example of external analysis
* [ ] Develop methods to measure entropy, clustering, and matching quality in simulations

---

Last updated: 2025-05-29

