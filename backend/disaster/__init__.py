"""Disaster Domain Package for Spiritus.

Provides resilient real-world public data feeds and SQLite-backed scenario simulation engines.
"""
from disaster.live_feeds import (
    fetch_earthquakes,
    fetch_wildfires,
    fetch_regional_weather,
    get_all_disaster_feeds,
)
from disaster.scenario_engine import (
    init_scenario_db,
    get_exercise_summary,
    find_safe_evacuation_route,
    inject_scenario_shock,
    reset_scenario_to_baseline,
)

__all__ = [
    "fetch_earthquakes",
    "fetch_wildfires",
    "fetch_regional_weather",
    "get_all_disaster_feeds",
    "init_scenario_db",
    "get_exercise_summary",
    "find_safe_evacuation_route",
    "inject_scenario_shock",
    "reset_scenario_to_baseline",
]
