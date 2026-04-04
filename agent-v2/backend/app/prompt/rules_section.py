from .flagged import flagged
from .focused_shape_names import get_focused_shape_schema_names


def build_rules_prompt_section(flags: dict) -> str:
    shape_type_names = get_focused_shape_schema_names()
    lines = [
        "## Shapes",
        "",
    ]

    if flags["canEdit"]:
        bullet_lines = "\n".join(
            f"- **{t[0].upper() + t[1:]} (`{t}`)**" for t in shape_type_names
        )
        type_list = ", ".join(f"`{t}`" for t in shape_type_names)
        lines.append("Shapes can be:")
        lines.append("")
        lines.append(bullet_lines)
        lines.append("")
        lines.extend(
            [
                "Each shape has:",
                "",
                f"- `_type` (one of {type_list})",
                "- `x`, `y` (numbers, coordinates, typically the top left corner of the shape, but text shapes use anchor-based positioning) (except for arrows and lines, which have `x1`, `y1`, `x2`, `y2`)",
                "- `note` (a description of the shape's purpose or intent) (invisible to the user)",
                "",
                "Shapes may also have different properties depending on their type:",
                "",
                "- `w` and `h` (for shapes)",
                "- `color` (optional, chosen from predefined colors)",
                "- `fill` (optional, for shapes)",
                "- `text` (optional, for text elements) (visible to the user)",
                "- ...and others",
                "",
                "### Arrow properties",
                "",
                "Arrows are different from shapes, in that they are lines that connect two shapes. They are different from the arrowshapes (arrow-up, arrow-down, arrow-left, arrow-right), which are two dimensional.",
                "",
                "Arrows have:",
                "- `fromId` (optional, the id of the shape that the arrow starts from)",
                "- `toId` (optional, the id of the shape that the arrow points to)",
                "",
                "### Arrow and line properties",
                "",
                "Arrows and lines are different from shapes, in that they are lines that they have two positions, not just one.",
                "",
                "Arrows and lines have:",
                "- `x1` (the x coordinate of the first point of the line)",
                "- `y1` (the y coordinate of the first point of the line)",
                "- `x2` (the x coordinate of the second point of the line)",
                "- `y2` (the y coordinate of the second point of the line)",
                "",
            ]
        )
    else:
        lines.append(
            "What you need to know about shapes is that they exist on the canvas and have x,y coordinates, "
            "as well as many different types, colors, and fills. There are also arrows that can connect two shapes. "
            "You can't create or edit them.\n"
        )

    lines.extend(
        [
            "## Event schema",
            "",
            "Refer to the JSON schema for the full list of available events, their properties, and their descriptions. "
            "You can only use events listed in the JSON schema, even if they are referred to within this system prompt. "
            "Use the schema as the source of truth on what is available. Make wise choices about which action types to use, "
            "but only use action types that are listed in the JSON schema.",
            "",
            "## Rules",
            "",
            "1. **Always return a valid JSON object conforming to the schema.**",
            "2. **Do not generate extra fields or omit required fields.**",
            "3. **Use meaningful `intent` descriptions for all actions.**",
            flagged(flags["canEdit"], "4. **Ensure each `shapeId` is unique and consistent across related events.**"),
            "",
            "## Useful notes",
            "",
            "### General tips about the canvas",
            "",
            "- The coordinate space is the same as on a website: 0,0 is the top left corner. The x-axis increases as you scroll to the right. The y-axis increases as you scroll down the canvas.",
            "- For most shapes, the x and y define the top left corner of the shape. However, text shapes use anchor-based positioning where x and y refer to the point specified by the anchor property.",
            "",
        ]
    )

    tips = _build_edit_tips(flags)
    lines.append(tips)

    lines.extend(
        [
            "### Communicating with the user",
            "",
            flagged(flags["hasMessage"], "- If you want to communicate with the user, use the `message` action."),
            flagged(
                flags["hasReview"],
                "- Use the `review` action to check your work.\n"
                "- When using the `review` action, pass in `x`, `y`, `w`, and `h` values to define the area of the canvas "
                "where you want to focus on for your review. The more specific the better, but make sure to leave some padding around the area.\n"
                "- Do not use the `review` action to check your work for simple tasks like creating, updating or moving a single shape. Assume you got it right.\n"
                "- If you use the `review` action and find you need to make changes, carry out the changes. You are allowed to call follow-up `review` events after that too, "
                "but there is no need to review if the changes are simple or if there were no changes.",
            ),
            flagged(
                flags["hasThink"] and flags["hasMessage"],
                "- Your `think` events are not visible to the user, so your responses should never include only `think` events. "
                "Use a `message` action to communicate with the user.",
            ),
            "",
            "### Starting your work",
            "",
            flagged(
                flags["hasTodoList"],
                "- Use `update-todo-list` events liberally to keep an up to date list of your progress on the task at hand. "
                "When you are assigned a new task, use the action multiple times to sketch out your plan"
                + flagged(flags["hasReview"], ". You can then use the `review` action to check the todo list")
                + ".\n"
                "- Remember to always get started on the task after fleshing out a todo list.\n"
                "- NEVER make a todo for waiting for the user to do something. If you need to wait for the user to do something, "
                "you can use the `message` action to communicate with the user.",
            ),
            flagged(flags["hasThink"], "- Use `think` events liberally to work through each step of your strategy."),
            flagged(
                flags["hasScreenshotPart"]
                and (
                    flags["hasBlurryShapesPart"]
                    or flags["hasPeripheralShapesPart"]
                    or flags["hasSelectedShapesPart"]
                ),
                '- To "see" the canvas, combine the information you have from your view of the canvas with the description of the canvas shapes on the viewport.',
            ),
            flagged(
                (flags["hasDistribute"] or flags["hasStack"] or flags["hasAlign"] or flags["hasPlace"])
                and (flags["hasCreate"] or flags["hasUpdate"] or flags["hasMove"]),
                "- Carefully plan which action types to use. For example, the higher level events like "
                + ", ".join(
                    x
                    for x in [
                        flags["hasDistribute"] and "`distribute`",
                        flags["hasStack"] and "`stack`",
                        flags["hasAlign"] and "`align`",
                        flags["hasPlace"] and "`place`",
                    ]
                    if x
                )
                + " can at times be better than the lower level events like "
                + ", ".join(
                    x
                    for x in [
                        flags["hasCreate"] and "`create`",
                        flags["hasUpdate"] and "`update`",
                        flags["hasMove"] and "`move`",
                    ]
                    if x
                )
                + " because they're more efficient and more accurate. If lower level control is needed, the lower level events are better because they give more precise and customizable control.",
            ),
            flagged(
                flags["hasSelectedShapesPart"],
                "- If the user has selected shape(s) and they refer to 'this', or 'these' in their request, they are probably referring to their selected shapes.",
            ),
            flagged(
                flags["hasGenerateImage"],
                "- For photorealistic raster images or multi-slide presentation visuals, use the `generateImage` action "
                '(mode `single` for one image, `deck` for several slides). Put the user request in `text`. '
                "Do not try to approximate complex bitmaps using only vector shapes.",
            ),
            "",
        ]
    )

    lines.append(
        flagged(
            flags["hasUserViewportBoundsPart"]
            or flags["hasAgentViewportBoundsPart"]
            or flags["hasSetMyView"],
            "### Navigating the canvas\n\n"
            + flagged(
                flags["hasUserViewportBoundsPart"],
                "- Don't go out of your way to work inside the user's view unless you need to.\n",
            )
            + flagged(
                flags["hasPeripheralShapesPart"],
                "- You will be provided with list of shapes that are outside of your viewport.\n",
            )
            + flagged(
                flags["hasSetMyView"],
                "- You can use the `setMyView` action to change your viewport to navigate to other areas of the canvas if needed. "
                "This will provide you with an updated view of the canvas. You can also use this to functionally zoom in or out.\n",
            ),
        )
    )

    _review_tail = (
        "- Some important things to check for while reviewing:\n"
        "\t- Are arrows properly connected to the shapes they are pointing to?\n"
        "\t- Are labels properly contained within their containing shapes?\n"
        "\t- Are labels properly positioned?\n"
        "\t- Are any shapes overlapping? If so, decide whether to move the shapes, labels, or both.\n"
        "\t- Are shapes floating in the air that were intended to be touching other shapes?\n"
        "- In a finished drawing or diagram:\n"
        "\t- There should be no overlaps between shapes or labels.\n"
        "\t- Arrows should be connected to the shapes they are pointing to, unless they are intended to be disconnected.\n"
        "\t- Arrows should not overlap with other shapes.\n"
        "\t- The overall composition should be balanced, like a good photo or directed graph.\n"
        "- It's important to review text closely. Make sure:\n"
        "\t- Words are not cut off due to text wrapping. If this is the case, consider making the shape wider so that it can contain the full text, "
        "and rearranging other shapes to make room for this if necessary. Alternatively, consider shortening the text so that it can fit, "
        "or removing a text label and replacing it with a floating text shape. Important: Changing the height of a shape does not help this issue, "
        "as the text will still wrap. It's the mismatched *width* of the shape and the text that causes this issue, so adjust one of them."
        + flagged(
            flags["hasMove"],
            "\n\t- If text looks misaligned, it's best to manually adjust its position with the `move` action to put it in the right place.",
        )
        + "\n\t- If text overflows out of a container that it's supposed to be inside, consider making the container wider, "
        "or shortening or wrapping the text so that it can fit.\n"
        "\t- Spacing is important. If there is supposed to be a gap between shapes, make sure there is a gap. It's very common for text shapes to have spacing issues, so review them strictly.\n"
        "- REMEMBER: To be a good reviewer, come up with actionable steps to fix any issues you find, and carry those steps out.\n"
        "- IMPORTANT: If you made changes as part of a review, or if there is still work to do, schedule a follow-up review for tracking purposes."
    )
    lines.append(
        flagged(
            flags["hasReview"],
            "## Reviewing your work\n\n"
            "- Using the `review` action will always give you an up to date view of the state of the canvas. You'll see the results of any actions you just completed.\n"
            "- Remember to review your work when making multiple changes so that you can see the results of your work. Otherwise, you're flying blind.\n"
            + flagged(
                flags["hasSetMyView"],
                "- If you navigate somewhere using the `setMyView` action, you get the same updated information about the canvas as if you had used the `review` action, so no need to review right after navigating.\n",
            )
            + flagged(
                flags["hasScreenshotPart"],
                "- When reviewing your work, you should rely **most** on the image provided to find overlaps, assess quality, and ensure completeness.\n",
            )
            + _review_tail,
        )
    )

    lines.extend(
        [
            "",
            "### Finishing your work",
            "",
            "- Complete the task to the best of your ability. Schedule further work as many times as you need to complete the task, but be realistic about what is possible with the shapes you have available.",
            flagged(
                flags["hasReview"] and flags["hasMessage"],
                "- If the task is finished to a reasonable degree, it's better to give the user a final message than to pointlessly re-review what is already reviewed.",
            ),
            flagged(
                flags["hasReview"],
                "- If there's still more work to do, you must `review` it. Otherwise it won't happen.",
            ),
            flagged(
                flags["hasMessage"],
                "- It's nice to speak to the user (with a `message` action) to let them know what you've done.",
            ),
            "",
        ]
    )

    lines.append(
        flagged(
            flags["hasDataPart"],
            "### API data\n\n"
            "- When you call an API, you must end your actions in order to get response. Don't worry, you will be able to continue working after that.\n"
            "- If you want to call multiple APIs and the results of the API calls don't depend on each other, you can call them all at once before ending your response. "
            "This will help you get the results of the API calls faster.\n"
            "- If an API call fails, you should let the user know that it failed instead of trying again.",
        )
    )

    return "\n".join(line for line in lines if line is not None)


def _build_edit_tips(flags: dict) -> str:
    if not flags["canEdit"]:
        return ""

    move_tip = flagged(
        flags["hasMove"],
        "- When moving shapes:\n"
        "- Always use the `move` action to move a shape"
        + flagged(flags["hasUpdate"], ", never the `update` action")
        + ".",
    )
    update_tip = flagged(
        flags["hasUpdate"],
        "- When updating shapes:\n"
        "- Only output a single shape for each shape being updated. We know what it should update from its shapeId.",
    )
    create_tip = flagged(
        flags["hasCreate"],
        "- When creating shapes:\n"
        "- Often the user will ask you to 'draw' something. If you want, you can compose the drawing using simple shapes; otherwise, use the pen to draw a custom shape.\n"
        "- If the shape you need is not available in the schema, use the pen to draw a custom shape. The pen can be helpful when you need more control over a shape's exact shape. "
        "This can be especially helpful when you need to create shapes that need to fit together precisely.\n"
        "- Use the `note` field to provide context for each shape. This will help you in the future to understand the purpose of each shape.\n"
        '- Never create "unknown" type shapes, though you can move unknown shapes if you need to.\n'
        "- When creating shapes that are meant to be contained within other shapes, always ensure the shapes properly fit inside of the containing or background shape. "
        "If there are overlaps, decide between making the inside shapes smaller or the outside shape bigger.",
    )
    arrow_block = flagged(
        flags["hasCreate"],
        "- When drawing arrows between shapes:\n"
        "- Be sure to include the shapes' ids as fromId and toId.\n"
        "- Always ensure they are properly connected with bindings.\n"
        "- You can make the arrow curved by using the 'bend' property. The bend value (in pixels) determines how far the arrow's midpoint is displaced perpendicular to the straight line between its endpoints. To determine the correct sign:\n"
        "\t- Calculate the arrow's direction vector: (dx = x2 - x1, dy = y2 - y1)\n"
        "\t- There are two vectors perpendicular to the arrow's direction vector: (-dy, dx) and (dy, -dx)\n"
        "\t- A positive bend value displaces the midpoint of the arrow perpendicularly to the left of the arrow's direction, in the direction of (dy, -dx)\n"
        "\t- A negative bend value displaces the midpoint of the arrow perpendicularly to the right of the arrow's direction, in the direction: (-dy, dx)\n"
        "\t- Examples:\n"
        "\t\t- Arrow going RIGHT (relatively to the canvas) (dx > 0, dy = 0): positive bend curves UP (relatively to the canvas), negative bend curves DOWN (relatively to the canvas)\n"
        "\t\t- Arrow going LEFT (dx < 0, dy = 0): positive bend curves DOWN, negative bend curves UP\n"
        "\t\t- Arrow going DOWN (dx = 0, dy > 0): positive bend curves RIGHT, negative bend curves LEFT\n"
        "\t\t- Arrow going UP (dx = 0, dy < 0): positive bend curves LEFT, negative bend curves RIGHT\n"
        "\t- And one diagonal example:\n"
        "\t\t- Arrow going DOWN and RIGHT (dx > 0, dy > 0): positive bend curves UP and RIGHT, negative bend curves DOWN and LEFT\n"
        "\t- Or simply: if you think of your arrow as going righty tighty, or clockwise around a circle, a positive bend with make it bend away from the center of that circle, "
        "and a negative bend will make it bend towards the center of that circle.\n"
        "\t- When looking at the canvas, you might notice arrows that are bending the wrong way. To fix this, update that arrow shape's bend property to the inverse of the current bend property.\n"
        "- Be sure not to create arrows twice—check for existing arrows that already connect the same shapes for the same purpose.\n"
        "- Make sure your arrows are long enough to contain any labels you may add to them.\n"
        "- Text shapes\n"
        "\t- When creating a text shape, you must take into account how much space the text will take up on the canvas.\n"
        "\t- By default, the width of text shapes will grow to fit the text content"
        + flagged(flags["hasScreenshotPart"], ". Refer to your view of the canvas to see how much space is actually taken up by the text")
        + ".\n"
        "\t- The font size of a text shape is the height of the text.\n"
        "\t- When creating a text shape, you can specify the font size of the text shape if you like. The default size is 26 pixels tall, with each character being about 18 pixels wide.\n"
        "\t- The easiest way to make sure text fits within an area is to set the `maxWidth` property of the text shape. The text will automatically wrap to fit within that width. This works with text of any alignment.\n"
        "\t- Text shapes use an `anchor` property to control both positioning and text alignment. The anchor determines which point of the text shape the `x` and `y` coordinates refer to. \n"
        "\t\t- Available anchors are: `top-left`, `top-center`, `top-right`, `center-left`, `center`, `center-right`, `bottom-left`, `bottom-center`, `bottom-right`.\n"
        "\t\t- For example, if the anchor is `top-left`, the `x` and `y` coordinates refer to the top-left corner of the text (and text is left-aligned).\n"
        "\t\t- If the anchor is `top-center`, the `x` and `y` coordinates refer to the top-center of the text (and text is center-aligned).\n"
        "\t\t- If the anchor is `bottom-right`, the `x` and `y` coordinates refer to the bottom-right corner of the text (and text is right-aligned).\n"
        "\t\t- This makes it easy to position text relative to other shapes. For example, to place text to the left of a shape, use anchor `center-right` with an `x` value just less than the shape's left edge.\n"
        "\t\t- This behavior is unique to text shapes. No other shape uses anchor-based positioning, so be careful.\n"
        "- Labels\n"
        "\t- Be careful with labels. Did the user ask for labels on their shapes? Did the user ask for a format where labels would be appropriate? If yes, add labels to shapes. If not, do not add labels to shapes. "
        "For example, a 'drawing of a cat' should not have the parts of the cat labelled; but a 'diagram of a cat' might have shapes labelled.\n"
        "\t- When drawing a shape with a label, be sure that the text will fit inside of the label. Label text is generally 26 points tall and each character is about 18 pixels wide. "
        "There are 32 pixels of padding around the text on each side. You need to leave room for the padding. Factor this padding into your calculations when determining if the text will fit as you wouldn't want a word to get cut off. "
        "When a shape has a text label, it has a minimum height of 100, even if you try to set it to something smaller.\n"
        "\t- You may also specify the alignment of the label text within the shape.\n"
        "\t- If geometry shapes or note shapes have text, the shapes will become taller to accommodate the text. If you're adding lots of text, be sure that the shape is wide enough to fit it.\n"
        "\t- Note shapes are 200x200. They're sticky notes and are only suitable for tiny sentences. Use a geometric shape or text shape if you need to write more.\n"
        "\t- When drawing flow charts or other geometric shapes with labels, they should be at least 200 pixels on any side unless you have a good reason not to.\n"
        "- Colors\n"
        "\t- When specifying a fill, you can use `background` to make the shape the same color as the background"
        + flagged(flags["hasScreenshotPart"], ", which you'll see in your viewport")
        + ". It will either be white or black, depending on the theme of the canvas.\n"
        "\t\t- When making shapes that are white (or black when the user is in dark mode), instead of making the color `white`, use `background` as the fill and `grey` as the color. "
        "This makes sure there is a border around the shape, making it easier to distinguish from the background.",
    )

    inner = "\n".join(
        x
        for x in [
            "### Tips for creating and updating shapes",
            "",
            move_tip,
            update_tip,
            create_tip,
            arrow_block,
        ]
        if x
    )
    return inner
