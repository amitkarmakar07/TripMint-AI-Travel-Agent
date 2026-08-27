import os
from dotenv import load_dotenv

load_dotenv()

class config:
    AVIATIONSTACK_API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
    DEFAULT_ORIGIN_IATA = os.getenv("DEFAULT_ORIGIN_IATA")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    TRAVILY_API_KEY = os.getenv("TRAVILY_API_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")
    LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING")
    LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT")
    LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY")
    LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT")


config = config()