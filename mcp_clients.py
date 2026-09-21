import os
import asyncio
import certifi
from langchain_mcp_adapters.client import MultiServerMCPClient
from config import config
from cache import get_cached, set_cached
import sys

os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()


TAVILY_API_KEY = config.TRAVILY_API_KEY
AVIATIONSTACK_API_KEY = config.AVIATIONSTACK_API_KEY
OPENWEATHER_API_KEY = config.OPENWEATHER_API_KEY


client = MultiServerMCPClient({
    "tavily" : {
        "transport" : "streamable_http",
        "url" : f"https://mcp.tavily.com/mcp/?tavilyApiKey={TAVILY_API_KEY}"
    },

    "aviationstack": {
      "transport": "stdio",
      "command": "uvx",
      "args": [
        "--with",
        "mcp<2",
        "aviationstack-mcp"
      ],
      "env": {
        "AVIATION_STACK_API_KEY": AVIATIONSTACK_API_KEY
      }
    },

    "weather": {
        "transport": "stdio",
        "command": sys.executable,  # will find where the python env is running
        "args": ["custom_weather_mcp.py"]  # custom mcp code
    }
})



search_tool = None
aviation_tools = {}
weather_tool = None
forecast_tool = None


async def initialize_tavily_mcp():

    global search_tool 

    if search_tool is not None :
        return

    tools = await client.get_tools()

    search_tool = next(
        tool for tool in tools if tool.name == "tavily_search"
    )


async def initialize_aviation_mcp():
    global aviation_tools 
    if aviation_tools:
        return
    
    tools = await client.get_tools()
    aviation_tools = {
        tool.name: tool for tool in tools
    }


async def initialize_weather_mcp():
    
    global weather_tool , forecast_tool
    
    if weather_tool and forecast_tool :
        return
    
    tools = await client.get_tools()
    
    weather_tool = next(
        tool for tool in tools if tool.name == "get_current_weather"
    )
    
    forecast_tool = next(
        tool for tool in tools if tool.name == "get_forecast"
    )


import json

# functions with Cloud Redis / in-memory fallback caching
async def tavily_mcp_search(query: str):
    cache_key = f"tavily:{query.lower().strip()}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    if search_tool is None:
        await initialize_tavily_mcp()
    
    result = await search_tool.ainvoke(
        {"query": query}
    )
    set_cached(cache_key, result, ttl_seconds=43200) # 12 hours
    return result


async def aviation_mcp_search(tool_name: str, tool_args: dict = None):
    args = tool_args or {}
    args_str = json.dumps(args, sort_keys=True)
    cache_key = f"aviation:{tool_name}:{args_str}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    if not aviation_tools:
        await initialize_aviation_mcp()

    if tool_name not in aviation_tools:
        raise ValueError(f"Tool {tool_name} not found")

    tool_to_call = aviation_tools[tool_name]
    result = await tool_to_call.ainvoke(args)
    set_cached(cache_key, result, ttl_seconds=14400) # 4 hours
    return result


async def weather_mcp_search(city: str):
    cache_key = f"weather:{city.lower().strip()}"
    cached = get_cached(cache_key)
    if cached is not None:
        return cached

    if weather_tool is None or forecast_tool is None:
        await initialize_weather_mcp()
    
    current_weather = await weather_tool.ainvoke({"city": city})
    forecast = await forecast_tool.ainvoke({"city": city})
    
    res = {"current_weather": current_weather, "forecast": forecast}
    set_cached(cache_key, res, ttl_seconds=21600) # 6 hours
    return res 