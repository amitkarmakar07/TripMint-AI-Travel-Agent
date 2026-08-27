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


class TripRequest(BaseModel):
    query: str
    thread_id: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/plan")
async def plan_trip(trip_req: TripRequest):
    try:
        if not trip_req.query or not trip_req.query.strip():
            return JSONResponse(
                status_code=400,
                content={"error": "Travel request cannot be empty."}
            )

        result = run_travel_agent(
            user_input=trip_req.query.strip(),
            thread_id=trip_req.thread_id
        )

        return JSONResponse(status_code=200, content=result)

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Error in /api/plan: {error_details}")
        return JSONResponse(
            status_code=500,
            content={"error": f"An error occurred while generating your trip plan: {str(e)}"}
        )


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
