from ..models_config import DEFAULT_MODEL_NAME


def get_model_name(prompt: dict) -> str:
    for part in prompt.values():
        if not isinstance(part, dict):
            continue
        if part.get("type") == "modelName":
            name = part.get("modelName")
            if name:
                return str(name)
    return DEFAULT_MODEL_NAME
