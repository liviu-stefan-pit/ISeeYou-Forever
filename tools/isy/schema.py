"""Append-only event fields. New fields are added at the end of a kind, never reordered."""

SCHEMA_VERSION = 2


def field(name, typ, since=1, required=False):
    return (name, typ, since, required)


KINDS = {
    "session_start": [
        field("level", "int", required=True),
        field("zone", "str", required=True),
        field("subzone", "str"),
        field("map", "int"),
        field("x", "int"),
        field("y", "int"),
        field("money", "int"),
        field("xp", "int"),
        field("xp_max", "int"),
        field("name", "str", required=True),
        field("realm", "str"),
        field("schema", "int", since=2),
    ],
    "session_end": [
        field("level", "int", required=True),
        field("seconds", "int"),
        field("xp", "int"),
        field("copper_in", "int"),
        field("copper_out", "int"),
    ],
    "played": [
        field("total_seconds", "int"),
        field("level_seconds", "int"),
    ],
    "xp": [
        field("amount", "int", required=True),
        field("rested", "int"),
        field("level", "int"),
        field("source", "str", required=True),
        field("mob_name", "str"),
        field("mob_level", "int"),
        field("classification", "str"),
        field("creature_type", "str"),
        field("quest_id", "str"),
        field("npc_id", "str", since=2),
    ],
    "level": [
        field("level", "int", required=True),
    ],
    "quest_accept": [
        field("quest_id", "str", required=True),
        field("title", "str"),
        field("level", "int"),
        field("zone", "str"),
        field("map", "int"),
        field("x", "int"),
        field("y", "int"),
        field("giver_name", "str", since=2),
        field("giver_id", "str", since=2),
    ],
    "quest_progress": [
        field("quest_id", "str", required=True),
        field("title", "str"),
        field("objective", "str"),
        field("done", "int"),
        field("required", "int"),
        field("level", "int", since=2),
        field("zone", "str", since=2),
        field("map", "int", since=2),
        field("x", "int", since=2),
        field("y", "int", since=2),
    ],
    "quest_abandon": [
        field("quest_id", "str", required=True),
        field("title", "str"),
        field("level", "int"),
    ],
    "quest_turnin": [
        field("quest_id", "str", required=True),
        field("title", "str"),
        field("xp", "int"),
        field("copper", "int"),
        field("level", "int"),
        field("zone", "str"),
        field("map", "int"),
        field("x", "int"),
        field("y", "int"),
        field("accept_unix", "int"),
        field("duration", "int"),
        field("npc_name", "str", since=2),
        field("npc_id", "str", since=2),
        field("reward_item", "str", since=2),
    ],
    "quest_seen": [
        field("quest_id", "str", since=2, required=True),
        field("title", "str", since=2),
        field("level", "int", since=2),
        field("zone", "str", since=2),
        field("map", "int", since=2),
        field("x", "int", since=2),
        field("y", "int", since=2),
    ],
    "quest_ready": [
        field("quest_id", "str", since=2, required=True),
        field("title", "str", since=2),
        field("level", "int", since=2),
        field("zone", "str", since=2),
        field("map", "int", since=2),
        field("x", "int", since=2),
        field("y", "int", since=2),
    ],
    "money": [
        field("delta", "int"),
        field("balance", "int"),
        field("source", "str"),
        field("detail", "str"),
    ],
    "route": [
        field("map", "int"),
        field("x", "int"),
        field("y", "int"),
        field("zone", "str"),
    ],
    "zone": [
        field("zone", "str", required=True),
        field("subzone", "str"),
        field("map", "int"),
        field("x", "int"),
        field("y", "int"),
    ],
    "fight_start": [
        field("zone", "str"),
        field("map", "int"),
        field("x", "int"),
        field("y", "int"),
        field("mob_name", "str"),
        field("mob_level", "int"),
        field("classification", "str"),
        field("creature_type", "str"),
        field("npc_id", "str", since=2),
    ],
    "fight_end": [
        field("duration", "float"),
        field("xp", "int"),
        field("zone", "str"),
        field("map", "int"),
        field("x", "int"),
        field("y", "int"),
        field("named", "int"),
        field("ticks", "int"),
    ],
    "mob": [
        field("name", "str", required=True),
        field("level", "int"),
        field("classification", "str"),
        field("creature_type", "str"),
        field("zone", "str"),
        field("map", "int"),
        field("x", "int"),
        field("y", "int"),
        field("context", "str"),
        field("npc_id", "str", since=2),
    ],
    "death": [
        field("zone", "str", required=True),
        field("map", "int"),
        field("x", "int"),
        field("y", "int"),
        field("level", "int"),
    ],
    "unghost": [
        field("zone", "str"),
        field("map", "int"),
        field("x", "int"),
        field("y", "int"),
    ],
    "alive": [
        field("zone", "str"),
        field("map", "int"),
        field("x", "int"),
        field("y", "int"),
    ],
    "loot": [
        field("text", "str", required=True),
        field("item_id", "str", since=2),
        field("count", "int", since=2),
        field("quality", "int", since=2),
    ],
    "skill": [
        field("text", "str"),
    ],
    "rep": [
        field("name", "str"),
        field("reaction", "int"),
        field("standing", "int"),
    ],
    "bags": [
        field("slots", "str"),
    ],
    "bag_delta": [
        field("changes", "str", since=2),
    ],
    "group": [
        field("size", "int"),
    ],
    "travel": [
        field("method", "str"),
        field("origin", "str"),
        field("destination", "str"),
    ],
    "character": [
        field("guid", "str", since=2),
        field("class", "str", since=2),
        field("race", "str", since=2),
        field("faction", "str", since=2),
        field("sex", "int", since=2),
        field("level", "int", since=2),
        field("talents", "str", since=2),
        field("gear", "str", since=2),
        field("reason", "str", since=2),
    ],
    "gear": [
        field("slot", "int", since=2),
        field("old_item", "str", since=2),
        field("new_item", "str", since=2),
    ],
    "npc": [
        field("kind", "str", since=2, required=True),
        field("name", "str", since=2),
        field("npc_id", "str", since=2),
        field("zone", "str", since=2),
        field("map", "int", since=2),
        field("x", "int", since=2),
        field("y", "int", since=2),
    ],
    "npc_close": [
        field("kind", "str", since=2),
        field("duration", "int", since=2),
    ],
    "bind": [
        field("zone", "str", since=2),
        field("subzone", "str", since=2),
    ],
    "spell_learned": [
        field("spell_id", "int", since=2),
        field("name", "str", since=2),
        field("level", "int", since=2),
    ],
    "taxi_start": [
        field("origin", "str", since=2),
        field("destination", "str", since=2),
    ],
    "taxi_end": [
        field("destination", "str", since=2),
        field("zone", "str", since=2),
        field("map", "int", since=2),
        field("x", "int", since=2),
        field("y", "int", since=2),
    ],
    "rest": [
        field("resting", "int", since=2),
    ],
    "afk": [
        field("afk", "int", since=2),
    ],
    "mount": [
        field("mounted", "int", since=2),
    ],
    "kill": [
        field("name", "str", since=2),
        field("npc_id", "str", since=2),
        field("level", "int", since=2),
        field("classification", "str", since=2),
        field("creature_type", "str", since=2),
        field("zone", "str", since=2),
        field("map", "int", since=2),
        field("x", "int", since=2),
        field("y", "int", since=2),
    ],
}


def cast_value(value, typ):
    if typ == "int":
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0
    if typ == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
    return "" if value is None else str(value)


def empty_value(typ):
    if typ == "int":
        return 0
    if typ == "float":
        return 0.0
    return ""


def name_fields(event):
    spec = KINDS.get(event["kind"])
    named = {}
    present = {}
    if spec is None:
        event["named"] = named
        event["present"] = present
        event["unknown_kind"] = True
        event["extra"] = list(event["f"])
        return event
    for index, (name, typ, _since, _required) in enumerate(spec):
        if index < len(event["f"]) and event["f"][index] != "":
            named[name] = cast_value(event["f"][index], typ)
            present[name] = True
        else:
            named[name] = empty_value(typ)
            present[name] = False
    event["named"] = named
    event["present"] = present
    event["unknown_kind"] = False
    event["extra"] = event["f"][len(spec):]
    return event


def schema_document():
    kinds = {}
    for kind, fields in KINDS.items():
        kinds[kind] = [
            {"name": name, "type": typ, "since": since, "required": required}
            for name, typ, since, required in fields
        ]
    return {
        "version": SCHEMA_VERSION,
        "coordinates": "x and y are map fractions times 10000",
        "money": "copper",
        "bags": "A bags event replaces inventory. A bag_delta event is the change since the previous bags or bag_delta event.",
        "kills": "inferred is 1 when the combat log did not report the kill and it was derived from a fight window.",
        "segments": "dead, combat, taxi, npc, afk, moving, rest, idle. Higher priority wins when they overlap.",
        "kinds": kinds,
    }


def schema_markdown():
    lines = [
        "---",
        "type: schema",
        "schema: %d" % SCHEMA_VERSION,
        "---",
        "",
        "# I see you forever wiki",
        "",
        "This wiki is rebuilt from append-only logs. Raw lines live in each character's `log/` folder. Compiled pages are derived and can be deleted; the next export restores them.",
        "",
        "Fields are append-only. New fields are added at the end of a kind and never reordered, so older logs still parse. `session_start` carries a `schema` field (2 for the current addon). Sessions without that field are schema 1.",
        "",
        "Tracking starts when the addon first loads on that character. A level 20 character has no record of levels 1-19.",
        "",
        "Stable ids, when the game provides them, are the player GUID, the NPC id (6th segment of a creature GUID), quest ids, and item ids. Names are labels.",
        "",
        "## Layout",
        "",
        "- `index.md` lists characters.",
        "- `characters/<Realm>__<Name>/index.md` lists level chapters.",
        "- `log/YYYY-MM-DD.md` is the immutable source for that day. It is not split.",
        "- `levels/01-10/`, `levels/11-20/`, `levels/21-30/`, then five-level folders through `56-60/`. Each chapter has its own zones, quests, mobs, routes, and sessions.",
        "- `data/SCHEMA.json` is this field list as JSON.",
        "- `data/isy.sqlite` is one database for every character.",
        "- `data/characters/<slug>/events.jsonl` is one named event per line.",
        "- `data/characters/<slug>/check.md` lists anomalies.",
        "",
        "## Event line",
        "",
        "`id, unix time, session id, kind, fields...` separated by tabs. The log stores each line as `event: <line>`.",
        "",
        "Coordinates are map fractions times 10000. Money is copper.",
        "",
        "| Kind | Fields |",
        "| --- | --- |",
    ]
    for kind, fields in KINDS.items():
        rendered = []
        for name, typ, since, required in fields:
            label = name
            if since > 1:
                label += " (v%d)" % since
            if required:
                label += "*"
            rendered.append(label)
        lines.append("| %s | %s |" % (kind, ", ".join(rendered)))
    lines.extend([
        "",
        "A star marks a field that should not be empty. `(v2)` marks a field added in schema 2; schema 1 lines simply omit it.",
        "",
        "Session experience totals come from `xp` events. Quest pages come from quest events. Money totals come from `money` events. A quest turn-in therefore appears once as experience, once as a quest reward, and once in the money ledger.",
        "",
        "`bags` is a full inventory snapshot and replaces derived bag state. `bag_delta` is the change since the previous bag event, written as `itemId:+n` or `itemId:-n`.",
        "",
        "Activity segments cover every second of a session: dead, combat, taxi, npc, afk, moving, rest, then idle. The first matching state wins.",
        "",
        "## Page frontmatter",
        "",
        "Character: `type`, `name`, `realm`, `guid`, `class`, `race`, `faction`, `start_level`, `started`.",
        "Chapter: `type`, `levels`, `seconds`, `xp`, `copper_in`, `copper_out`.",
        "Session: `type`, `id`, `character`, `realm`, `started`, `ended`, `level_start`, `level_end`, `xp`, `copper_in`, `copper_out`, `seconds`.",
        "Quest: `type`, `id`, `title`, `zone`, `level`, `xp`, `copper`, `duration_seconds`.",
        "Mob: `type`, `name`, `classification`, `creature_type`, `level_min`, `level_max`, `xp_samples`, `xp_average`.",
        "Zone: `type`, `name`, `seconds`, `xp`, `deaths`, `quests`.",
        "Route: `type`, `session`, `zone`, `map`, `points`.",
        "Log: `type`, `character`, `realm`, `date`.",
        "",
    ])
    return "\n".join(lines)
