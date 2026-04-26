"""
FastAPI chat server for the Architecture Q&A agent.

Endpoints:
  GET  /          → serves the chat UI
  POST /chat      → {"question": "..."} → SSE stream of tokens + final answer
  GET  /examples  → returns the list of example questions
  GET  /health    → {"status": "ok"}

Run:
    source .venv/bin/activate
    python interaction/server.py
    # or via uvicorn directly:
    uvicorn interaction.server:app --reload --port 8000
"""

import os
import json
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ── Import the agent (reuse existing logic) ───────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from interaction.qa_agent import ArchitectureQAAgent, EXAMPLE_QUESTIONS

# ── App setup ─────────────────────────────────────────────────────────────────
agent: ArchitectureQAAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    loop = asyncio.get_event_loop()
    agent = await loop.run_in_executor(None, ArchitectureQAAgent)
    yield
    if agent:
        agent.close()


app = FastAPI(title="Architecture Q&A", lifespan=lifespan)


# ── Models ────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str


# ── SSE streaming helper ──────────────────────────────────────────────────────
def sse(event: str, data: str) -> str:
    """Format a single SSE message."""
    payload = json.dumps({"event": event, "data": data})
    return f"data: {payload}\n\n"


async def stream_answer(question: str) -> AsyncGenerator[str, None]:
    """Run the agent in a thread and stream structured SSE events."""
    loop = asyncio.get_event_loop()

    # Collect intermediate steps via a simple callback-friendly wrapper
    steps: dict = {}

    def run_agent():
        # Temporarily capture verbose output into steps dict
        cypher_generated = []
        cypher_corrected = []
        results_list = []

        # Monkey-patch ask() to capture internals without changing qa_agent.py
        original_ask = agent._run_cypher

        call_count = 0

        def patched_run_cypher(cypher):
            nonlocal call_count
            call_count += 1
            r = original_ask(cypher)
            if call_count == 1:
                cypher_generated.append(cypher)
                results_list.extend(r)
            else:
                cypher_corrected.append(cypher)
                results_list.clear()
                results_list.extend(r)
            return r

        agent._run_cypher = patched_run_cypher
        try:
            answer = agent.ask(question, verbose=False)
        finally:
            agent._run_cypher = original_ask

        steps["cypher"] = cypher_generated[0] if cypher_generated else ""
        steps["cypher_corrected"] = cypher_corrected[0] if cypher_corrected else ""
        steps["results"] = results_list
        steps["answer"] = answer

    # Run blocking agent call in a thread pool
    await loop.run_in_executor(None, run_agent)

    yield sse("cypher", steps.get("cypher", ""))

    if steps.get("cypher_corrected"):
        yield sse("retry", steps["cypher_corrected"])

    row_count = len(steps.get("results", []))
    yield sse("results_count", str(row_count))

    yield sse("answer", steps.get("answer", "No answer returned."))
    yield sse("done", "")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/examples")
async def examples():
    return {"examples": EXAMPLE_QUESTIONS}


@app.post("/chat")
async def chat(req: ChatRequest):
    if not req.question.strip():
        return JSONResponse({"error": "Question cannot be empty"}, status_code=400)
    return StreamingResponse(
        stream_answer(req.question.strip()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "chat.html"
    return HTMLResponse(html_path.read_text())


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("interaction.server:app", host="0.0.0.0", port=8000, reload=False)
