"""Live public data feeds for Spiritus disaster observation view.

Integrates:
- USGS M2.5+ Earthquake Feed (GeoJSON)
- NASA EONET Open Wildfire Feed (GeoJSON/JSON)
- Open-Meteo Regional Weather & Forecast (JSON)

Provides caching, freshness metadata, stale/offline fallback, and strict separation
of observed ground truth vs forecasts.
"""
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("spiritus.feeds")

USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
NASA_EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events?category=wildfires&status=open"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# In-memory feed cache
_CACHE: Dict[str, Dict[str, Any]] = {
    "earthquakes": {"data": None, "fetched_at": 0.0, "status": "uninitialized", "source": "USGS M2.5+ Day"},
    "wildfires": {"data": None, "fetched_at": 0.0, "status": "uninitialized", "source": "NASA EONET Wildfires"},
    "weather": {"data": {}, "fetched_at": 0.0, "status": "uninitialized", "source": "Open-Meteo API"},
}
CACHE_TTL = 300.0  # 5 minutes


async def fetch_earthquakes(force: bool = False, timeout: float = 6.0) -> Dict[str, Any]:
    """Fetches USGS M2.5+ day earthquakes with in-memory caching."""
    now = time.time()
    cached = _CACHE["earthquakes"]
    if not force and cached["data"] is not None and (now - cached["fetched_at"] < CACHE_TTL):
        return {
            "source": cached["source"],
            "fetched_at": cached["fetched_at"],
            "stale": False,
            "status": "cached",
            "type": "observation",
            "events": cached["data"]
        }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(USGS_URL)
            if resp.status_code == 200:
                geo = resp.json()
                features = geo.get("features", [])
                events = []
                for f in features:
                    props = f.get("properties", {})
                    geom = f.get("geometry", {})
                    coords = geom.get("coordinates", [0, 0, 0])
                    events.append({
                        "id": f.get("id", ""),
                        "title": props.get("title", "Earthquake"),
                        "mag": props.get("mag", 0.0),
                        "place": props.get("place", "Unknown"),
                        "time": props.get("time", 0),
                        "lat": coords[1] if len(coords) > 1 else 0.0,
                        "lon": coords[0] if len(coords) > 0 else 0.0,
                        "depth": coords[2] if len(coords) > 2 else 0.0,
                        "category": "earthquake",
                        "significance": props.get("sig", 0),
                    })
                cached["data"] = events
                cached["fetched_at"] = now
                cached["status"] = "live"
                return {
                    "source": cached["source"],
                    "fetched_at": now,
                    "stale": False,
                    "status": "live",
                    "type": "observation",
                    "count": len(events),
                    "events": events
                }
    except Exception as e:
        logger.warning(f"Error fetching USGS earthquakes: {e}")

    # Fallback to existing cache if available
    if cached["data"] is not None:
        return {
            "source": cached["source"],
            "fetched_at": cached["fetched_at"],
            "stale": True,
            "status": "stale_cached",
            "type": "observation",
            "count": len(cached["data"]),
            "events": cached["data"]
        }

    return {
        "source": cached["source"],
        "fetched_at": 0.0,
        "stale": True,
        "status": "unavailable",
        "type": "observation",
        "count": 0,
        "events": []
    }


async def fetch_wildfires(force: bool = False, timeout: float = 6.0) -> Dict[str, Any]:
    """Fetches NASA EONET active wildfires with in-memory caching."""
    now = time.time()
    cached = _CACHE["wildfires"]
    if not force and cached["data"] is not None and (now - cached["fetched_at"] < CACHE_TTL):
        return {
            "source": cached["source"],
            "fetched_at": cached["fetched_at"],
            "stale": False,
            "status": "cached",
            "type": "observation",
            "events": cached["data"]
        }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(NASA_EONET_URL)
            if resp.status_code == 200:
                body = resp.json()
                raw_events = body.get("events", [])
                events = []
                for ev in raw_events:
                    geom = ev.get("geometry", [])
                    latest_coord = geom[-1] if geom else {}
                    coords = latest_coord.get("coordinates", [0, 0])
                    events.append({
                        "id": ev.get("id", ""),
                        "title": ev.get("title", "Wildfire"),
                        "category": "wildfire",
                        "lat": coords[1] if len(coords) > 1 else 0.0,
                        "lon": coords[0] if len(coords) > 0 else 0.0,
                        "date": latest_coord.get("date", ""),
                        "sources": [s.get("id") for s in ev.get("sources", [])],
                    })
                cached["data"] = events
                cached["fetched_at"] = now
                cached["status"] = "live"
                return {
                    "source": cached["source"],
                    "fetched_at": now,
                    "stale": False,
                    "status": "live",
                    "type": "observation",
                    "count": len(events),
                    "events": events
                }
    except Exception as e:
        logger.warning(f"Error fetching NASA EONET wildfires: {e}")

    if cached["data"] is not None:
        return {
            "source": cached["source"],
            "fetched_at": cached["fetched_at"],
            "stale": True,
            "status": "stale_cached",
            "type": "observation",
            "count": len(cached["data"]),
            "events": cached["data"]
        }

    return {
        "source": cached["source"],
        "fetched_at": 0.0,
        "stale": True,
        "status": "unavailable",
        "type": "observation",
        "count": 0,
        "events": []
    }


async def fetch_regional_weather(lat: float = 17.6868, lon: float = 83.2185, timeout: float = 6.0) -> Dict[str, Any]:
    """Fetches regional weather and wind from Open-Meteo API. Strictly marked as forecast."""
    now = time.time()
    cache_key = f"{round(lat, 2)}_{round(lon, 2)}"
    if cache_key in _CACHE["weather"]:
        entry = _CACHE["weather"][cache_key]
        if now - entry["fetched_at"] < CACHE_TTL:
            return entry["data"]

    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        "hourly": "temperature_2m,relativehumidity_2m,windspeed_10m,precipitation",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(OPEN_METEO_URL, params=params)
            if resp.status_code == 200:
                w = resp.json()
                curr = w.get("current_weather", {})
                res = {
                    "source": "Open-Meteo API",
                    "fetched_at": now,
                    "stale": False,
                    "status": "live",
                    "type": "forecast",
                    "location": {"lat": lat, "lon": lon},
                    "temperature": curr.get("temperature"),
                    "windspeed": curr.get("windspeed"),
                    "winddirection": curr.get("winddirection"),
                    "weathercode": curr.get("weathercode"),
                }
                _CACHE["weather"][cache_key] = {"data": res, "fetched_at": now}
                return res
    except Exception as e:
        logger.warning(f"Error fetching Open-Meteo weather: {e}")

    return {
        "source": "Open-Meteo API",
        "fetched_at": 0.0,
        "stale": True,
        "status": "unavailable",
        "type": "forecast",
        "location": {"lat": lat, "lon": lon},
        "temperature": 28.0,
        "windspeed": 12.0,
        "winddirection": 180,
    }


async def get_all_disaster_feeds(lat: float = 17.6868, lon: float = 83.2185) -> Dict[str, Any]:
    """Aggregates all public disaster feeds concurrently."""
    quakes_task = fetch_earthquakes()
    fires_task = fetch_wildfires()
    weather_task = fetch_regional_weather(lat, lon)
    quakes, fires, weather = await asyncio.gather(quakes_task, fires_task, weather_task)
    return {
        "timestamp": time.time(),
        "earthquakes": quakes,
        "wildfires": fires,
        "weather": weather,
    }
