import asyncio
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from state import TravelState
from llm import light_llm, parse_mcp_output
from mcp_clients import weather_mcp_search


def weather_agent(state: TravelState):
    query = state.get("user_query", "")
    constraints_dest = state.get("trip_constraints", {}).get("destination", "")

    # Use fast lightweight LLM for city extraction
    response = light_llm.invoke([
        SystemMessage(content="""You are a travel location extraction assistant. Identify the primary destination city for weather lookup.
If a specific city is mentioned (e.g. Paris, Tokyo, Mumbai), return that city name.
If only a country or region is mentioned (e.g. Bulgaria, Japan, France), return its primary capital or major destination city (e.g. Bulgaria -> Sofia, Japan -> Tokyo, France -> Paris).
If no destination can be identified, return 'None'.
Return ONLY the city name with no extra punctuation or words."""),
        HumanMessage(content=f"User Query: {query}\nKnown Destination: {constraints_dest}")
    ])

    location = str(response.content).strip().rstrip(".").strip()

    try:
        if not location or location.lower() in ["none", "location not found", "'none'", "\"none\""]:
            weather_data_str = "No specific destination city found for weather forecast."
        else:
            weather_raw = asyncio.run(weather_mcp_search(location))
            current = parse_mcp_output(weather_raw.get("current_weather")) if isinstance(weather_raw, dict) else {}
            forecast_raw = parse_mcp_output(weather_raw.get("forecast")) if isinstance(weather_raw, dict) else {}

            if isinstance(current, dict) and "temp_c" in current:
                city_name = current.get("city", location)
                temp = current.get("temp_c", "N/A")
                feels = current.get("feels_like_c", "N/A")
                humidity = current.get("humidity", "N/A")
                cond = str(current.get("condition", "N/A")).title()

                weather_md = f"### Current Weather in {city_name}\n\n"
                weather_md += f"- **Condition:** {cond}\n"
                weather_md += f"- **Temperature:** {temp}°C (Feels like: {feels}°C)\n"
                weather_md += f"- **Humidity:** {humidity}%\n\n"

                forecast_items = forecast_raw.get("forecast", []) if isinstance(forecast_raw, dict) else []
                if forecast_items:
                    weather_md += "### Upcoming Forecast\n\n"
                    for item in forecast_items[:5]:
                        dt = item.get("datetime", "")
                        t = item.get("temp_c", "")
                        c = str(item.get("condition", "")).title()
                        weather_md += f"- **{dt}:** {t}°C, {c}\n"

                weather_data_str = weather_md.strip()
            elif isinstance(current, dict) and "error" in current:
                weather_data_str = f"Weather data currently unavailable for {location}: {current.get('error')}"
            else:
                weather_data_str = f"Weather data for {location} could not be retrieved."

    except Exception as e:
        weather_data_str = f"Error fetching weather: {str(e)}"

    return {
        "weather_result": weather_data_str,
        "messages": [AIMessage(content="Weather result fetched successfully.")],
        "llm_calls": 1
    }
