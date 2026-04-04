from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ModePart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["mode"] = "mode"
    modeType: str
    partTypes: list[str] = Field(default_factory=list)
    actionTypes: list[str] = Field(default_factory=list)


class ModelNamePart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["modelName"] = "modelName"
    modelName: str


class DebugPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["debug"] = "debug"
    logSystemPrompt: bool = False
    logMessages: bool = False


class MessagesPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["messages"] = "messages"
    agentMessages: list[str] = Field(default_factory=list)
    requestSource: Literal["user", "self", "other-agent"]


class DataPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["data"] = "data"
    data: list[Any] = Field(default_factory=list)


class ScreenshotPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["screenshot"] = "screenshot"
    screenshot: str = ""


class ChatHistoryPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["chatHistory"] = "chatHistory"
    history: list[dict[str, Any]] = Field(default_factory=list)


class BlurryShapesPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["blurryShapes"] = "blurryShapes"
    shapes: list[Any] = Field(default_factory=list)


class PeripheralShapesPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["peripheralShapes"] = "peripheralShapes"
    clusters: list[Any] = Field(default_factory=list)


class SelectedShapesPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["selectedShapes"] = "selectedShapes"
    shapeIds: list[str] = Field(default_factory=list)


class TimePart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["time"] = "time"
    time: str


class TodoListPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["todoList"] = "todoList"
    items: list[Any] = Field(default_factory=list)


class CanvasLintsPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["canvasLints"] = "canvasLints"
    lints: list[dict[str, Any]] = Field(default_factory=list)


class ContextItemsPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["contextItems"] = "contextItems"
    items: list[dict[str, Any]] = Field(default_factory=list)
    requestSource: str


class UserViewportBoundsPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["userViewportBounds"] = "userViewportBounds"
    userBounds: dict[str, Any] | None = None


class AgentViewportBoundsPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["agentViewportBounds"] = "agentViewportBounds"
    agentBounds: dict[str, Any] | None = None


class UserActionHistoryPart(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["userActionHistory"] = "userActionHistory"
    added: list[dict[str, Any]] = Field(default_factory=list)
    removed: list[dict[str, Any]] = Field(default_factory=list)
    updated: list[dict[str, Any]] = Field(default_factory=list)


class AgentPromptModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    mode: ModePart
    debug: DebugPart | None = None
    modelName: ModelNamePart | None = None
    messages: MessagesPart | None = None
    data: DataPart | None = None
    screenshot: ScreenshotPart | None = None
    chatHistory: ChatHistoryPart | None = None
    blurryShapes: BlurryShapesPart | None = None
    peripheralShapes: PeripheralShapesPart | None = None
    selectedShapes: SelectedShapesPart | None = None
    time: TimePart | None = None
    todoList: TodoListPart | None = None
    canvasLints: CanvasLintsPart | None = None
    contextItems: ContextItemsPart | None = None
    userViewportBounds: UserViewportBoundsPart | None = None
    agentViewportBounds: AgentViewportBoundsPart | None = None
    userActionHistory: UserActionHistoryPart | None = None


def validated_prompt_to_dict(model: AgentPromptModel) -> dict[str, Any]:
    return model.model_dump(mode="python", exclude_none=True)
