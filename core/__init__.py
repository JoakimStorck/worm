"""
WORM – Worker-Occupation-Region Model

Agentbaserad modell för simulering av arbetsmarknad: kompetens, geografi och matchning.
Modulstruktur:
- scenariobuilder
- world
- configreader
- plotting
- occupations.utils
- geography.geoworld
"""
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
