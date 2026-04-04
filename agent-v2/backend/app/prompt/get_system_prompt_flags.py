from typing import Any

_EDIT_ACTION_TYPES = frozenset(
    {
        "align",
        "bringToFront",
        "delete",
        "distribute",
        "label",
        "move",
        "place",
        "resize",
        "rotate",
        "sendToBack",
        "stack",
        "update",
    }
)


def _is_edit_action(action_type: str) -> bool:
    return action_type in _EDIT_ACTION_TYPES


def get_system_prompt_flags(
    actions: list[str],
    parts: list[str],
) -> dict[str, Any]:
    return {
        "hasMessage": "message" in actions,
        "hasThink": "think" in actions,
        "hasReview": "review" in actions,
        "hasSetMyView": "setMyView" in actions,
        "hasTodoList": "update-todo-list" in actions and "todoList" in parts,
        "hasAddDetail": "add-detail" in actions,
        "hasCreate": "create" in actions,
        "hasDelete": "delete" in actions,
        "hasUpdate": "update" in actions,
        "hasLabel": "label" in actions,
        "hasMove": "move" in actions,
        "hasPlace": "place" in actions,
        "hasBringToFront": "bringToFront" in actions,
        "hasSendToBack": "sendToBack" in actions,
        "hasRotate": "rotate" in actions,
        "hasResize": "resize" in actions,
        "hasAlign": "align" in actions,
        "hasDistribute": "distribute" in actions,
        "hasStack": "stack" in actions,
        "hasClear": "clear" in actions,
        "hasPen": "pen" in actions,
        "hasMessagesPart": "messages" in parts,
        "hasDataPart": "data" in parts,
        "hasContextItemsPart": "contextItems" in parts,
        "hasScreenshotPart": "screenshot" in parts,
        "hasUserViewportBoundsPart": "userViewportBounds" in parts,
        "hasAgentViewportBoundsPart": "agentViewportBounds" in parts,
        "hasBlurryShapesPart": "blurryShapes" in parts,
        "hasPeripheralShapesPart": "peripheralShapes" in parts,
        "hasSelectedShapesPart": "selectedShapes" in parts,
        "hasChatHistoryPart": "chatHistory" in parts,
        "hasUserActionHistoryPart": "userActionHistory" in parts,
        "hasTodoListPart": "todoList" in parts,
        "hasCanvasLintsPart": "canvasLints" in parts,
        "hasTimePart": "time" in parts,
        "canEdit": any(_is_edit_action(t) for t in actions),
    }
