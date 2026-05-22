#!/usr/bin/env python3
"""
app.py - Flask web API that returns current weather for Jersey City NJ (07306)
Uses OpenWeatherMap free tier API.

Environment variables required:
    WEATHER_API_KEY  - your OpenWeatherMap API key

Run locally:
    export WEATHER_API_KEY=your_key_here
    python3 app.py
"""

import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

# --- Config ---------------------------------------------------------------
ZIP_CODE = "07306"
COUNTRY  = "us"
UNITS    = "imperial"   # Fahrenheit; change to "metric" for Celsius
OWM_URL  = "https://api.openweathermap.org/data/2.5/weather"


def get_api_key():
    """Read API key from environment variable — never hardcode secrets."""
    key = os.environ.get("WEATHER_API_KEY")
    if not key:
        raise RuntimeError(
            "WEATHER_API_KEY environment variable is not set. "
            "Run: export WEATHER_API_KEY=your_key_here"
        )
    return key


# --- Routes ---------------------------------------------------------------

@app.route("/")
def index():
    """Health check — useful in Docker/OpenShift to confirm the app is up."""
    return jsonify({"status": "ok", "message": "Weather API is running"})


@app.route("/weather")
def weather():
    """Return current weather for Jersey City NJ."""
    try:
        api_key = get_api_key()
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    params = {
        "zip":   f"{ZIP_CODE},{COUNTRY}",
        "appid": api_key,
        "units": UNITS,
    }

    try:
        response = requests.get(OWM_URL, params=params, timeout=5)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        return jsonify({"error": "Weather API timed out"}), 504
    except requests.exceptions.HTTPError as e:
        return jsonify({"error": f"Weather API error: {e}"}), 502
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Request failed: {e}"}), 502

    data = response.json()

    result = {
        "city":        data["name"],
        "zip":         ZIP_CODE,
        "temp_f":      data["main"]["temp"],
        "feels_like_f": data["main"]["feels_like"],
        "temp_min_f":  data["main"]["temp_min"],
        "temp_max_f":  data["main"]["temp_max"],
        "humidity":    data["main"]["humidity"],
        "description": data["weather"][0]["description"],
        "wind_mph":    data["wind"]["speed"],
    }

    return jsonify(result)


# --- Main -----------------------------------------------------------------

if __name__ == "__main__":
    # host="0.0.0.0" is required for Docker — makes the app reachable
    # from outside the container, not just localhost
    app.run(host="0.0.0.0", port=5000, debug=True)