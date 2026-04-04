import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "http://localhost:8000"


def main() -> None:
    base = os.environ.get("AGENT_BASE_URL", DEFAULT_BASE).rstrip("/")
    url = f"{base}/invocations"
    # Minimal payload (backward compatible):
    payload = {
        "conversation_history": "",
        "user_query": "Накидай идею с бизнесом про машины",
    }
    # Optional extensions (see app/main.py invoke):
    # "canvas_context": ""  # or a text/JSON snapshot from the client; empty uses server-side placeholder
    # "bedrock_model_id": "eu.anthropic.claude-sonnet-4-6"  # must be listed in ALLOWED_BEDROCK_MODEL_IDS (defaults to BEDROCK_MODEL_ID only)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(e, file=sys.stderr)
        print(e.read().decode("utf-8", errors="replace"), file=sys.stderr)
        raise SystemExit(1) from e
    print(raw)
    data = json.loads(raw)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
