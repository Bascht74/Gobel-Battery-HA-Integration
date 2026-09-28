"""Load BMS modules without importing the Home Assistant package entry point."""

import sys
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "gobel_battery"
sys.path.insert(0, str(COMPONENT))
