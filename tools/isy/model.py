"""Derived records. The raw log stays the source; these tables are rebuilt."""

from isy.schema import name_fields
from isy.parse import field, num

GAP_MOVING = 15
PRIORITY = ("dead", "combat", "taxi", "npc", "afk", "moving", "rest", "idle")


def stamp_levels(events):
    level = 0
    zone = ""
    for event in events:
        kind = event["kind"]
        if kind == "session_start":
            level = num(event, 0) or level
            zone = field(event, 1) or zone
        elif kind == "level":
            level = num(event, 0) or level
        elif kind == "xp":
            gained_at = num(event, 2)
            if gained_at:
                level = gained_at
        elif kind == "zone":
            zone = field(event, 0) or zone
        elif kind == "route":
            zone = field(event, 3) or zone
        event["char_level"] = level if level else 1
        event["char_zone"] = zone
    _backfill_leading_zone(events)


def _backfill_leading_zone(events):
    """Login often records an empty zone for a few seconds. The next real zone is where the character already was."""
    index = 0
    while index < len(events):
        session = events[index]["session"]
        cursor = index
        while cursor < len(events) and events[cursor]["session"] == session and not events[cursor].get("char_zone"):
            cursor += 1
        if cursor < len(events) and events[cursor]["session"] == session and events[cursor].get("char_zone"):
            zone = events[cursor]["char_zone"]
            for earlier in range(index, cursor):
                events[earlier]["char_zone"] = zone
        while cursor < len(events) and events[cursor]["session"] == session:
            cursor += 1
        index = cursor


def prepare_events(events):
    schema = 1
    for event in events:
        name_fields(event)
        if event["kind"] == "session_start":
            if event["present"].get("schema"):
                schema = event["named"]["schema"] or 1
            else:
                schema = 1
        event["schema"] = schema
    stamp_levels(events)
    return events


def identity_from_events(events, realm, name):
    guid = ""
    class_token = ""
    race = ""
    faction = ""
    for event in events:
        named = event.get("named") or {}
        if event["kind"] == "session_start":
            event_name = named.get("name") or ""
            event_realm = named.get("realm") or ""
            if event_name and event_name != "this character":
                name = event_name
            if event_realm:
                realm = event_realm
        elif event["kind"] == "character":
            if named.get("guid"):
                guid = named["guid"]
            if named.get("class"):
                class_token = named["class"]
            if named.get("race"):
                race = named["race"]
            if named.get("faction"):
                faction = named["faction"]
    return realm, name, guid, class_token, race, faction


def _session_map(events):
    sessions = {}
    order = []
    for event in events:
        sid = event["session"]
        if sid not in sessions:
            sessions[sid] = {
                "id": sid,
                "start_t": None,
                "end_t": None,
                "level_start": 0,
                "level_end": 0,
                "reported_level": 0,
                "xp": 0,
                "copper_in": 0,
                "copper_out": 0,
                "seconds": 0,
                "schema": 1,
                "last_t": event["t"],
            }
            order.append(sid)
        row = sessions[sid]
        row["last_t"] = event["t"]
        named = event["named"]
        kind = event["kind"]
        if kind == "session_start":
            row["start_t"] = event["t"]
            row["level_start"] = named.get("level") or 0
            row["level_end"] = max(row["level_end"], row["level_start"])
            row["schema"] = event.get("schema") or 1
        elif kind == "session_end":
            row["end_t"] = event["t"]
            row["reported_level"] = named.get("level") or 0
            row["seconds"] = named.get("seconds") or 0
            row["level_end"] = max(row["level_end"], row["reported_level"])
        elif kind == "level":
            row["level_end"] = max(row["level_end"], named.get("level") or 0)
        elif kind == "xp":
            row["xp"] += named.get("amount") or 0
            row["level_end"] = max(row["level_end"], named.get("level") or 0)
        elif kind == "money":
            delta = named.get("delta") or 0
            if delta > 0:
                row["copper_in"] += delta
            elif delta < 0:
                row["copper_out"] += -delta
        row["level_end"] = max(row["level_end"], event.get("char_level") or 0)
    rows = []
    for sid in order:
        row = sessions[sid]
        if not row["seconds"] and row["start_t"] and row["last_t"]:
            row["seconds"] = max(0, row["last_t"] - row["start_t"])
        rows.append(row)
    return rows


def _levels(events):
    totals = {}
    for index in range(len(events) - 1):
        current = events[index]
        nxt = events[index + 1]
        if current["session"] != nxt["session"]:
            continue
        delta = max(0, nxt["t"] - current["t"])
        level = current.get("char_level") or 1
        bucket = totals.setdefault(level, {"seconds": 0, "xp": 0})
        bucket["seconds"] += delta
    for event in events:
        if event["kind"] != "xp":
            continue
        level = event.get("char_level") or 1
        bucket = totals.setdefault(level, {"seconds": 0, "xp": 0})
        bucket["xp"] += event["named"].get("amount") or 0
    return [
        {"level": level, "seconds": bucket["seconds"], "xp": bucket["xp"]}
        for level, bucket in sorted(totals.items())
    ]


def _point(event, kind, quest_id):
    named = event["named"]
    return {
        "quest_id": quest_id,
        "kind": kind,
        "t": event["t"],
        "session": event["session"],
        "zone": named.get("zone") or event.get("char_zone") or "",
        "map": named.get("map") or 0,
        "x": named.get("x") or 0,
        "y": named.get("y") or 0,
        "objective": named.get("objective") or "",
        "done": named.get("done") or 0,
        "required": named.get("required") or 0,
    }


def _quests(events):
    quests = {}
    points = []

    def row(quest_id, title):
        quest = quests.setdefault(quest_id, {
            "quest_id": quest_id,
            "title": title or ("Quest " + quest_id),
            "zone": "",
            "level": 0,
            "xp": 0,
            "copper": 0,
            "accept_t": None,
            "turnin_t": None,
            "ready_t": None,
            "seen_t": None,
            "duration": 0,
            "giver_name": "",
            "giver_id": "",
            "turnin_name": "",
            "turnin_id": "",
            "reward_item": "",
            "preexisting": 0,
            "abandons": 0,
        })
        if title:
            quest["title"] = title
        return quest

    for event in events:
        kind = event["kind"]
        if kind not in ("quest_accept", "quest_seen", "quest_progress", "quest_ready", "quest_turnin", "quest_abandon"):
            continue
        named = event["named"]
        quest_id = str(named.get("quest_id") or "")
        quest = row(quest_id, named.get("title") or "")
        if named.get("zone"):
            quest["zone"] = named["zone"]
        if named.get("level"):
            quest["level"] = named["level"]
        if kind == "quest_accept":
            if quest["turnin_t"] is None or event["t"] < quest["turnin_t"]:
                if quest["accept_t"] is None:
                    quest["accept_t"] = event["t"]
            quest["giver_name"] = named.get("giver_name") or quest["giver_name"]
            quest["giver_id"] = str(named.get("giver_id") or quest["giver_id"])
            points.append(_point(event, "accept", quest_id))
        elif kind == "quest_seen":
            quest["seen_t"] = event["t"]
            quest["preexisting"] = 1
            points.append(_point(event, "seen", quest_id))
        elif kind == "quest_progress":
            points.append(_point(event, "progress", quest_id))
        elif kind == "quest_ready":
            quest["ready_t"] = event["t"]
            points.append(_point(event, "ready", quest_id))
        elif kind == "quest_turnin":
            quest["turnin_t"] = event["t"]
            quest["xp"] = named.get("xp") or 0
            quest["copper"] = named.get("copper") or 0
            quest["duration"] = named.get("duration") or 0
            if not quest["duration"] and quest["accept_t"]:
                quest["duration"] = max(0, event["t"] - quest["accept_t"])
            quest["turnin_name"] = named.get("npc_name") or ""
            quest["turnin_id"] = str(named.get("npc_id") or "")
            quest["reward_item"] = str(named.get("reward_item") or "")
            points.append(_point(event, "turnin", quest_id))
        elif kind == "quest_abandon":
            quest["abandons"] += 1
    return list(quests.values()), points


def _fights(events):
    pending = None
    fights = []
    for event in events:
        if event["kind"] == "fight_start":
            pending = event
        elif event["kind"] == "fight_end" and pending is not None:
            start = pending
            pending = None
            named = start["named"]
            end = event["named"]
            fights.append({
                "session": event["session"],
                "start_t": start["t"],
                "end_t": event["t"],
                "mob_name": named.get("mob_name") or "",
                "npc_id": str(named.get("npc_id") or ""),
                "level": named.get("mob_level") or 0,
                "zone": end.get("zone") or named.get("zone") or "",
                "map": end.get("map") or named.get("map") or 0,
                "x": end.get("x") or named.get("x") or 0,
                "y": end.get("y") or named.get("y") or 0,
                "duration": end.get("duration") or 0,
                "xp": end.get("xp") or 0,
                "named_ticks": end.get("named") or 0,
                "ticks": end.get("ticks") or 0,
            })
    return fights


def _kill_row(payload, inferred):
    return {
        "t": payload["t"],
        "session": payload["session"],
        "name": payload["name"],
        "npc_id": payload["npc_id"],
        "level": payload["level"],
        "zone": payload["zone"],
        "map": payload["map"],
        "x": payload["x"],
        "y": payload["y"],
        "xp": payload["xp"],
        "inferred": inferred,
    }


def _kills(events, fights):
    explicit = [event for event in events if event["kind"] == "kill"]
    if not explicit:
        rows = []
        for fight in fights:
            if fight["xp"] and fight["mob_name"]:
                rows.append(_kill_row({
                    "t": fight["end_t"],
                    "session": fight["session"],
                    "name": fight["mob_name"],
                    "npc_id": fight["npc_id"],
                    "level": fight["level"],
                    "zone": fight["zone"],
                    "map": fight["map"],
                    "x": fight["x"],
                    "y": fight["y"],
                    "xp": fight["xp"],
                }, 1))
        return rows
    rows = []
    used = set()
    for event in explicit:
        xp = 0
        name = event["named"].get("name") or ""
        for other in events:
            if other["kind"] != "xp" or other["id"] in used:
                continue
            if other["named"].get("source") != "kill":
                continue
            if abs(other["t"] - event["t"]) > 2:
                continue
            other_name = other["named"].get("mob_name") or ""
            if name and other_name and name != other_name:
                continue
            xp += other["named"].get("amount") or 0
            used.add(other["id"])
        named = event["named"]
        rows.append(_kill_row({
            "t": event["t"],
            "session": event["session"],
            "name": name,
            "npc_id": str(named.get("npc_id") or ""),
            "level": named.get("level") or 0,
            "zone": named.get("zone") or "",
            "map": named.get("map") or 0,
            "x": named.get("x") or 0,
            "y": named.get("y") or 0,
            "xp": xp,
        }, 0))
    for fight in fights:
        covered = False
        for event in explicit:
            if event["session"] == fight["session"] and fight["start_t"] <= event["t"] <= fight["end_t"]:
                covered = True
                break
        if covered or not fight["xp"] or not fight["mob_name"]:
            continue
        rows.append(_kill_row({
            "t": fight["end_t"],
            "session": fight["session"],
            "name": fight["mob_name"],
            "npc_id": fight["npc_id"],
            "level": fight["level"],
            "zone": fight["zone"],
            "map": fight["map"],
            "x": fight["x"],
            "y": fight["y"],
            "xp": fight["xp"],
        }, 1))
    return rows


def _deaths(events):
    rows = []
    for event in events:
        if event["kind"] != "death":
            continue
        named = event["named"]
        rows.append({
            "t": event["t"],
            "session": event["session"],
            "zone": named.get("zone") or "",
            "map": named.get("map") or 0,
            "x": named.get("x") or 0,
            "y": named.get("y") or 0,
            "level": named.get("level") or 0,
            "killer_name": named.get("killer_name") or "",
            "killer_id": str(named.get("killer_id") or ""),
            "killer_level": named.get("killer_level") or 0,
            "ability": named.get("ability") or "",
            "attackers": named.get("attackers") or 0,
            "damage": named.get("damage") or 0,
        })
    return rows


def _add_interval(intervals, start, end, state):
    if end > start:
        intervals.append((start, end, state))


def session_segments(rows):
    if not rows:
        return []
    sid = rows[0]["session"]
    start = rows[0]["t"]
    end = rows[-1]["t"]
    for event in rows:
        if event["kind"] == "session_start":
            start = event["t"]
        elif event["kind"] == "session_end":
            end = max(end, event["t"])
    intervals = []
    pending = {}
    afk_on = None
    rest_on = None
    for event in rows:
        kind = event["kind"]
        named = event.get("named") or {}
        if kind == "fight_start":
            pending["combat"] = event["t"]
        elif kind == "fight_end" and "combat" in pending:
            _add_interval(intervals, pending.pop("combat"), event["t"], "combat")
        elif kind == "death":
            pending["dead"] = event["t"]
        elif kind in ("unghost", "alive") and "dead" in pending:
            _add_interval(intervals, pending.pop("dead"), event["t"], "dead")
        elif kind == "taxi_start" or (
            kind == "travel" and named.get("method") == "taxi" and named.get("destination")
        ):
            pending["taxi"] = event["t"]
        elif kind == "taxi_end" and "taxi" in pending:
            _add_interval(intervals, pending.pop("taxi"), event["t"], "taxi")
        elif kind == "npc":
            pending["npc:" + (named.get("kind") or "")] = event["t"]
        elif kind == "npc_close":
            key = "npc:" + (named.get("kind") or "")
            if key in pending:
                _add_interval(intervals, pending.pop(key), event["t"], "npc")
        elif kind == "afk":
            if named.get("afk"):
                afk_on = event["t"]
            elif afk_on is not None:
                _add_interval(intervals, afk_on, event["t"], "afk")
                afk_on = None
        elif kind == "rest":
            if named.get("resting"):
                rest_on = event["t"]
            elif rest_on is not None:
                _add_interval(intervals, rest_on, event["t"], "rest")
                rest_on = None
    for state, opened in pending.items():
        label = "npc" if state.startswith("npc:") else state
        _add_interval(intervals, opened, end, label)
    if afk_on is not None:
        _add_interval(intervals, afk_on, end, "afk")
    if rest_on is not None:
        _add_interval(intervals, rest_on, end, "rest")

    routes = [event for event in rows if event["kind"] == "route"]
    for left, right in zip(routes, routes[1:]):
        if right["t"] - left["t"] > GAP_MOVING:
            continue
        left_named = left.get("named") or {}
        right_named = right.get("named") or {}
        left_at = (left_named.get("map"), left_named.get("x"), left_named.get("y"))
        right_at = (right_named.get("map"), right_named.get("x"), right_named.get("y"))
        if left_at != right_at:
            _add_interval(intervals, left["t"], right["t"], "moving")

    times = {start, end}
    for opened, closed, _state in intervals:
        if start <= opened <= end:
            times.add(opened)
        if start <= closed <= end:
            times.add(closed)
    ordered = sorted(times)
    pieces = []
    zone = ""
    zone_at = []
    for event in rows:
        if event.get("char_zone"):
            zone_at.append((event["t"], event["char_zone"]))
    for left, right in zip(ordered, ordered[1:]):
        if right <= left:
            continue
        active = set()
        for opened, closed, state in intervals:
            if opened <= left and right <= closed:
                active.add(state)
        chosen = "idle"
        for state in PRIORITY:
            if state in active:
                chosen = state
                break
        for when, name in zone_at:
            if when <= left:
                zone = name
        pieces.append((left, right, chosen, zone))
    merged = []
    for piece in pieces:
        if merged and merged[-1][2] == piece[2] and merged[-1][3] == piece[3] and merged[-1][1] == piece[0]:
            previous = merged[-1]
            merged[-1] = (previous[0], piece[1], piece[2], piece[3])
        else:
            merged.append(piece)
    return [
        {
            "session": sid,
            "state": state,
            "start_t": opened,
            "end_t": closed,
            "seconds": closed - opened,
            "zone": zone_name,
        }
        for opened, closed, state, zone_name in merged
    ]


def _segments(events):
    grouped = {}
    order = []
    for event in events:
        if event["session"] not in grouped:
            order.append(event["session"])
            grouped[event["session"]] = []
        grouped[event["session"]].append(event)
    rows = []
    for sid in order:
        rows.extend(session_segments(grouped[sid]))
    return rows


def _npcs(events):
    pending = {}
    rows = []
    for event in events:
        named = event["named"]
        if event["kind"] == "npc":
            pending[named.get("kind") or ""] = event
        elif event["kind"] == "npc_close":
            kind = named.get("kind") or ""
            start = pending.pop(kind, None)
            duration = named.get("duration") or 0
            if not duration and start is not None:
                duration = max(0, event["t"] - start["t"])
            source = start["named"] if start is not None else {}
            rows.append({
                "t": start["t"] if start is not None else event["t"],
                "session": event["session"],
                "kind": kind,
                "name": source.get("name") or "",
                "npc_id": str(source.get("npc_id") or ""),
                "zone": source.get("zone") or "",
                "map": source.get("map") or 0,
                "x": source.get("x") or 0,
                "y": source.get("y") or 0,
                "duration": duration,
            })
    return rows


def _money(events):
    rows = []
    for event in events:
        if event["kind"] != "money":
            continue
        named = event["named"]
        rows.append({
            "t": event["t"],
            "session": event["session"],
            "delta": named.get("delta") or 0,
            "balance": named.get("balance") or 0,
            "source": named.get("source") or "",
            "detail": named.get("detail") or "",
        })
    return rows


def _split_changes(text):
    rows = []
    for part in (text or "").split(","):
        if ":" not in part:
            continue
        item_id, count = part.split(":", 1)
        item_id = item_id.strip()
        count = count.strip()
        if not item_id:
            continue
        rows.append((item_id, count))
    return rows


def _items(events):
    rows = []
    for event in events:
        named = event["named"]
        if event["kind"] == "loot" and named.get("item_id"):
            rows.append({
                "t": event["t"],
                "session": event["session"],
                "item_id": str(named.get("item_id") or ""),
                "count": named.get("count") or 0,
                "quality": named.get("quality") or 0,
                "source": "loot",
                "raw": named.get("text") or "",
            })
        elif event["kind"] == "bags":
            for item_id, count in _split_changes(named.get("slots") or ""):
                try:
                    number = int(count)
                except ValueError:
                    continue
                rows.append({
                    "t": event["t"],
                    "session": event["session"],
                    "item_id": item_id,
                    "count": number,
                    "quality": 0,
                    "source": "snapshot",
                    "raw": "",
                })
        elif event["kind"] == "bag_delta":
            for item_id, count in _split_changes(named.get("changes") or ""):
                try:
                    number = int(count)
                except ValueError:
                    continue
                rows.append({
                    "t": event["t"],
                    "session": event["session"],
                    "item_id": item_id,
                    "count": number,
                    "quality": 0,
                    "source": "delta",
                    "raw": "",
                })
    return rows


def _routes(events):
    rows = []
    for event in events:
        if event["kind"] != "route":
            continue
        named = event["named"]
        rows.append({
            "t": event["t"],
            "session": event["session"],
            "map": named.get("map") or 0,
            "x": named.get("x") or 0,
            "y": named.get("y") or 0,
            "zone": named.get("zone") or "",
        })
    return rows


def derive(slug, realm, name, guid, class_token, race, faction, events):
    start_level = 0
    started = None
    for event in events:
        if event["kind"] == "session_start":
            start_level = event["named"].get("level") or 0
            started = event["t"]
            break
    quests, points = _quests(events)
    fights = _fights(events)
    return {
        "slug": slug,
        "name": name,
        "realm": realm,
        "guid": guid,
        "class_token": class_token,
        "race": race,
        "faction": faction,
        "start_level": start_level,
        "started": started,
        "events": events,
        "sessions": _session_map(events),
        "levels": _levels(events),
        "quests": quests,
        "quest_points": points,
        "fights": fights,
        "kills": _kills(events, fights),
        "deaths": _deaths(events),
        "segments": _segments(events),
        "npcs": _npcs(events),
        "money": _money(events),
        "items": _items(events),
        "route_points": _routes(events),
    }
