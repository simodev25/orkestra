"""Weather MCP — Real API calling Open Meteo (free, no API key).

Example usage:
  await get_weather(city="Paris")
  await get_weather(city="London", days=3)
"""

import httpx
from agentscope.tool import ToolResponse
from agentscope.message import TextBlock
import json

# City → coordinates mapping (extendable)
CITY_COORDS = {
    "paris": (48.8566, 2.3522),
    "london": (51.5074, -0.1278),
    "new york": (40.7128, -74.0060),
    "tokyo": (35.6762, 139.6503),
    "berlin": (52.5200, 13.4050),
    "casablanca": (33.5731, -7.5898),
    "dubai": (25.2048, 55.2708),
    "sydney": (-33.8688, 151.2093),
}


async def get_weather(city: str = "Paris", days: int = 1) -> ToolResponse:
    """Get current weather and forecast for a city using Open Meteo API.

    Args:
        city: City name (e.g., 'Paris', 'London', 'Tokyo').
        days: Number of forecast days (1-7).
    """
    city_lower = city.lower().strip()
    coords = CITY_COORDS.get(city_lower)
    if not coords:
        return ToolResponse(content=[TextBlock(
            type="text",
            text=json.dumps({"error": f"City '{city}' not found. Available: {', '.join(CITY_COORDS.keys())}"})
        )])

    lat, lon = coords
    days = min(max(days, 1), 7)

    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,wind_speed_10m,relative_humidity_2m,weather_code"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code"
        f"&forecast_days={days}"
        f"&timezone=auto"
    )

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    current = data.get("current", {})
    daily = data.get("daily", {})

    result = {
        "city": city,
        "coordinates": {"lat": lat, "lon": lon},
        "current": {
            "temperature_c": current.get("temperature_2m"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "humidity_percent": current.get("relative_humidity_2m"),
            "weather_code": current.get("weather_code"),
        },
        "forecast": [
            {
                "date": daily["time"][i] if "time" in daily else None,
                "max_c": daily["temperature_2m_max"][i] if "temperature_2m_max" in daily else None,
                "min_c": daily["temperature_2m_min"][i] if "temperature_2m_min" in daily else None,
                "precipitation_mm": daily["precipitation_sum"][i] if "precipitation_sum" in daily else None,
            }
            for i in range(min(days, len(daily.get("time", []))))
        ],
        "source": "Open Meteo API (free, no key)",
    }

    return ToolResponse(content=[TextBlock(type="text", text=json.dumps(result, indent=2))])
