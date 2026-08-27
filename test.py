import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from tools.tavily_tool import tavily_search
from tools.flight_tool import search_flights
from backend import run_travel_agent

res = run_travel_agent(user_input="Plan a 7 days trip to Japan from India")
print(res["answer"])


