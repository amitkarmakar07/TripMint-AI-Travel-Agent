from langgraph.types import interrupt
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from state import TravelState
from llm import llm


def itinerary_agent(state: TravelState):
    prompt = f"""You are a world class AI travel planning agent. Create a complete,
    structured day-by-day travel itinerary for the following user request.

    User Request:
    {state.get('user_query', '')}

    Flight Results:
    {state.get('flight_results', '')}

    Hotel Results:
    {state.get('hotel_results', '')}

    Weather Results:
    {state.get('weather_result', '')}

    Budget Analysis:
    {state.get('budget_analysis', '')}

    Format Requirements:
    - Provide an engaging Trip Overview at the top.
    - Structure each day strictly using:
      ### Day X: [Catchy Day Title]
      - **Morning:** [Activities & Sightseeing]
      - **Afternoon:** [Lunch & Highlights]
      - **Evening:** [Dinner & Nightlife / Relaxation]
      - **Highlights:** [Essential tips, travel advice, or local etiquette]
    - Keep each day concise, practical, and highly engaging.
    """

    response = llm.invoke([
        SystemMessage(content="You are a world class travel planning agent."),
        HumanMessage(content=prompt)
    ])

    approval_request = (
        "Please review the generated draft itinerary. Is it good? Provide specific feedback or suggest improvements if needed."
    )

    return {
        "itinerary": str(response.content),
        "approval_request": approval_request,
        "messages": [AIMessage(content="Draft itinerary generated successfully.")],
        "llm_calls": 1
    }


def human_approval_agent(state: TravelState):
    review = interrupt(
        {
            "question": "Do you approve this itinerary?",
            "draft_itinerary": state.get("itinerary", ""),
            "approval_request": state.get("approval_request", ""),
            "selected_agents": state.get("selected_agents", []),
            "supervisor_reasoning": state.get("supervisor_reasoning", ""),
            "expected_response": {
                "approved": True,
                "feedback": "Optional revision feedback"
            }
        }
    )

    approved = bool(review.get("approved", False)) if isinstance(review, dict) else bool(review)
    human_feedback = str(review.get("feedback", "")).strip() if isinstance(review, dict) else ""

    return {
        "approved": approved,
        "human_feedback": human_feedback,
        "messages": [
            AIMessage(content=f"Human feedback recorded. Approved: {approved}")
        ]
    }


def master_agent(state: TravelState):
    if state.get("approved", False):
        review_instruction = "The user approved the draft itinerary. Preserve its recommendations while formatting and polishing."
    else:
        feedback = state.get("human_feedback", "")
        review_instruction = f"""The user requested adjustments. Apply this feedback carefully:
        {feedback if feedback else "Refine and improve the draft before finalizing."}
        """

    final_prompt = f"""Generate the final comprehensive travel response for the user.

    User Request: 
    {state.get('user_query', '')}
    
    Review Instructions:
    {review_instruction}

    Supervisor Constraints:
    {state.get('trip_constraints', {})}
    
    Flight Information:
    {state.get('flight_results', '')}
    
    Hotel Suggestions:
    {state.get('hotel_results', '')}
    
    Weather Results:
    {state.get('weather_result', '')}
    
    Budget Analysis:
    {state.get('budget_analysis', '')}
    
    Draft Itinerary:
    {state.get('itinerary', '')}


    Format the final answer beautifully and clearly using ONLY the sections relevant to what was gathered:
    1. Trip Summary
    2. Flight Information (Include only if flight data is available: Best Recommended Flight Options with Flight Names, Flight Numbers, Departure Times, Arrival Times, Total Duration & Layover, Departure Airport, Arrival Airport, Airlines, Airfare Range, Peak Season Warning, and Booking Advice)
    3. Hotel Suggestions (Include only if hotel recommendations are available)
    4. Weather Information (Include only if weather information was gathered)
    5. Day-to-Day Itinerary (Always include)
    6. Estimated Budget & Money-Saving Tips (Include only if budget analysis was performed)
    7. Final Recommendations

    Important:
    - Do NOT include empty or placeholder sections for categories that were not requested or gathered.
    - Be clear, practical, and well-structured with Markdown headings and bullet points.
    - Keep the response genuinely useful for real travel planning.
    """

    response = llm.invoke([
        SystemMessage(content="You are a professional AI travel planning assistant."),
        HumanMessage(content=final_prompt)
    ])

    final_text = str(response.content)

    return {
        "final_response": final_text,
        "messages": [AIMessage(content=final_text)],
        "llm_calls": 1
    }
