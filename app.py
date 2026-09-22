import traceback
from pathlib import Path
from typing import Optional, Any
import uvicorn
import nest_asyncio
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from backend import run_travel_agent, resume_travel_agent, stream_travel_agent, stream_resume_travel_agent
from cache import check_rate_limit

nest_asyncio.apply()

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="TripMint - AI Travel Planning System",
    description="Multi-agent AI travel agent with guardrails, supervisor routing, live flight status, hotel search, weather forecasts, budget analysis, and human-in-the-loop approvals."
)

MAX_BODY_BYTES = 50 * 1024  # 50 KB max input size


@app.middleware("http")
async def security_and_rate_limit_middleware(request: Request, call_next):
    """Middleware enforcing input size limits (50 KB) and Redis client rate limits (10 req/min)."""
    # 1. Input Size Validation
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Payload Too Large: Request body exceeds the maximum permitted limit of 50 KB."}
                )
        except (ValueError, TypeError):
            pass

    # 2. Rate Limiting for API routes
    if request.url.path.startswith("/api/"):
        client_ip = request.client.host if request.client else "127.0.0.1"
        allowed, _ = check_rate_limit(client_ip, max_requests=10, window_seconds=60)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Too Many Requests: Rate limit exceeded (maximum 10 requests per minute). Please try again shortly."}
            )

    response = await call_next(request)
    return response


app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)

app.mount(
    "/images",
    StaticFiles(directory=str(BASE_DIR / "images")),
    name="images"
)

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)


class TravelRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None


class ApprovalResumeRequest(BaseModel):
    thread_id: str
    approved: bool
    feedback: Optional[str] = ""


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"name": "TripMint"}
    )


@app.get("/home", response_class=HTMLResponse)
async def home_scroll(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={}
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
                "answer": result.get("answer", "No answer generated."),
                "thread_id": result.get("thread_id", ""),
                "requires_approval": result.get("requires_approval", False),
                "approval_request": result.get("approval_request", ""),
                "guardrail_allowed": result.get("guardrail_allowed", True),
                "guardrail_reason": result.get("guardrail_reason", ""),
                "selected_agents": result.get("selected_agents", []),
                "trip_constraints": result.get("trip_constraints", {}),
                "supervisor_reasoning": result.get("supervisor_reasoning", ""),
                "flight_results": result.get("flight_results", ""),
                "hotel_results": result.get("hotel_results", ""),
                "weather_result": result.get("weather_result", ""),
                "budget_analysis": result.get("budget_analysis", ""),
                "itinerary": result.get("itinerary", ""),
                "approved": result.get("approved", False),
                "human_feedback": result.get("human_feedback", ""),
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


@app.post("/api/resume_planner")
async def resume_planner(request_data: ApprovalResumeRequest):
    try:
        thread_id = request_data.thread_id.strip()
        if not thread_id:
            return JSONResponse(
                status_code=400,
                content={"error": "Thread ID is required to resume the travel plan."}
            )

        result = resume_travel_agent(
            thread_id=thread_id,
            approved=request_data.approved,
            feedback=request_data.feedback or ""
        )

        return JSONResponse(
            status_code=200,
            content={
                "answer": result.get("answer", "No answer generated."),
                "thread_id": result.get("thread_id", thread_id),
                "requires_approval": result.get("requires_approval", False),
                "approval_request": result.get("approval_request", ""),
                "guardrail_allowed": result.get("guardrail_allowed", True),
                "guardrail_reason": result.get("guardrail_reason", ""),
                "selected_agents": result.get("selected_agents", []),
                "trip_constraints": result.get("trip_constraints", {}),
                "supervisor_reasoning": result.get("supervisor_reasoning", ""),
                "flight_results": result.get("flight_results", ""),
                "hotel_results": result.get("hotel_results", ""),
                "weather_result": result.get("weather_result", ""),
                "budget_analysis": result.get("budget_analysis", ""),
                "itinerary": result.get("itinerary", ""),
                "approved": result.get("approved", False),
                "human_feedback": result.get("human_feedback", ""),
                "llm_calls": result.get("llm_calls", 0),
            }
        )

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"Error in /api/resume_planner: {error_details}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Error resuming travel plan: {str(e)}"}
        )


@app.post("/api/travel_planner/stream")
async def travel_planner_stream(request_data: TravelRequest):
    """Server-Sent Events (SSE) streaming endpoint for live agent execution updates."""
    user_message = request_data.message.strip()
    if not user_message:
        return JSONResponse(
            status_code=400,
            content={"error": "User message cannot be empty."}
        )

    return StreamingResponse(
        stream_travel_agent(
            user_input=user_message,
            thread_id=request_data.thread_id
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/resume_planner/stream")
async def resume_planner_stream(request_data: ApprovalResumeRequest):
    """Server-Sent Events (SSE) streaming endpoint for resuming approval card."""
    thread_id = request_data.thread_id.strip()
    if not thread_id:
        return JSONResponse(
            status_code=400,
            content={"error": "Thread ID is required to resume the travel plan."}
        )

    return StreamingResponse(
        stream_resume_travel_agent(
            thread_id=thread_id,
            approved=request_data.approved,
            feedback=request_data.feedback or ""
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(content={})


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)