import os
import uuid
import operator
import certifi
import psycopg
from typing import TypedDict, Annotated
from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage, SystemMessage
from langchain_groq import ChatGroq

from config import config
from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights

# SSL Certificate Setup
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()


# Helper function to get database URL with sslmode
def get_database_url():
    database_url = config.DATABASE_URL
    if not database_url:
        raise ValueError("DATABASE_URL is not defined in the config")
    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"
    return database_url


# API Key Setup for LLM
llm_api_key = config.GROQ_API_KEY
if not llm_api_key:
    raise ValueError("GROQ_API_KEY not found in config")

llm = ChatGroq(
    model="qwen/qwen3.8-27b",
    api_key=llm_api_key,
    temperature=0.7
)


# Define Travel State
class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    flight_results: str
    hotel_results: str
    itinerary: str
    llm_calls: int


# Defining Agents
def flight_agent(state: TravelState):
    query = state["user_query"]
    flight_data = search_flights(query, limit=3)

    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(content="Flight results fetched successfully.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


def hotel_agent(state: TravelState):
    query = f"Best hotels for {state['user_query']}"
    hotel_results = tavily_search(query)

    return {
        "hotel_results": hotel_results,
        "messages": [
            AIMessage(content="Hotel results fetched successfully.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


def itinerary_agent(state: TravelState):
    prompt = f"""You are a world class travel planning agent. Create a complete
travel itinerary for the following user request.

User Request:
{state['user_query']}

Flight Results:
{state['flight_results']}

Hotel Results:
{state['hotel_results']}

Make the itinerary practical, budget-aware, and easy to follow.
"""

    response = llm.invoke([
        SystemMessage(content="You are a world class travel planning agent."),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


def master_agent(state: TravelState):
    final_prompt = f"""Generate the final travel response for the user.

User Request: 
{state["user_query"]}

Flight Information:
{state['flight_results']}

Hotel Suggestions:
{state['hotel_results']}

Itinerary:
{state['itinerary']}

Format the final answer beautifully and clearly using these sections:
1. Trip Summary
2. Flight Information
3. Hotel Suggestions
4. Day to Day Itinerary
5. Estimated Budget
6. Final Recommendations

Important:
- Be clear, practical, and structured.
- Mention that live flight API may not provide ticket prices if pricing is unavailable.
- Keep the response useful for real travel planning.
"""

    response = llm.invoke([
        SystemMessage(content="You are a professional AI travel booking assistant."),
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


# Graph Builder
graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("master_agent", master_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "master_agent")
graph.add_edge("master_agent", END)


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


# Primary function to execute the graph
def run_travel_agent(user_input: str, thread_id: str = None):
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    run_config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    result = travel_graph.invoke(
        {
            "messages": [HumanMessage(content=user_input)],
            "user_query": user_input,
            "flight_results": "",
            "hotel_results": "",
            "itinerary": "",
            "llm_calls": 0
        },
        config=run_config
    )

    final_answer = result["messages"][-1].content

    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_results", "results not found"),
        "hotel_results": result.get("hotel_results", "results not found"),
        "itinerary": result.get("itinerary", "results not found"),
        "llm_calls": result.get("llm_calls", 0)
    }
