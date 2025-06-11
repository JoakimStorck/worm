# scripts/run_scenario.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.pipeline.run_scenario_pipeline import main

if __name__ == "__main__":
    main()
