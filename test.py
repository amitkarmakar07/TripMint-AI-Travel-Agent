import asyncio
# from mcp_client_test import get_all_tools
from mcp_clients import client

async def gettools() :
    tools = await client.get_tools()
    for tool in tools :
        print(tool.name)

if __name__ == "__main__" :
    asyncio.run(gettools())

