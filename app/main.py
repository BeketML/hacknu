from bedrock_agentcore.runtime import BedrockAgentCoreApp
from mcp import stdio_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

from agent_service.config import resolve_bedrock_model_id, settings
from agent_service.prompts import build_user_prompt
from agent_service.tldraw_mcp import (
    system_prompt_with_endpoints,
    tldraw_stdio_params,
    validate_tldraw_mcp_dist,
)

validate_tldraw_mcp_dist(settings)

mcp_client = MCPClient(lambda: stdio_client(tldraw_stdio_params()))

app = BedrockAgentCoreApp()

@app.entrypoint
async def invoke(payload):
    # Optional: canvas_context (str), bedrock_model_id (str, must be in ALLOWED_BEDROCK_MODEL_IDS).
    conversation_history = payload.get("conversation_history", "")
    user_query = payload.get("user_query", "")
    raw_canvas = payload.get("canvas_context")
    canvas_context = raw_canvas if isinstance(raw_canvas, str) else None

    model_id = resolve_bedrock_model_id(payload.get("bedrock_model_id"), settings)
    bedrock_model = BedrockModel(
        model_id=model_id,
        region_name=settings.aws_region,
        temperature=settings.bedrock_temperature,
    )

    prompt = build_user_prompt(
        conversation_history=conversation_history,
        user_query=user_query,
        canvas_context=canvas_context,
    )
    agent = Agent(
        model=bedrock_model,
        system_prompt=system_prompt_with_endpoints(),
        tools=[mcp_client],
    )

    result = agent(prompt)

    return {
        "result": result.message
    }


if __name__ == "__main__":
    app.run(8000)
