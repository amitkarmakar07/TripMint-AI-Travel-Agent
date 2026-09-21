from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from state import TravelState, empty_constraints, agent_order, known_agents
from llm import llm, light_llm, llm_call, json_from_llm


def supervisor_agent(state: TravelState):
    query = state["user_query"]
    llm_calls = state.get("llm_calls", 0)

    guardrail_prompt = f"""
    Determine whether the following request belongs to travel planning or travel information. Valid requests can include
    destination, flights, hotels, weather, budgets, visas, transportation, sightseeing, food, packing, or itineraries.

    Block clearly unrelated requests (not related to travel) and requests asking for harmful or illegal instructions. Do not block a valid
    travel request merely because some details are missing.

    Return strict JSON only:
    {{
        "allowed": true,
        "reason": "Short reason in English",
        "selected_agents": []
    }}

    User request: {query}
    """

    try:
        guardrail_response = light_llm.invoke([
            SystemMessage(content="You are the input guardrail for a travel-planning application. Return strict JSON only."),
            HumanMessage(content=guardrail_prompt)
        ])

        guardrail_json = json_from_llm(str(guardrail_response.content))
        allowed = bool(guardrail_json.get("allowed", True))
        reason = str(guardrail_json.get("reason", "")).strip()
        llm_calls += 1

    except Exception as exc:
        print(f"Guardrail Error: {exc}")
        allowed = True
        reason = "Guardrail validation fallback allowed the request."
    
    if not allowed:
        reason = reason or (
            "TripMint AI can only help with travel-planning and travel-related queries. "
            "Please ask about a destination, flight, hotel, or other travel-related topic."
        )
        return {
            "guardrail_allowed": False,
            "guardrail_reason": reason,
            "selected_agents": [],
            "trip_constraints": empty_constraints(),
            "supervisor_reasoning": reason,
            "final_response": reason,
            "messages": [AIMessage(content=f"Guardrail blocked request: {reason}")],
            "llm_calls": llm_calls
        }

    supervisor_prompt = f"""
    You are the supervisor of a multi-agent travel-planning system. Choose ONLY the specialist agents truly needed for the user's request.
    Available agents:
     - flight_agent: Select ONLY if the user asks about flights, airlines, airfare, or requires long-distance travel between cities/countries.
     - hotel_agent: Select ONLY if accommodation, hotels, resorts, or places to stay are relevant or requested.
     - weather_agent: Select ONLY if the user explicitly asks about weather, climate, season, forecast, packing advice, or best time of year to visit.
     - budget_agent: Select ONLY if the user explicitly mentions a budget (e.g. ₹X, $Y), asks for cost estimation, pricing, or financial feasibility.
     - itinerary_agent: Day-by-day itinerary planning, activities, sightseeing, and attractions (ALWAYS include this).

    Important rule: Do NOT select weather_agent or budget_agent unless the user query explicitly touches upon weather or budget considerations.

    Return strict JSON only using this schema:
    {{
        "selected_agents": ["itinerary_agent"],
        "trip_constraints": {{
            "destination": "",
            "origin": "",
            "duration": "",
            "budget": "",
            "travel_style": "",
            "special_preferences": []
        }},
        "reasoning": ""
    }}

    User request: {query}
    """

    try:
        supervisor_response = llm_call(
            "You are a travel specialist supervisor that analyzes user queries, extracts trip constraints, and selects required agents.",
            supervisor_prompt
        )
        supervisor_json = json_from_llm(supervisor_response)
        requested_agents = supervisor_json.get("selected_agents", [])
        selected_agents = [
            name for name in agent_order if name in requested_agents and name in known_agents
        ]

        if "itinerary_agent" not in selected_agents:
            selected_agents.append("itinerary_agent")
            
        constraints = empty_constraints()
        raw_constraints = supervisor_json.get("trip_constraints", {})

        if isinstance(raw_constraints, dict):
            constraints.update(raw_constraints)

        reasoning = str(supervisor_json.get("reasoning", "")).strip()
        llm_calls += 1
 
    except Exception as exc:
        print(f"Supervisor Error: {exc}")
        selected_agents = agent_order.copy()
        constraints = empty_constraints()
        reasoning = f"Supervisor Error: {exc}. Defaulting to all agents and empty constraints."
        
    return {
        "guardrail_allowed": True,
        "guardrail_reason": reason,
        "selected_agents": selected_agents,
        "trip_constraints": constraints,
        "supervisor_reasoning": reasoning,
        "final_response": "",
        "messages": [AIMessage(content="Supervisor created the agent plan.")],
        "llm_calls": llm_calls
    }


def guardrail_blocked_agent(state: TravelState):
    reason = (
        state.get("guardrail_reason")
        or state.get("final_response")
        or "Your request was blocked by the guardrail. TripMint AI can only help with travel-planning and travel-related queries."
    )
    return {
        "final_response": reason,
        "messages": [AIMessage(content=reason)]
    }
