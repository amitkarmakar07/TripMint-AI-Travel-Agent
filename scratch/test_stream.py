from langchain_core.messages import HumanMessage
from state import empty_constraints
from graph import travel_graph

def main():
    thread_id = "test_stream_sync_1"
    run_config = {"configurable": {"thread_id": thread_id}}
    initial_input = {
        "messages": [HumanMessage(content="What is the weather in London?")],
        "user_query": "What is the weather in London?",
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
    print("Starting sync stream...")
    for chunk in travel_graph.stream(initial_input, config=run_config, stream_mode="updates"):
        for node, update in chunk.items():
            print(f"Node completed: {node}")

    snapshot = travel_graph.get_state(run_config)
    print("Snapshot next:", snapshot.next)
    print("Snapshot tasks with interrupts:", [t.interrupts for t in snapshot.tasks if t.interrupts])

if __name__ == "__main__":
    main()
