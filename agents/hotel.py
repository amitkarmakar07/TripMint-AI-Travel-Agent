import asyncio
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from state import TravelState
from llm import light_llm, parse_mcp_output
from mcp_clients import tavily_mcp_search


def hotel_agent(state: TravelState):
    query = state.get("user_query", "")
    destination = state.get("trip_constraints", {}).get("destination", "")
    search_term = destination if destination else query

    try:
        raw_results = asyncio.run(tavily_mcp_search(f"Best hotels and places to stay in {search_term}"))
        parsed = parse_mcp_output(raw_results)

        extracted_content = ""
        if isinstance(parsed, dict) and "results" in parsed:
            for item in parsed.get("results", [])[:6]:
                title = item.get("title", "")
                content = item.get("content", "")
                url = item.get("url", "")
                extracted_content += f"Hotel: {title}\nDetails: {content}\nLink: {url}\n\n"
        elif isinstance(parsed, str):
            extracted_content = parsed
        else:
            extracted_content = str(raw_results)

        hotel_prompt = f"""You are a professional hotel and accommodation specialist. Based on the following search results, curate 3-5 top hotel recommendations for this trip.

Destination: {search_term}
User Query: {query}

Search Information:
{extracted_content[:3500]}

Provide a clean, beautifully formatted Markdown response with:
1. Recommended Hotels grouped by category (e.g., Luxury, Mid-Range, Boutique/Budget).
2. For each hotel include:
   - **Name**
   - **Location / Neighborhood**
   - **Key Highlights & Amenities**
   - **Why it's recommended**
3. Quick Booking & Accommodation Advice for this destination.
"""
        hotel_response = light_llm.invoke([
            SystemMessage(content="You are a professional hotel and accommodation specialist."),
            HumanMessage(content=hotel_prompt)
        ])
        hotel_data = str(hotel_response.content)

    except Exception as e:
        hotel_data = f"Unable to fetch hotel recommendations: {str(e)}"

    return {
        "hotel_results": hotel_data,
        "messages": [
            AIMessage(content="Hotel recommendations generated successfully.")
        ],
        "llm_calls": 1
    }
