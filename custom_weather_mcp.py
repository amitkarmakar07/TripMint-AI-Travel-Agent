from mcp.server.fastmcp import FastMCP
import requests
import os
from config import config

mcp = FastMCP("Weather-MCP")
OPENWEATHER_API_KEY = config.OPENWEATHER_API_KEY

@mcp.tool()
def get_current_weather(city :str) :
    response = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params = {
            "q" :city,
            "appid" : OPENWEATHER_API_KEY,
            "units" : "metric"
        }
    )

    data = response.json()

    if response.status_code != 200:
        return {"error": data.get("message", "Failed to fetch current weather")}
    
    return {
        "city" : data["name"],
        "temp_c" : data["main"]["temp"],
        "feels_like_c" : data["main"]["feels_like"],
        "humidity" : data["main"]["humidity"],
        "condition" : data["weather"][0]["description"]
    }

@mcp.tool()
def get_forecast(city : str) :
    url = ("https://api.openweathermap.org/data/2.5/forecast")
    
    params = {
        "q": city,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric"
    }

    response = requests.get(url, params=params)
    data = response.json()

    if response.status_code != 200:
        return {"error": data.get("message", "Failed to fetch forecast")}

    forecast_list = []

    for item in data.get("list", [])[:5] :
        forecast_list.append({
            "datetime" : item["dt_txt"],
            "temp_c" : item["main"]["temp"],
            "condition" : item["weather"][0]["description"]
        })
    
    return {
        "city" : city,
        "forecast" : forecast_list    
    }

if __name__ == "__main__" :
    mcp.run()