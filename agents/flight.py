import asyncio
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from state import TravelState
from llm import light_llm
from config import config
from mcp_clients import aviation_mcp_search, tavily_mcp_search

FLIGHT_AGENT_PROMPT = """
You are an expert aviation flight planner. Your task is to analyze live flight schedule data and route timetables to provide top flight recommendations with realistic/live flight names, flight numbers, departure times, and arrival times.

User Trip Query: {query}
Departure Airport IATA: {dep_code}
Destination Airport IATA: {arr_code}

Live Departure Airport Activity (AviationStack MCP):
{live_schedule}

Route Timetable & Airline Schedules (Tavily MCP):
{route_info}

Provide an authoritative, beautifully structured response strictly using these sections:

### 1. Best Recommended Flight Options (Names & Schedules)
Provide 2 to 3 top recommended flight choices (Direct or Optimal 1-Stop Connections). For each option, clearly specify:
- **Flight Name & Carrier:** (e.g., Emirates, Air India, Turkish Airlines, Lufthansa)
- **Flight Number:** (e.g., AI101, TK717 / TK1027, LH761)
- **Scheduled Departure Time:** (e.g., 06:15 AM from {dep_code} Terminal 3)
- **Scheduled Arrival Time:** (e.g., 14:30 PM at destination)
- **Flight Duration & Layover:** (e.g., 10h 45m with 1h 50m layover)
- **Why This Flight:** (e.g., Best morning departure, shortest layover, premium comfort)

### 2. Likely Departure & Arrival Airports
- **Departure Airport:** [Airport Name, IATA Code, City, Terminal]
- **Arrival Airport:** [Airport Name, IATA Code, City, Terminal]

### 3. Airlines Serving This Route
List key international and domestic carriers with typical frequencies.

### 4. Typical Flight Duration & Layovers
Details on direct flight times vs connecting hub options (e.g., via Dubai, Doha, Istanbul, Frankfurt).

### 5. Estimated Airfare Range
- **Economy Class:** [Range in INR / local currency, Round Trip]
- **Business / Premium Class:** [Range in INR / local currency, Round Trip]

### 6. Peak Season Warning & Surcharges
Seasonal variations, holiday rushes, and price volatility alerts.

### 7. Strategic Booking Advice
Best advance booking window, preferred departure days, and baggage considerations.

Ensure each section is clearly labeled and easy for travelers to act upon.
"""


def flight_agent(state: TravelState):
    query = state["user_query"]

    try:
        from tools.flight_tool import parse_route
        dep_iata, arr_iata = parse_route(query)
        dep_code = dep_iata or getattr(config, "DEFAULT_ORIGIN_IATA", "DEL") or "DEL"
        arr_code = arr_iata or "Destination"

        # 1. AviationStack MCP: live flight departure schedule
        live_schedule_str = ""
        try:
            sched = asyncio.run(aviation_mcp_search("flight_arrival_departure_schedule", {
                "airport_iata_code": dep_code,
                "schedule_type": "departure",
                "limit": 10
            }))
            live_schedule_str = str(sched)[:3000]
        except Exception as err:
            live_schedule_str = f"AviationStack schedule note: {err}"

        # 2. Tavily MCP: route flight schedules, best times, and airlines
        route_info_str = ""
        try:
            route_query = f"flight options and schedule from {dep_code} to {query} airlines flight times departure arrival duration"
            route_info = asyncio.run(tavily_mcp_search(route_query))
            route_info_str = str(route_info)[:3000]
        except Exception as err:
            route_info_str = f"Route flight search note: {err}"

        prompt = FLIGHT_AGENT_PROMPT.format(
            query=query,
            dep_code=dep_code,
            arr_code=arr_code,
            live_schedule=live_schedule_str,
            route_info=route_info_str
        )

        flight_response = light_llm.invoke([
            SystemMessage(content="You are an expert travel flight planner."),
            HumanMessage(content=prompt)
        ])
        flight_data = str(flight_response.content)
        
    except Exception as e:
        flight_data = f"Unable to fetch flight data: {str(e)}"

    return {
        "flight_results": flight_data,
        "messages": [AIMessage(content="Flight recommendation generated.")],
        "llm_calls": 1
    }
