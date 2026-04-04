import json
import traceback
from collections.abc import Iterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .agent_service import stream_agent_actions
from .schemas.agent_prompt import AgentPromptModel, validated_prompt_to_dict

SSE_HEADERS = {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "Transfer-Encoding": "chunked",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}

app = FastAPI(title="agent-v2 backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


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
        err = {"error": str(e)}
        yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n".encode(enc)
        traceback.print_exc()


@app.post("/stream")
async def stream(request: Request):
    body = await request.json()
    try:
        model = AgentPromptModel.model_validate(body)
        prompt = validated_prompt_to_dict(model)
    except Exception as e:
        err = {"error": f"Invalid prompt: {e}"}

        def err_gen():
            yield f"data: {json.dumps(err, ensure_ascii=False)}\n\n".encode("utf-8")

        return StreamingResponse(err_gen(), headers=dict(SSE_HEADERS))

    return StreamingResponse(_sse_events(prompt), headers=dict(SSE_HEADERS))
