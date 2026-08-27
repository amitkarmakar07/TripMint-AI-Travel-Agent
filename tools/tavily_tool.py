from tavily import TavilyClient
import os
from config import config

tavily = TavilyClient(api_key=config.TRAVILY_API_KEY)

def tavily_search(query) :
    response = tavily.search(
        query = query,
        max_results= 5
    )
    results = []
    
    for i , r in enumerate(response["results"],1) :
        title = r.get("title","Unknown")
        url = r.get("url","")
        content = r.get("content","").strip()
        
        if(len(content) > 500) :
            content = content[:500].rsplit(" ",1)[0]+ "..."
        
        results.append(f"{i}. {title}\n{url}\n{content}\n")
        
    return "\n\n".join(results)  
        
    