_GEO_TYPES = [
    "rectangle",
    "ellipse",
    "triangle",
    "diamond",
    "hexagon",
    "pill",
    "cloud",
    "x-box",
    "check-box",
    "heart",
    "pentagon",
    "octagon",
    "star",
    "parallelogram-right",
    "parallelogram-left",
    "trapezoid",
    "fat-arrow-right",
    "fat-arrow-left",
    "fat-arrow-up",
    "fat-arrow-down",
]


def get_focused_shape_schema_names() -> list[str]:
    return [
        "draw",
        *_GEO_TYPES,
        "line",
        "text",
        "arrow",
        "note",
        "unknown",
    ]
