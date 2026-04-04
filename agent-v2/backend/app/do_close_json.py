def close_and_parse_json(s: str):
    stack_of_openings: list[str] = []
    i = 0
    string_chars = s
    while i < len(string_chars):
        char = string_chars[i]
        last_opening = stack_of_openings[-1] if stack_of_openings else None

        if char == '"':
            if i > 0 and string_chars[i - 1] == "\\":
                i += 1
                continue
            if last_opening == '"':
                stack_of_openings.pop()
            else:
                stack_of_openings.append('"')

        if last_opening == '"':
            i += 1
            continue

        if char in "{[":
            stack_of_openings.append(char)

        if char == "}" and last_opening == "{":
            stack_of_openings.pop()

        if char == "]" and last_opening == "[":
            stack_of_openings.pop()

        i += 1

    closed = s
    for j in range(len(stack_of_openings) - 1, -1, -1):
        opening = stack_of_openings[j]
        if opening == "{":
            closed += "}"
        elif opening == "[":
            closed += "]"
        elif opening == '"':
            closed += '"'

    try:
        import json

        return json.loads(closed)
    except Exception:
        return None
