"""Unit tests for public live disaster feeds: caching, structure, and offline resilience.
"""
import asyncio
import unittest
from unittest.mock import patch, MagicMock

from disaster.live_feeds import (
    fetch_earthquakes,
    fetch_wildfires,
    fetch_regional_weather,
    get_all_disaster_feeds,
    _CACHE,
)


class TestLiveFeedsUnit(unittest.TestCase):
    def setUp(self):
        # Reset cache before test
        _CACHE["earthquakes"] = {"data": None, "fetched_at": 0.0, "status": "uninitialized", "source": "USGS M2.5+ Day"}
        _CACHE["wildfires"] = {"data": None, "fetched_at": 0.0, "status": "uninitialized", "source": "NASA EONET Wildfires"}
        _CACHE["weather"] = {"data": {}, "fetched_at": 0.0, "status": "uninitialized", "source": "Open-Meteo API"}

    def test_earthquakes_offline_fallback(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Seed cache
        _CACHE["earthquakes"]["data"] = [{"id": "cached_01", "title": "Test Quake", "mag": 4.5}]
        _CACHE["earthquakes"]["fetched_at"] = 1000.0

        # Simulate network error with timeout 0.001
        res = loop.run_until_complete(fetch_earthquakes(force=True, timeout=0.0001))
        self.assertTrue(res["stale"])
        self.assertEqual(res["status"], "stale_cached")
        self.assertEqual(len(res["events"]), 1)
        self.assertEqual(res["events"][0]["id"], "cached_01")

        loop.close()

    def test_wildfires_offline_fallback(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        _CACHE["wildfires"]["data"] = [{"id": "wf_01", "title": "Cached Fire"}]
        _CACHE["wildfires"]["fetched_at"] = 1000.0

        res = loop.run_until_complete(fetch_wildfires(force=True, timeout=0.0001))
        self.assertTrue(res["stale"])
        self.assertEqual(res["status"], "stale_cached")
        self.assertEqual(len(res["events"]), 1)

        loop.close()

    def test_weather_offline_fallback(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        res = loop.run_until_complete(fetch_regional_weather(lat=17.68, lon=83.21, timeout=0.0001))
        self.assertTrue(res["stale"])
        self.assertEqual(res["type"], "forecast")
        self.assertIn("temperature", res)

        loop.close()


if __name__ == "__main__":
    unittest.main()
