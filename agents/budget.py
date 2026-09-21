from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from state import TravelState
from llm import light_llm


def budget_agent(state: TravelState):
    prompt = f"""
    Analyze whether this trip is realistic for the user's budget.

    User Query: {state.get('user_query', '')}
    Trip Constraints: {state.get('trip_constraints', {})}
    Flight Results: {state.get('flight_results', '')}
    Hotel Results: {state.get('hotel_results', '')}
    Weather Results: {state.get('weather_result', '')}

    Return:
    1. Estimated cost categories (Flights, Stays, Activities, Food, Buffer)
    2. Budget risk areas
    3. Money-saving suggestions
    4. Overall Feasibility
    5. Final Budget Recommendation

    Provide a practical and clear cost assessment in INR.
    """

    response = light_llm.invoke([
        SystemMessage(content="You are a practical budget analysis assistant."),
        HumanMessage(content=prompt)
    ])

    return {
        "budget_analysis": str(response.content),
        "messages": [AIMessage(content="Budget assessment generated.")],
        "llm_calls": 1
    }
