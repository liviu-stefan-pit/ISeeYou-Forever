import shutil

from isy.format import day_key, slugify, yq


def read_lua_string(text, index):
    index += 1
    chars = []
    while index < len(text):
        char = text[index]
        if char == "\\":
            nxt = text[index + 1] if index + 1 < len(text) else ""
            if nxt.isdigit():
                digits = nxt
                cursor = index + 2
                while cursor < len(text) and len(digits) < 3 and text[cursor].isdigit():
                    digits += text[cursor]
                    cursor += 1
                chars.append(chr(int(digits)))
                index = cursor
                continue
            mapping = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}
            chars.append(mapping.get(nxt, nxt))
            index += 2
            continue
        if char == '"':
            return "".join(chars), index + 1
        chars.append(char)
        index += 1
    return "".join(chars), index


def events_table_bounds(text):
    marker = text.find('["events"]')
    if marker < 0:
        marker = text.find("['events']")
    if marker < 0:
        return None
    start = text.find("{", marker)
    if start < 0:
        return None
    index = start + 1
    depth = 1
    while index < len(text) and depth:
        char = text[index]
        if char == '"':
            _, index = read_lua_string(text, index)
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return start, index + 1
        index += 1
    return None


def extract_events(text):
    bounds = events_table_bounds(text)
    if bounds is None:
        return []
    start, end = bounds
    events = []
    index = start + 1
    depth = 1
    while index < end and depth:
        char = text[index]
        if char == '"':
            value, index = read_lua_string(text, index)
            if depth == 1:
                events.append(value)
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        index += 1
    return events


def clear_saved_events(path):
    """Empty the events list in a SavedVariables file. Other fields stay."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    bounds = events_table_bounds(text)
    if bounds is None:
        return 0
    start, end = bounds
    count = len(extract_events(text))
    if text[start:end].strip() == "{}":
        return 0
    updated = text[:start] + "{}" + text[end:]
    temporary = path.with_suffix(".lua.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(updated)
    temporary.replace(path)
    return count


def parse_event(line):
    parts = line.split("\t")
    if len(parts) < 4:
        return None
    try:
        event_id = int(parts[0])
        timestamp = int(parts[1])
        session_id = int(parts[2])
    except ValueError:
        return None
    return {
        "id": event_id,
        "t": timestamp,
        "session": session_id,
        "kind": parts[3],
        "f": parts[4:],
    }


def field(event, index, default=""):
    fields = event["f"]
    if index < len(fields) and fields[index] != "":
        return fields[index]
    return default


def num(event, index, default=0):
    try:
        return int(float(field(event, index, default)))
    except (TypeError, ValueError):
        return default


def flt(event, index, default=0.0):
    try:
        return float(field(event, index, default))
    except (TypeError, ValueError):
        return default


def identity_from_path(path):
    if path.parent.name.lower() == "savedvariables":
        return path.parent.parent.parent.name, path.parent.parent.name
    return "Unknown", path.stem


def find_saves(path):
    if path.is_file():
        return [path]
    found = []
    for candidate in path.rglob("ISeeYouForever.lua"):
        if candidate.parent.name.lower() == "savedvariables":
            found.append(candidate)
    return sorted(found)


def known_ids(log_dir):
    seen = set()
    if not log_dir.exists():
        return seen
    for page in log_dir.glob("*.md"):
        for line in page.read_text(encoding="utf-8").splitlines():
            if line.startswith("event: "):
                event = parse_event(line[7:])
                if event:
                    seen.add(event["id"])
    return seen


def append_logs(folder, realm, name, raw_lines):
    log_dir = folder / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    seen = known_ids(log_dir)
    added = 0
    grouped = {}
    for line in raw_lines:
        event = parse_event(line)
        if not event or event["id"] in seen:
            continue
        seen.add(event["id"])
        grouped.setdefault(day_key(event["t"]), []).append((event, line))
        added += 1
    for day, rows in grouped.items():
        page = log_dir / (day + ".md")
        rows.sort(key=lambda row: (row[0]["t"], row[0]["id"]))
        if not page.exists():
            header = "\n".join([
                "---",
                "type: log",
                "character: " + yq(name),
                "realm: " + yq(realm),
                "date: " + yq(day),
                "---",
                "",
                "# " + day,
                "",
                "",
            ])
            page.write_text(header, encoding="utf-8")
        with page.open("a", encoding="utf-8") as handle:
            for _, line in rows:
                handle.write("event: " + line + "\n")
    return added


def load_events(log_dir):
    events = []
    seen = set()
    for page in sorted(log_dir.glob("*.md")):
        for line in page.read_text(encoding="utf-8").splitlines():
            if not line.startswith("event: "):
                continue
            event = parse_event(line[7:])
            if not event or event["id"] in seen:
                continue
            seen.add(event["id"])
            events.append(event)
    events.sort(key=lambda event: (event["t"], event["id"]))
    return events


def read_meta(text):
    meta = {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return meta
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"')
    return meta


def character_slug(realm, name):
    return slugify(realm) + "__" + slugify(name)


def event_ids(raw_lines, limit=30):
    found = set()
    for line in raw_lines:
        event = parse_event(line)
        if not event:
            continue
        found.add(event["id"])
        if len(found) >= limit:
            break
    return found


def move_folder(source, target):
    if source.resolve() == target.resolve():
        return source
    try:
        source.rename(target)
        return target
    except OSError:
        pass
    try:
        shutil.move(str(source), str(target))
        return target
    except OSError as err:
        print("Could not rename %s (%s). Keeping that folder." % (source, err))
        return source


def align_folder(wiki, realm, name, guid, raw_ids):
    root = wiki / "characters"
    root.mkdir(parents=True, exist_ok=True)
    desired = root / character_slug(realm, name)
    if guid:
        for folder in sorted(path for path in root.iterdir() if path.is_dir()):
            page = folder / "index.md"
            if not page.exists():
                continue
            meta = read_meta(page.read_text(encoding="utf-8"))
            if meta.get("guid") and meta.get("guid") == guid:
                if folder != desired and not desired.exists():
                    return move_folder(folder, desired)
                return folder
    if desired.exists():
        return desired
    if raw_ids:
        for folder in sorted(path for path in root.iterdir() if path.is_dir()):
            if folder == desired:
                continue
            overlap = known_ids(folder / "log") & raw_ids
            if overlap and not desired.exists():
                return move_folder(folder, desired)
    return desired
