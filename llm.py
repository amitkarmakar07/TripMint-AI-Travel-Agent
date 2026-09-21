import os
import json
import certifi
from typing import Any
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from config import config

# SSL Certificate Setup
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

# API Key Setup for LLM
llm_api_key = config.OPENAI_API_KEY
if not llm_api_key:
    raise ValueError("OPENAI_API_KEY not found in config")

# 1. Primary OpenAI Models
primary_llm = ChatOpenAI(
    model="gpt-4o",
    api_key=llm_api_key,
    temperature=0.7,
    max_retries=2
)

primary_light_llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=llm_api_key,
    temperature=0.0,
    max_retries=2
)

# 2. Cross-Provider Groq Fallbacks
groq_fallbacks = []
if getattr(config, "GROQ_API_KEY", None):
    try:
        from langchain_groq import ChatGroq
        groq_model = ChatGroq(
            model="openai/gpt-oss-120b",
            api_key=config.GROQ_API_KEY,
            temperature=0.7,
            max_retries=2
        )
        groq_fallbacks.append(groq_model)
    except Exception as err:
        print(f"[LLM Warning] Could not initialize Groq fallback: {err}")

# 3. Resilient Fallback Chains:
# Complex LLM: gpt-4o -> gpt-4o-mini -> Groq (openai/gpt-oss-120b)
llm = primary_llm.with_fallbacks([primary_light_llm] + groq_fallbacks)

# Lightweight LLM: gpt-4o-mini -> Groq (openai/gpt-oss-120b)
light_llm = primary_light_llm.with_fallbacks(groq_fallbacks) if groq_fallbacks else primary_light_llm


def llm_call(system_prompt: str, user_prompt: str) -> str:
    """Helper for simple System + User prompt LLM invocation."""
    response = llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
    )
    return str(response.content)


def json_from_llm(text: str) -> dict[str, Any]:
    """Safely parses JSON block from LLM markdown or plain response."""
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end < start:
        raise ValueError("The model did not return a valid JSON")
    
    return json.loads(text[start : end + 1])


def parse_mcp_output(raw_output: Any) -> Any:
    """Helper to extract clean data or JSON from MCP tool responses."""
    if isinstance(raw_output, list) and len(raw_output) > 0:
        first = raw_output[0]
        if isinstance(first, dict) and "text" in first:
            try:
                return json.loads(first["text"])
            except Exception:
                return first["text"]
    elif isinstance(raw_output, dict):
        return raw_output
    elif isinstance(raw_output, str):
        try:
            return json.loads(raw_output)
        except Exception:
            return raw_output
    return raw_output
