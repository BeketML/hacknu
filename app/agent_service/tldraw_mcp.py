import os

from mcp import StdioServerParameters

from .config import Settings, settings
from .prompt_sections import build_system_prompt_base


def validate_tldraw_mcp_dist(cfg: Settings) -> None:
    if not cfg.require_tldraw_dist:
        return
    dist_js = cfg.tldraw_mcp_root / "dist" / "index.js"
    if not dist_js.is_file():
        raise RuntimeError(
            f"TLDRAW MCP dist missing: {dist_js}. "
            f"Run npm run build in {cfg.tldraw_mcp_root}."
        )


def tldraw_mcp_env(cfg: Settings) -> dict[str, str]:
    env = os.environ.copy()
    env["TLDRAW_WS_URL"] = cfg.tldraw_ws_url
    return env


def tldraw_stdio_params(cfg: Settings | None = None) -> StdioServerParameters:
    cfg = cfg or settings
    root = cfg.tldraw_mcp_root
    dist_js = root / "dist" / "index.js"
    env = tldraw_mcp_env(cfg)
    if dist_js.is_file():
        return StdioServerParameters(
            command="node",
            args=[str(dist_js)],
            cwd=str(root),
            env=env,
        )
    return StdioServerParameters(
        command="npx",
        args=["--yes", "tsx", "src/index.ts"],
        cwd=str(root),
        env=env,
    )


def system_prompt_with_endpoints(cfg: Settings | None = None) -> str:
    cfg = cfg or settings
    return (
        build_system_prompt_base()
        + f"\n\nThe tldraw UI is served at {cfg.tldraw_ui_url}. "
        f"The MCP server talks to the widget WebSocket relay at {cfg.tldraw_ws_url}; "
        "keep that page open in the browser so canvas commands apply."
    )
