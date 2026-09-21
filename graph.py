import psycopg
from psycopg.rows import dict_row
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver

from config import config
from state import TravelState, agent_order
from agents import (
    supervisor_agent,
    guardrail_blocked_agent,
    flight_agent,
    hotel_agent,
    weather_agent,
    budget_agent,
    itinerary_agent,
    human_approval_agent,
    master_agent
)


# Helper function to get database URL with sslmode
def get_database_url() -> str:
    database_url = config.DATABASE_URL
    if not database_url:
        raise ValueError("DATABASE_URL is not defined in the config")
    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"
    return database_url


# Routing Logic
ROUTE_MAP = {
    "guardrail_blocked": "guardrail_blocked",
    "flight_agent": "flight_agent",
    "hotel_agent": "hotel_agent",
    "weather_agent": "weather_agent",
    "budget_agent": "budget_agent",
    "itinerary_agent": "itinerary_agent",
}


def get_selected_agents(state: TravelState) -> list[str]:
    selected = state.get("selected_agents", [])
    return [agent for agent in agent_order if agent in selected]


def route_from_supervisor(state: TravelState) -> list[str]:
    """Parallel Fan-Out router: returns list of specialist agents to execute concurrently."""
    if not state.get("guardrail_allowed", True):
        return ["guardrail_blocked"]
    
    selected = get_selected_agents(state)
    specialists = [agent for agent in selected if agent != "itinerary_agent"]

    if specialists:
        return specialists
    return ["itinerary_agent"]


# Build LangGraph
graph = StateGraph(TravelState)

graph.add_node("supervisor_agent", supervisor_agent)
graph.add_node("guardrail_blocked", guardrail_blocked_agent)
graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("weather_agent", weather_agent)
graph.add_node("budget_agent", budget_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("human_approval", human_approval_agent)
graph.add_node("master_agent", master_agent)

# Entry edge
graph.add_edge(START, "supervisor_agent")

# Parallel Fan-Out: supervisor conditionally triggers multiple specialist agents concurrently
graph.add_conditional_edges("supervisor_agent", route_from_supervisor, ROUTE_MAP)

# Fan-In: All parallel specialists converge into itinerary_agent (barrier join)
graph.add_edge("flight_agent", "itinerary_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("weather_agent", "itinerary_agent")
graph.add_edge("budget_agent", "itinerary_agent")

# Sequential itinerary approval and master response synthesis
graph.add_edge("itinerary_agent", "human_approval")
graph.add_edge("human_approval", "master_agent")
graph.add_edge("master_agent", END)
graph.add_edge("guardrail_blocked", END)

# Postgres Checkpointer
DATABASE_URL = get_database_url()

conn = psycopg.connect(
    DATABASE_URL,
    autocommit=True,
    row_factory=dict_row
)

checkpointer = PostgresSaver(conn)
checkpointer.setup()

travel_graph = graph.compile(checkpointer=checkpointer)
