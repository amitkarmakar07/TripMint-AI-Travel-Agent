import traceback
from pathlib import Path
from typing import Optional
import uvicorn

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from backend import run_travel_agent

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="TripMint - AI Travel Planning System",
    description="Multi-agent AI travel agent with live flight status, hotel search, and custom itineraries."
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)


class TravelRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "name": "TripMint"}
    )


@app.post("/api/travel_planner")
async def travel_planner(request_data: TravelRequest):
    try:
        user_message = request_data.message.strip()

        if not user_message:
            return JSONResponse(
                status_code=400,
                content={"error": "User message cannot be empty."}
            )

        result = run_travel_agent(
            user_input=user_message,
            thread_id=request_data.thread_id
        )

        return JSONResponse(
            status_code=200,
            content={
                "answer": result.get("answer", "No answer found"),
                "flight_results": result.get("flight_results", "no flight results found"),
                "hotel_results": result.get("hotel_results", "no hotel results found"),
                "itinerary": result.get("itinerary", "no itinerary found"),
                "thread_id": result.get("thread_id", "no thread id found"),
                "llm_calls": result.get("llm_calls", 0),
            }
        )

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Error in /api/travel_planner: {error_details}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error generating travel plan: {str(e)}"}
        )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(content={})


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)