from __future__ import annotations

import json
from typing import Any

CHAT_HISTORY_PRIORITY = float("-inf")


def _content_to_blocks(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in content:
        if item.get("type") == "image":
            out.append({"type": "image", "image": item.get("image")})
        else:
            out.append({"type": "text", "text": item.get("text") or ""})
    return out


def _build_history_item_message(item: dict[str, Any], priority: float) -> dict[str, Any] | None:
    t = item.get("type")
    if t == "prompt":
        content: list[dict[str, Any]] = []
        msg = (item.get("agentFacingMessage") or "").strip()
        if msg:
            content.append({"type": "text", "text": item.get("agentFacingMessage")})
        for context_item in item.get("contextItems") or []:
            ct = context_item.get("type")
            if ct == "shape":
                content.append(
                    {
                        "type": "text",
                        "text": f"[CONTEXT]: {json.dumps(context_item.get('shape'))}",
                    }
                )
            elif ct == "shapes":
                content.append(
                    {
                        "type": "text",
                        "text": f"[CONTEXT]: {json.dumps(context_item.get('shapes'))}",
                    }
                )
            else:
                content.append(
                    {"type": "text", "text": f"[CONTEXT]: {json.dumps(context_item)}"}
                )
        if not content:
            return None
        src = item.get("promptSource")
        role = "user" if src in ("user", "other-agent") else "assistant"
        return {"role": role, "content": content, "priority": priority}

    if t == "continuation":
        data = item.get("data") or []
        if len(data) == 0:
            return None
        text = f"[DATA RETRIEVED]: {json.dumps(data)}"
        return {
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
            "priority": priority,
        }

    if t == "action":
        action = item.get("action") or {}
        at = action.get("_type")
        if at == "message":
            text = action.get("text") or "<message data lost>"
        elif at == "think":
            text = "[THOUGHT]: " + (action.get("text") or "<thought data lost>")
        else:
            raw = {k: v for k, v in action.items() if k not in ("complete", "time")}
            text = "[ACTION]: " + json.dumps(raw)
        return {
            "role": "assistant",
            "content": [{"type": "text", "text": text}],
            "priority": priority,
        }

    return None


def _messages_from_chat_history(part: dict[str, Any]) -> list[dict[str, Any]]:
    history = part.get("history") or []
    if len(history) == 0:
        return []
    last_index = len(history) - 1
    end = len(history)
    if end > 0 and history[last_index].get("type") == "prompt":
        end = last_index
    messages: list[dict[str, Any]] = []
    for i in range(end):
        m = _build_history_item_message(history[i], CHAT_HISTORY_PRIORITY)
        if m:
            messages.append(m)
    return messages


def _default_build_from_part(part: dict[str, Any], priority: float) -> list[dict[str, Any]]:
    ptype = part.get("type")
    handlers = {
        "blurryShapes": _part_blurry_shapes,
        "canvasLints": _part_canvas_lints,
        "contextItems": _part_context_items,
        "data": _part_data,
        "messages": _part_messages,
        "peripheralShapes": _part_peripheral_shapes,
        "screenshot": _part_screenshot,
        "selectedShapes": _part_selected_shapes,
        "time": _part_time,
        "todoList": _part_todo_list,
        "userActionHistory": _part_user_action_history,
        "userViewportBounds": _part_user_viewport_bounds,
        "agentViewportBounds": _part_agent_viewport_bounds,
    }
    fn = handlers.get(ptype)
    if not fn:
        return []
    strings = fn(part)
    if not strings:
        return []
    message_content: list[dict[str, Any]] = []
    for item in strings:
        if isinstance(item, str) and item.startswith("data:image/"):
            message_content.append({"type": "image", "image": item})
        else:
            message_content.append({"type": "text", "text": str(item)})
    return [{"role": "user", "content": message_content, "priority": priority}]


def _part_blurry_shapes(part: dict[str, Any]) -> list[str]:
    shapes = part.get("shapes") or []
    if len(shapes) == 0:
        return ["There are no shapes in your view at the moment."]
    return ["These are the shapes you can currently see:", json.dumps(shapes)]


def _part_canvas_lints(part: dict[str, Any]) -> list[str]:
    lints = part.get("lints") or []
    if not lints:
        return []
    messages: list[str] = [
        "[LINTER]: The following potential visual problems have been detected in the canvas. You should decide if you want to address them. Defer to your view of the canvas to decide if you need to make changes; it's very possible that you don't need to make any changes."
    ]
    grow_y = [l for l in lints if l.get("type") == "growY-on-shape"]
    overlap = [l for l in lints if l.get("type") == "overlapping-text"]
    friendless = [l for l in lints if l.get("type") == "friendless-arrow"]
    if grow_y:
        shape_ids = [sid for l in grow_y for sid in (l.get("shapeIds") or [])]
        messages.append(
            "Text overflow: These shapes have text that caused their containers to grow past the size that they were intended to be, potentially breaking out of their container. If you decide to fix: you need to set the height back to what you originally intended after increasing the width.\n"
            + "\n".join(f"  - {sid}" for sid in shape_ids)
        )
    if overlap:
        lines = [
            "Overlapping text: The shapes in each group have text and overlap each other, which may make text hard to read. If you decide to fix this, you may need to increase the size of any shapes containing the text.",
        ]
        for lint in overlap:
            lines.append("  - " + ", ".join(lint.get("shapeIds") or []))
        messages.append("\n".join(lines))
    if friendless:
        shape_ids = [sid for l in friendless for sid in (l.get("shapeIds") or [])]
        messages.append(
            "Unconnected arrows: These arrows aren't fully connected to other shapes.\n"
            + "\n".join(f"  - {sid}" for sid in shape_ids)
        )
    return messages


def _part_context_items(part: dict[str, Any]) -> list[str]:
    items = part.get("items") or []
    request_source = part.get("requestSource")
    messages: list[str] = []
    shape_items = [i for i in items if i.get("type") == "shape"]
    shapes_items = [i for i in items if i.get("type") == "shapes"]
    area_items = [i for i in items if i.get("type") == "area"]
    point_items = [i for i in items if i.get("type") == "point"]
    if area_items:
        is_self = request_source == "self"
        areas = [i.get("bounds") for i in area_items]
        messages.append(
            "You have decided to focus your view on the following area. Make sure to focus your task here."
            if is_self
            else "The user has specifically brought your attention to the following areas in this request. The user might refer to them as the \"area(s)\" or perhaps \"here\" or \"there\", but either way, it's implied that you should focus on these areas in both your reasoning and actions. Make sure to focus your task on these areas:"
        )
        for area in areas:
            messages.append(json.dumps(area))
    if point_items:
        points = [i.get("point") for i in point_items]
        messages.append(
            "The user has specifically brought your attention to the following points in this request. The user might refer to them as the \"point(s)\" or perhaps \"here\" or \"there\", but either way, it's implied that you should focus on these points in both your reasoning and actions. Make sure to focus your task on these points:"
        )
        for p in points:
            messages.append(json.dumps(p))
    if shape_items:
        shapes = [i.get("shape") for i in shape_items]
        messages.append(
            f"The user has specifically brought your attention to these {len(shapes)} shapes individually in this request. Make sure to focus your task on these shapes where applicable:"
        )
        for sh in shapes:
            messages.append(json.dumps(sh))
    for context_item in shapes_items:
        shapes = context_item.get("shapes") or []
        if len(shapes) > 0:
            messages.append(
                f"The user has specifically brought your attention to the following group of {len(shapes)} shapes in this request. Make sure to focus your task on these shapes where applicable:"
            )
            messages.append("\n".join(json.dumps(shape) for shape in shapes))
    return messages


def _part_data(part: dict[str, Any]) -> list[str]:
    data = part.get("data") or []
    if len(data) == 0:
        return []
    return ["Here's the data you requested:", *[json.dumps(item) for item in data]]


def _part_messages(part: dict[str, Any]) -> list[str]:
    src = part.get("requestSource")
    if src in ("user", "self", "other-agent"):
        return list(part.get("agentMessages") or [])
    return []


def _part_peripheral_shapes(part: dict[str, Any]) -> list[str]:
    clusters = part.get("clusters") or []
    if len(clusters) == 0:
        return []
    return [
        "There are some groups of shapes in your peripheral vision, outside the your main view. You can't make out their details or content. If you want to see their content, you need to get closer. The groups are as follows",
        json.dumps(clusters),
    ]


def _part_screenshot(part: dict[str, Any]) -> list[str]:
    screenshot = part.get("screenshot") or ""
    if screenshot == "":
        return []
    return [
        "Here is the part of the canvas that you can currently see at this moment. It is not a reference image.",
        screenshot,
    ]


def _part_selected_shapes(part: dict[str, Any]) -> list[str]:
    shape_ids = part.get("shapeIds") or []
    if not shape_ids:
        return []
    if len(shape_ids) == 1:
        return [f"The user has this shape selected: {shape_ids[0]}"]
    return [f"The user has these shapes selected: {', '.join(shape_ids)}"]


def _part_time(part: dict[str, Any]) -> list[str]:
    return [f"The user's current time is: {part.get('time')!s}"]


def _part_todo_list(part: dict[str, Any]) -> list[str]:
    items = part.get("items") or []
    if len(items) == 0:
        return ["You have no todos yet."]
    return ["Here is your current todo list:", json.dumps(items)]


def _part_user_action_history(part: dict[str, Any]) -> list[str]:
    updated = part.get("updated") or []
    removed = part.get("removed") or []
    added = part.get("added") or []
    if len(updated) == 0 and len(removed) == 0 and len(added) == 0:
        return []
    return [
        "Since the previous request, the user has made the following changes to the canvas:",
        json.dumps(part),
    ]


def _part_user_viewport_bounds(part: dict[str, Any]) -> list[str]:
    user_bounds = part.get("userBounds")
    if not user_bounds:
        return []
    b = user_bounds
    if isinstance(b, dict) and "x" in b:
        cx = (b.get("x", 0) + b.get("w", 0) / 2)
        cy = (b.get("y", 0) + b.get("h", 0) / 2)
    else:
        cx, cy = 0, 0
    return [f"The user's view is centered at ({cx}, {cy})."]


def _part_agent_viewport_bounds(part: dict[str, Any]) -> list[str]:
    agent_bounds = part.get("agentBounds")
    if not agent_bounds:
        return []
    return [
        f"The bounds of the part of the canvas that you can currently see are: {json.dumps(agent_bounds)}",
    ]


PRIORITIES: dict[str, float] = {
    "blurryShapes": -70,
    "canvasLints": -50,
    "contextItems": -55,
    "data": 200,
    "messages": float("inf"),
    "peripheralShapes": -65,
    "screenshot": -40,
    "selectedShapes": -55,
    "time": -100,
    "todoList": 10,
    "userActionHistory": -40,
    "userViewportBounds": -80,
    "agentViewportBounds": -80,
}


def build_messages(prompt: dict) -> list[dict[str, Any]]:
    all_messages: list[dict[str, Any]] = []

    for part in prompt.values():
        if not isinstance(part, dict):
            continue
        ptype = part.get("type")
        if ptype in ("mode", "debug", "modelName"):
            continue
        if ptype == "chatHistory":
            all_messages.extend(_messages_from_chat_history(part))
            continue
        priority = PRIORITIES.get(ptype, 0)
        all_messages.extend(_default_build_from_part(part, priority))

    all_messages.sort(key=lambda m: m.get("priority", 0))

    result: list[dict[str, Any]] = []
    for tl in all_messages:
        result.append(
            {
                "role": tl["role"],
                "content": _content_to_blocks(tl["content"]),
            }
        )
    return result
