import urllib.request
import urllib.parse
import json
from langchain_core.tools import tool

# WMO weather interpretation codes → human-readable descriptions
_WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
}


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode())


@tool
def weather(city: str) -> str:
    """
    Returns the current weather conditions for a given city.
    Use this tool whenever the user asks about the weather, temperature, or conditions in a location.
    Input should be a city name (e.g. 'São Paulo', 'London', 'Tokyo').
    """
    # Step 1: geocode the city name → lat/lon
    geo_url = (
        "https://geocoding-api.open-meteo.com/v1/search?"
        + urllib.parse.urlencode({"name": city, "count": 1, "language": "en", "format": "json"})
    )
    try:
        geo_data = _fetch_json(geo_url)
    except Exception as e:
        return f"Could not reach the geocoding service: {e}"

    results = geo_data.get("results")
    if not results:
        return f"Could not find a location named '{city}'. Please try a different city name."

    location = results[0]
    lat = location["latitude"]
    lon = location["longitude"]
    display_name = f"{location['name']}, {location.get('country', '')}"

    # Step 2: fetch current weather from Open-Meteo
    weather_url = (
        "https://api.open-meteo.com/v1/forecast?"
        + urllib.parse.urlencode({
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "wind_speed_unit": "kmh",
        })
    )
    try:
        weather_data = _fetch_json(weather_url)
    except Exception as e:
        return f"Could not reach the weather service: {e}"

    current = weather_data.get("current", {})
    units = weather_data.get("current_units", {})

    temp = current.get("temperature_2m", "N/A")
    humidity = current.get("relative_humidity_2m", "N/A")
    wind = current.get("wind_speed_10m", "N/A")
    code = current.get("weather_code", -1)
    condition = _WMO_CODES.get(code, "Unknown conditions")

    return (
        f"Weather in {display_name}:\n"
        f"  Condition : {condition}\n"
        f"  Temperature: {temp}{units.get('temperature_2m', '°C')}\n"
        f"  Humidity   : {humidity}{units.get('relative_humidity_2m', '%')}\n"
        f"  Wind speed : {wind}{units.get('wind_speed_10m', ' km/h')}"
    )
