import uuid
import json
from typing import Any, Generator
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from state import TravelState, empty_constraints
from graph import travel_graph


def extract_interrupt_payload(result: dict[str, Any]) -> dict[str, Any] | None:
    """Extracts the interrupt payload dictionary if an interrupt was triggered."""
    interrupts = result.get("__interrupt__", [])
    if not interrupts:
        return None
    
    first_interrupt = interrupts[0]
    payload = getattr(first_interrupt, "value", first_interrupt)
    return payload if isinstance(payload, dict) else {"value": payload}


def serialize_result(result: dict[str, Any], thread_id: str) -> dict[str, Any]:
    """Serializes the graph execution output into a clean dictionary response."""
    messages = result.get("messages", [])
    last_message = messages[-1].content if messages else ""
    answer = result.get("final_response") or last_message
    interrupt_payload = extract_interrupt_payload(result)
    
    if interrupt_payload: 
        answer = interrupt_payload.get("draft_itinerary") or result.get("itinerary", "")
    
    return {
        "thread_id": thread_id,
        "answer": answer,
        "requires_approval": interrupt_payload is not None,
        "approval_request": (interrupt_payload.get("approval_request", "") if interrupt_payload else result.get("approval_request", "")),
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "weather_result": result.get("weather_result", ""),
        "budget_analysis": result.get("budget_analysis", ""),
        "itinerary": (interrupt_payload.get("draft_itinerary", "") if interrupt_payload else result.get("itinerary", "")),
        "selected_agents": result.get("selected_agents", []),
        "trip_constraints": result.get("trip_constraints", {}),
        "supervisor_reasoning": result.get("supervisor_reasoning", ""),
        "guardrail_allowed": result.get("guardrail_allowed", True),
        "guardrail_reason": result.get("guardrail_reason", ""),
        "approved": result.get("approved", False),
        "human_feedback": result.get("human_feedback", ""),
        "llm_calls": result.get("llm_calls", 0)
    }


def run_travel_agent(user_input: str, thread_id: str | None = None) -> dict[str, Any]:
    """Primary synchronous entry point to start a new travel planning session."""
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"
    
    run_config = {"configurable": {"thread_id": thread_id}}
    
    result = travel_graph.invoke(
        {
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
        },
        config=run_config
    )
    return serialize_result(result, thread_id)


def resume_travel_agent(thread_id: str, approved: bool, feedback: str = "") -> dict[str, Any]:
    """Resumes graph execution after human approval or revision feedback."""
    if not thread_id:
        raise ValueError("Thread ID is required to resume travel agent")
    
    run_config = {"configurable": {"thread_id": thread_id}}
    
    result = travel_graph.invoke(
        Command(
            resume={
                "approved": approved,
                "feedback": feedback.strip(),
            }
        ),
        config=run_config,
    )
    return serialize_result(result, thread_id)


def stream_travel_agent(user_input: str, thread_id: str | None = None) -> Generator[str, None, None]:
    """Server-Sent Events (SSE) streaming generator for real-time multi-agent execution."""
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"
    
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
    
    # Emit initial start event
    start_payload = json.dumps({"thread_id": thread_id, "status": "started", "query": user_input})
    yield f"event: start\ndata: {start_payload}\n\n"
    
    for chunk in travel_graph.stream(initial_input, config=run_config, stream_mode="updates"):
        for node_name, node_update in chunk.items():
            if node_name == "__interrupt__":
                continue
            
            clean_update = {k: v for k, v in node_update.items() if k != "messages"}
            evt_payload = json.dumps({
                "node": node_name,
                "thread_id": thread_id,
                "update": clean_update
            })
            yield f"event: node_complete\ndata: {evt_payload}\n\n"
            
    snapshot = travel_graph.get_state(run_config)
    interrupts = [t.interrupts for t in snapshot.tasks if t.interrupts]
    
    if interrupts:
        first_interrupt = interrupts[0][0]
        payload = getattr(first_interrupt, "value", first_interrupt)
        interrupt_data = {
            "thread_id": thread_id,
            "requires_approval": True,
            "approval_request": payload.get("approval_request", "") if isinstance(payload, dict) else "",
            "draft_itinerary": payload.get("draft_itinerary", "") if isinstance(payload, dict) else "",
            "itinerary": payload.get("draft_itinerary", "") if isinstance(payload, dict) else "",
            "selected_agents": payload.get("selected_agents", []) if isinstance(payload, dict) else [],
            "trip_constraints": snapshot.values.get("trip_constraints", {}),
            "supervisor_reasoning": snapshot.values.get("supervisor_reasoning", ""),
            "flight_results": snapshot.values.get("flight_results", ""),
            "hotel_results": snapshot.values.get("hotel_results", ""),
            "weather_result": snapshot.values.get("weather_result", ""),
            "budget_analysis": snapshot.values.get("budget_analysis", ""),
            "guardrail_allowed": snapshot.values.get("guardrail_allowed", True),
            "guardrail_reason": snapshot.values.get("guardrail_reason", ""),
            "llm_calls": snapshot.values.get("llm_calls", 0),
            "answer": payload.get("draft_itinerary", "") if isinstance(payload, dict) else ""
        }
        yield f"event: interrupt\ndata: {json.dumps(interrupt_data)}\n\n"
    else:
        final_data = serialize_result(snapshot.values, thread_id)
        yield f"event: complete\ndata: {json.dumps(final_data)}\n\n"


def stream_resume_travel_agent(thread_id: str, approved: bool, feedback: str = "") -> Generator[str, None, None]:
    """Server-Sent Events (SSE) streaming generator for resuming graph after human approval."""
    if not thread_id:
        raise ValueError("Thread ID is required to resume travel agent")
    
    run_config = {"configurable": {"thread_id": thread_id}}
    resume_cmd = Command(
        resume={
            "approved": approved,
            "feedback": feedback.strip(),
        }
    )
    
    start_payload = json.dumps({"thread_id": thread_id, "status": "resumed", "approved": approved})
    yield f"event: start\ndata: {start_payload}\n\n"
    
    for chunk in travel_graph.stream(resume_cmd, config=run_config, stream_mode="updates"):
        for node_name, node_update in chunk.items():
            if node_name == "__interrupt__":
                continue
            clean_update = {k: v for k, v in node_update.items() if k != "messages"}
            evt_payload = json.dumps({
                "node": node_name,
                "thread_id": thread_id,
                "update": clean_update
            })
            yield f"event: node_complete\ndata: {evt_payload}\n\n"
            
    snapshot = travel_graph.get_state(run_config)
    final_data = serialize_result(snapshot.values, thread_id)
    yield f"event: complete\ndata: {json.dumps(final_data)}\n\n"


__all__ = [
    "run_travel_agent",
    "resume_travel_agent",
    "stream_travel_agent",
    "stream_resume_travel_agent",
    "travel_graph",
    "TravelState",
    "empty_constraints"
]
