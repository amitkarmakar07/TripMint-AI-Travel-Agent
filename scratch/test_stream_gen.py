import json
from backend import serialize_result
from graph import travel_graph
from state import empty_constraints
from langchain_core.messages import HumanMessage

def stream_travel_agent(user_input: str, thread_id: str = "test_sse_1"):
    run_config = {"configurable": {"thread_id": thread_id}}
    initial_input = {
        "messages": [HumanMessage(content=user_input)],
        "user_query": user_input,
        "guardrail_allowed": True,
        "guardrail_reason": "",
        "selected_agents": [],
        "trip_constraints": empty_constraints(),
        "supervisor_reasoning": "",
        "flight_results": "",
        "hotel_results": "",
        "weather_result": "",
        "budget_analysis": "",
        "itinerary": "",
        "approval_request": "",
        "approved": False,
        "human_feedback": "",
        "final_response": "",
        "llm_calls": 0
    }
    
    yield {"event": "start", "data": {"thread_id": thread_id, "query": user_input}}
    
    for chunk in travel_graph.stream(initial_input, config=run_config, stream_mode="updates"):
        for node_name, node_update in chunk.items():
            if node_name == "__interrupt__":
                continue
            yield {
                "event": "node_complete",
                "data": {
                    "node": node_name,
                    "thread_id": thread_id
                }
            }
            
    snapshot = travel_graph.get_state(run_config)
    interrupts = [t.interrupts for t in snapshot.tasks if t.interrupts]
    if interrupts:
        first_interrupt = interrupts[0][0]
        payload = getattr(first_interrupt, "value", first_interrupt)
        yield {
            "event": "interrupt",
            "data": {
                "thread_id": thread_id,
                "requires_approval": True,
                "draft_itinerary": payload.get("draft_itinerary", "")[:100]
            }
        }
    else:
        yield {
            "event": "complete",
            "data": {"status": "done"}
        }

for evt in stream_travel_agent("weather in London"):
    print("SSE Event:", evt["event"], evt["data"])
