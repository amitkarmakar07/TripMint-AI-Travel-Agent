import operator
from typing import TypedDict, Annotated, Any
from langchain_core.messages import AnyMessage


class TravelState(TypedDict):
    # input
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str

    # guardrail results
    guardrail_allowed: bool
    guardrail_reason: str
    selected_agents: list[str]
    trip_constraints: dict[str, Any]
    supervisor_reasoning: str
    
    # agents results
    flight_results: str
    hotel_results: str
    weather_result: str
    budget_analysis: str
    itinerary: str
    
    # human in the loop
    approval_request: str
    approved: bool
    human_feedback: str
    final_response: str
    llm_calls: Annotated[int, operator.add]


known_agents = [
    "flight_agent",
    "hotel_agent",
    "weather_agent",
    "budget_agent",
    "itinerary_agent"
]

agent_order = [
    "flight_agent",
    "hotel_agent",
    "weather_agent",
    "budget_agent",
    "itinerary_agent"
]


def empty_constraints() -> dict[str, Any]:
    return {
        "destination": "",
        "origin": "",
        "duration": "",
        "budget": "",
        "travel_style": "",
        "special_preferences": []
    }
