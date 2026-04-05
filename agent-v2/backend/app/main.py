import json
import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .agent_service import stream_agent_actions
from .imagegen.routes import router as imagegen_router
from .imagegen.context_routes import router as context_router
from .logging_config import configure_logging
from .request_logging_middleware import RequestLoggingMiddleware
from .schemas.agent_prompt import AgentPromptModel, validated_prompt_to_dict

logger = logging.getLogger(__name__)

SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "Transfer-Encoding": "chunked",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield
    for h in logging.getLogger().handlers:
        try:
            h.flush()
        except Exception:
            pass


app = FastAPI(title="agent-v2 backend", lifespan=lifespan)
app.include_router(imagegen_router)
app.include_router(context_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.add_middleware(RequestLoggingMiddleware)


@app.options("/stream")
def stream_options():
    return JSONResponse(content=None, headers=dict(SSE_HEADERS))


def _sse_events(prompt: dict) -> Iterator[bytes]:
    enc = "utf-8"
    try:
        for change in stream_agent_actions(prompt):
            line = f"data: {json.dumps(change, ensure_ascii=False)}\n\n"
            yield line.encode(enc)
    except Exception as e:
        logger.exception("SSE stream failed")
        err = {"error": str(e)}
        yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n".encode(enc)


@app.post("/stream")
async def stream(request: Request):
    body = await request.json()
    try:
        model = AgentPromptModel.model_validate(body)
        prompt = validated_prompt_to_dict(model)
    except Exception as e:
        logger.warning("Invalid prompt: %s", e)
        err = {"error": f"Invalid prompt: {e}"}

        def err_gen():
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n".encode("utf-8")

        return StreamingResponse(err_gen(), headers=dict(SSE_HEADERS))

    return StreamingResponse(_sse_events(prompt), headers=dict(SSE_HEADERS))
