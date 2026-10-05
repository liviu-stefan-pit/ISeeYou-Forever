#!/usr/bin/env python3
"""Compile ISeeYouForever SavedVariables into a per-character markdown wiki.

Recording starts at the level the character had when the addon loaded.
Each character gets a folder under wiki/characters/.

Usage:
  python tools/export_wiki.py PATH [--out wiki]
  python tools/export_wiki.py --out wiki

PATH is a character SavedVariables file (ISeeYouForever.lua) or a folder
to search, such as WTF/Account. Export before using /isy prune.
"""

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """---
type: schema
---

# I see you forever wiki

This wiki is rebuilt from append-only logs. Raw lines live in each character's `log/` folder. Compiled pages are derived and can be deleted; the next export restores them.

Tracking starts when the addon first loads on that character. A level 20 character has no record of levels 1-19.

## Layout

- `index.md` lists characters.
- `characters/<Realm>__<Name>/index.md` lists level chapters.
- `log/YYYY-MM-DD.md` is the immutable source for that day. It is not split.
- `levels/01-10/`, `levels/11-20/`, `levels/21-30/`, then five-level folders through `56-60/`. Each chapter has its own zones, quests, mobs, routes, and sessions.

## Event line

`id, unix time, session id, kind, fields...` separated by tabs. The log stores each line as `event: <line>`.

| Kind | Fields |
| --- | --- |
| session_start | level, zone, subzone, map, x, y, money, xp, xpMax, name, realm |
| session_end | level, duration seconds, xp, copper in, copper out |
| played | total seconds, level seconds |
| xp | amount, rested, level, source (`kill`, `quest`, `other`), mob name, mob level, classification, creature type, quest id |
| level | level |
| quest_accept | quest id, title, level, zone, map, x, y |
| quest_progress | quest id, title, objective, done, required |
| quest_abandon | quest id, title, level |
| quest_turnin | quest id, title, xp, copper, level, zone, map, x, y, accept unix, duration seconds |
| money | delta copper, balance, source, detail |
| route | map, x, y, zone. Coordinates are map fractions times 10000. |
| zone | zone, subzone, map, x, y |
| fight_start | zone, map, x, y, mob name, mob level, classification, creature type |
| fight_end | duration seconds, xp, zone, map, x, y, named xp ticks, xp ticks |
| mob | name, level, classification, creature type, zone, map, x, y, context |
| death | zone, map, x, y, level |
| unghost | zone, map, x, y |
| alive | zone, map, x, y |
| loot | chat text |
| skill | chat text |
| rep | name, reaction, standing |
| bags | `itemId:count` pairs |
| group | size, 1 when solo |
| travel | method, origin, destination |

Session experience totals come from `xp` events. Quest pages come from quest events. Money totals come from `money` events. A quest turn-in therefore appears once as experience, once as a quest reward, and once in the money ledger.

## Page frontmatter

Character: `type`, `name`, `realm`, `start_level`, `started`.
Chapter: `type`, `levels`, `seconds`, `xp`, `copper_in`, `copper_out`.
Session: `type`, `id`, `character`, `realm`, `started`, `ended`, `level_start`, `level_end`, `xp`, `copper_in`, `copper_out`, `seconds`.
Quest: `type`, `id`, `title`, `zone`, `level`, `xp`, `copper`, `duration_seconds`.
Mob: `type`, `name`, `classification`, `creature_type`, `level_min`, `level_max`, `xp_samples`, `xp_average`.
Zone: `type`, `name`, `seconds`, `xp`, `deaths`, `quests`.
Route: `type`, `session`, `zone`, `map`, `points`.
Log: `type`, `character`, `realm`, `date`.
"""


def slugify(text):
    cleaned = []
    for char in str(text):
        if char.isalnum():
            cleaned.append(char.lower())
        elif char in " -_":
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "unknown"


def yq(value):
    text = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return '"' + text + '"'


def iso(timestamp):
    return datetime.fromtimestamp(int(timestamp), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_key(timestamp):
    return datetime.fromtimestamp(int(timestamp), timezone.utc).strftime("%Y-%m-%d")


def copper_text(copper):
    copper = int(copper)
    sign = "-" if copper < 0 else ""
    copper = abs(copper)
    gold, rem = divmod(copper, 10000)
    silver, coins = divmod(rem, 100)
    if gold:
        return "%s%dg %ds %dc" % (sign, gold, silver, coins)
    if silver:
        return "%s%ds %dc" % (sign, silver, coins)
    return "%s%dc" % (sign, coins)


def duration_text(seconds):
    seconds = int(seconds)
    if seconds < 0:
        seconds = 0
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return "%dh %dm" % (hours, minutes)
    return "%dm %ds" % (minutes, secs)


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


def extract_events(text):
    marker = text.find('["events"]')
    if marker < 0:
        marker = text.find("['events']")
    if marker < 0:
        return []
    start = text.find("{", marker)
    if start < 0:
        return []
    events = []
    index = start + 1
    depth = 1
    while index < len(text) and depth:
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


def fresh_dir(path):
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def write_page(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def new_session(session_id):
    return {
        "id": session_id,
        "start": None,
        "end": None,
        "level_start": None,
        "level_end": None,
        "xp": 0,
        "copper_in": 0,
        "copper_out": 0,
        "quests": [],
        "deaths": [],
        "fights": [],
        "pending_fight": None,
        "money": {},
        "levels": [],
        "last": None,
        "reported_seconds": None,
    }


def ensure_mob(mobs, mob_name):
    return mobs.setdefault(mob_name, {
        "levels": set(),
        "classes": set(),
        "types": set(),
        "zones": set(),
        "xp": [],
        "seen": 0,
    })


def add_mob_meta(mobs, mob_name, level, classification, creature_type, zone, count=True):
    if not mob_name:
        return
    mob = ensure_mob(mobs, mob_name)
    if level:
        try:
            mob["levels"].add(int(level))
        except ValueError:
            pass
    if classification:
        mob["classes"].add(classification)
    if creature_type:
        mob["types"].add(creature_type)
    if zone:
        mob["zones"].add(zone)
    if count:
        mob["seen"] += 1


def ensure_quest(quests, quest_id, title):
    quest = quests.setdefault(quest_id, {
        "title": title or ("Quest " + quest_id),
        "accepts": [],
        "turnins": [],
        "abandons": 0,
        "progress": [],
        "zone": "",
        "level": "",
    })
    if title:
        quest["title"] = title
    return quest


BANDS = (
    (1, 10),
    (11, 20),
    (21, 30),
    (31, 35),
    (36, 40),
    (41, 45),
    (46, 50),
    (51, 55),
    (56, 60),
)


def band_for(level):
    level = int(level or 1)
    if level < 1:
        level = 1
    for band in BANDS:
        if band[0] <= level <= band[1]:
            return band
    return BANDS[-1]


def band_slug(band):
    return "%02d-%02d" % band


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


def gap_seconds(events):
    totals = {}
    for index in range(len(events) - 1):
        current = events[index]
        nxt = events[index + 1]
        if current["session"] != nxt["session"]:
            continue
        delta = max(0, nxt["t"] - current["t"])
        band = band_for(current["char_level"])
        totals[band] = totals.get(band, 0) + delta
    return totals


def prepare_slice(all_events, band_events):
    sliced = [dict(event) for event in band_events]
    first = sliced[0]
    if first["kind"] not in ("session_start", "zone") and first.get("char_zone"):
        sliced.insert(0, {
            "id": first["id"],
            "t": first["t"],
            "session": first["session"],
            "kind": "zone",
            "f": [first["char_zone"], "", "0", "0", "0"],
            "char_level": first["char_level"],
            "char_zone": first["char_zone"],
        })
    last = band_events[-1]
    seen = False
    for event in all_events:
        if seen:
            if event["session"] == last["session"] and event["t"] >= last["t"]:
                sliced.append({
                    "id": event["id"],
                    "t": event["t"],
                    "session": event["session"],
                    "kind": "band_end",
                    "f": [],
                })
            break
        if event["id"] == last["id"]:
            seen = True
    return sliced


def rebuild(folder, realm, name, events, chapter=None, elapsed=None):
    for sub in ("sessions", "quests", "mobs", "zones", "routes"):
        fresh_dir(folder / sub)

    sessions = {}
    quests = {}
    mobs = {}
    zones = {}
    routes = {}
    current_zone = {"name": "", "start": None}
    last_t = None

    def session_for(event):
        return sessions.setdefault(event["session"], new_session(event["session"]))

    def close_zone(at):
        if not current_zone["name"] or current_zone["start"] is None or at is None:
            return
        zone = zones.setdefault(current_zone["name"], {
            "seconds": 0,
            "xp": 0,
            "deaths": 0,
            "quests": 0,
            "visits": 0,
        })
        zone["seconds"] += max(0, at - current_zone["start"])
        current_zone["start"] = at

    def enter_zone(zone_name, at):
        zone_name = zone_name or "Unknown"
        if current_zone["name"] == zone_name:
            return
        close_zone(at)
        current_zone["name"] = zone_name
        current_zone["start"] = at
        zones.setdefault(zone_name, {
            "seconds": 0,
            "xp": 0,
            "deaths": 0,
            "quests": 0,
            "visits": 0,
        })["visits"] += 1

    for event in events:
        last_t = event["t"]
        session = session_for(event)
        session["last"] = event["t"]
        if "anchor" not in session:
            session["anchor"] = event["t"]
        kind = event["kind"]

        if kind == "session_start":
            session["start"] = event["t"]
            session["level_start"] = num(event, 0)
            enter_zone(field(event, 1), event["t"])
        elif kind == "session_end":
            session["end"] = event["t"]
            session["level_end"] = num(event, 0)
            session["reported_seconds"] = num(event, 1)
            close_zone(event["t"])
            current_zone["start"] = None
        elif kind == "xp":
            amount = num(event, 0)
            session["xp"] += amount
            zone_name = current_zone["name"]
            if zone_name and zone_name in zones:
                zones[zone_name]["xp"] += amount
            mob_name = field(event, 4)
            if mob_name:
                add_mob_meta(mobs, mob_name, field(event, 5), field(event, 6), field(event, 7), zone_name, False)
                ensure_mob(mobs, mob_name)["xp"].append(amount)
        elif kind == "level":
            level = num(event, 0)
            session["level_end"] = level
            session["levels"].append((event["t"], level))
        elif kind == "quest_accept":
            quest = ensure_quest(quests, field(event, 0), field(event, 1))
            quest["accepts"].append(event["t"])
            quest["zone"] = field(event, 3) or quest["zone"]
            quest["level"] = field(event, 2) or quest["level"]
        elif kind == "quest_progress":
            quest = ensure_quest(quests, field(event, 0), field(event, 1))
            quest["progress"].append(field(event, 2) + " " + field(event, 3) + "/" + field(event, 4))
        elif kind == "quest_abandon":
            ensure_quest(quests, field(event, 0), field(event, 1))["abandons"] += 1
        elif kind == "quest_turnin":
            quest = ensure_quest(quests, field(event, 0), field(event, 1))
            quest["turnins"].append({
                "t": event["t"],
                "xp": num(event, 2),
                "copper": num(event, 3),
                "level": field(event, 4),
                "zone": field(event, 5),
                "duration": num(event, 10),
            })
            quest["zone"] = field(event, 5) or quest["zone"]
            quest["level"] = field(event, 4) or quest["level"]
            session["quests"].append(field(event, 0))
            zone_name = current_zone["name"]
            if zone_name and zone_name in zones:
                zones[zone_name]["quests"] += 1
        elif kind == "money":
            delta = num(event, 0)
            source = field(event, 2, "unknown")
            if delta > 0:
                session["copper_in"] += delta
            elif delta < 0:
                session["copper_out"] += -delta
            bucket = session["money"].setdefault(source, {"in": 0, "out": 0})
            if delta > 0:
                bucket["in"] += delta
            elif delta < 0:
                bucket["out"] += -delta
        elif kind == "route":
            zone_name = field(event, 3) or current_zone["name"] or "Unknown"
            key = (event["session"], zone_name, field(event, 0, "0"))
            routes.setdefault(key, []).append((num(event, 1), num(event, 2)))
        elif kind == "zone":
            enter_zone(field(event, 0), event["t"])
        elif kind == "fight_start":
            session["pending_fight"] = {
                "zone": field(event, 0),
                "mob": field(event, 4),
                "level": field(event, 5),
                "classification": field(event, 6),
                "creature_type": field(event, 7),
                "t": event["t"],
            }
            add_mob_meta(mobs, field(event, 4), field(event, 5), field(event, 6), field(event, 7), field(event, 0))
        elif kind == "fight_end":
            pending = session["pending_fight"] or {}
            session["pending_fight"] = None
            session["fights"].append({
                "zone": field(event, 2) or pending.get("zone", ""),
                "mob": pending.get("mob", ""),
                "level": pending.get("level", ""),
                "classification": pending.get("classification", ""),
                "creature_type": pending.get("creature_type", ""),
                "duration": flt(event, 0),
                "xp": num(event, 1),
                "named": num(event, 6),
                "ticks": num(event, 7),
            })
        elif kind == "mob":
            add_mob_meta(mobs, field(event, 0), field(event, 1), field(event, 2), field(event, 3), field(event, 4))
        elif kind == "death":
            zone_name = field(event, 0) or current_zone["name"]
            session["deaths"].append((event["t"], zone_name, field(event, 4)))
            if zone_name and zone_name in zones:
                zones[zone_name]["deaths"] += 1

    close_zone(last_t)

    start_level = None
    started = None
    for event in events:
        if event["kind"] == "session_start":
            start_level = num(event, 0)
            started = event["t"]
            break

    quest_files = {}
    for quest_id, quest in sorted(quests.items(), key=lambda item: item[1]["title"].lower()):
        filename = slugify(quest_id + "-" + quest["title"]) + ".md"
        quest_files[quest_id] = filename
        turnin = quest["turnins"][-1] if quest["turnins"] else None
        duration = turnin["duration"] if turnin else 0
        if not duration and quest["accepts"] and turnin:
            duration = max(0, turnin["t"] - quest["accepts"][0])
        lines = [
            "---",
            "type: quest",
            "id: " + yq(quest_id),
            "title: " + yq(quest["title"]),
            "zone: " + yq(quest["zone"]),
            "level: " + yq(quest["level"]),
            "xp: " + str(turnin["xp"] if turnin else 0),
            "copper: " + str(turnin["copper"] if turnin else 0),
            "duration_seconds: " + str(duration),
            "---",
            "",
            "# " + quest["title"],
            "",
            "Quest " + quest_id + " for " + name + ".",
            "",
        ]
        if quest["accepts"]:
            lines.append("- Accepted: " + iso(quest["accepts"][0]))
        if turnin:
            lines.append("- Turned in: " + iso(turnin["t"]))
            lines.append("- Reward: " + str(turnin["xp"]) + " XP, " + copper_text(turnin["copper"]))
            if duration:
                lines.append("- Accept to turn-in: " + duration_text(duration))
        if quest["abandons"]:
            lines.append("- Abandoned: " + str(quest["abandons"]))
        if quest["progress"]:
            lines.append("")
            lines.append("## Objectives")
            lines.append("")
            for note in quest["progress"]:
                lines.append("- " + note)
        lines.append("")
        write_page(folder / "quests" / filename, "\n".join(lines))

    mob_files = {}
    for mob_name, mob in sorted(mobs.items(), key=lambda item: item[0].lower()):
        filename = slugify(mob_name) + ".md"
        mob_files[mob_name] = filename
        levels = sorted(mob["levels"])
        average = round(sum(mob["xp"]) / len(mob["xp"])) if mob["xp"] else 0
        lines = [
            "---",
            "type: mob",
            "name: " + yq(mob_name),
            "classification: " + yq(", ".join(sorted(mob["classes"]))),
            "creature_type: " + yq(", ".join(sorted(mob["types"]))),
            "level_min: " + str(levels[0] if levels else 0),
            "level_max: " + str(levels[-1] if levels else 0),
            "xp_samples: " + str(len(mob["xp"])),
            "xp_average: " + str(average),
            "---",
            "",
            "# " + mob_name,
            "",
            "Seen " + str(mob["seen"]) + " times.",
            "",
        ]
        if levels:
            lines.append("- Levels: " + ", ".join(str(level) for level in levels))
        if mob["classes"]:
            lines.append("- Classification: " + ", ".join(sorted(mob["classes"])))
        if mob["types"]:
            lines.append("- Type: " + ", ".join(sorted(mob["types"])))
        if mob["zones"]:
            lines.append("- Zones: " + ", ".join(sorted(mob["zones"])))
        if mob["xp"]:
            lines.append("- XP samples: " + ", ".join(str(amount) for amount in mob["xp"]))
            lines.append("- Average XP: " + str(average))
        lines.append("")
        write_page(folder / "mobs" / filename, "\n".join(lines))

    zone_files = {}
    for zone_name, zone in sorted(zones.items(), key=lambda item: item[0].lower()):
        filename = slugify(zone_name) + ".md"
        zone_files[zone_name] = filename
        lines = [
            "---",
            "type: zone",
            "name: " + yq(zone_name),
            "seconds: " + str(zone["seconds"]),
            "xp: " + str(zone["xp"]),
            "deaths: " + str(zone["deaths"]),
            "quests: " + str(zone["quests"]),
            "---",
            "",
            "# " + zone_name,
            "",
            "- Time: " + duration_text(zone["seconds"]),
            "- Experience: " + str(zone["xp"]),
            "- Deaths: " + str(zone["deaths"]),
            "- Quests turned in: " + str(zone["quests"]),
            "- Visits: " + str(zone["visits"]),
            "",
        ]
        write_page(folder / "zones" / filename, "\n".join(lines))

    route_links = []
    for (session_id, zone_name, map_id), points in sorted(routes.items(), key=lambda item: (item[0][0], item[0][1])):
        filename = slugify(str(session_id) + "-" + zone_name + "-" + str(map_id)) + ".md"
        route_links.append((session_id, zone_name, filename, len(points)))
        body = [
            "---",
            "type: route",
            "session: " + str(session_id),
            "zone: " + yq(zone_name),
            "map: " + yq(map_id),
            "points: " + str(len(points)),
            "---",
            "",
            "# " + zone_name + " session " + str(session_id),
            "",
            "Coordinates are percentages of the map.",
            "",
        ]
        for x_value, y_value in points:
            body.append("- %.2f %.2f" % (x_value / 100.0, y_value / 100.0))
        body.append("")
        write_page(folder / "routes" / filename, "\n".join(body))

    total_xp = 0
    total_in = 0
    total_out = 0
    total_deaths = 0
    total_fights = 0
    for session in sessions.values():
        seconds = None
        if chapter is None and session["reported_seconds"] is not None:
            seconds = session["reported_seconds"]
        start_at = session["start"] or session.get("anchor")
        if seconds is None and start_at and session["last"]:
            seconds = max(0, session["last"] - start_at)
        session["seconds"] = seconds or 0
        if session["level_end"] is None:
            session["level_end"] = session["level_start"]
        total_xp += session["xp"]
        total_in += session["copper_in"]
        total_out += session["copper_out"]
        total_deaths += len(session["deaths"])
        total_fights += len(session["fights"])
        rate = round(session["xp"] / session["seconds"] * 3600) if session["seconds"] else 0
        lines = [
            "---",
            "type: session",
            "id: " + str(session["id"]),
            "character: " + yq(name),
            "realm: " + yq(realm),
            "started: " + yq(iso(session["start"]) if session["start"] else ""),
            "ended: " + yq(iso(session["end"]) if session["end"] else ""),
            "level_start: " + str(session["level_start"] or 0),
            "level_end: " + str(session["level_end"] or 0),
            "xp: " + str(session["xp"]),
            "copper_in: " + str(session["copper_in"]),
            "copper_out: " + str(session["copper_out"]),
            "seconds: " + str(session["seconds"]),
            "---",
            "",
            "# Session " + str(session["id"]),
            "",
            "- Time: " + duration_text(session["seconds"]),
            "- Level: " + str(session["level_start"] or "?") + " to " + str(session["level_end"] or "?"),
            "- Experience: " + str(session["xp"]) + " (" + str(rate) + "/hr)",
            "- Money in: " + copper_text(session["copper_in"]),
            "- Money out: " + copper_text(session["copper_out"]),
            "",
        ]
        if session["money"]:
            lines.append("## Money")
            lines.append("")
            for source, bucket in sorted(session["money"].items()):
                lines.append("- " + source + ": in " + copper_text(bucket["in"]) + ", out " + copper_text(bucket["out"]))
            lines.append("")
        if session["quests"]:
            lines.append("## Quests turned in")
            lines.append("")
            for quest_id in session["quests"]:
                title = quests[quest_id]["title"] if quest_id in quests else quest_id
                link = quest_files.get(quest_id, "")
                if link:
                    lines.append("- [" + title + "](../quests/" + link + ")")
                else:
                    lines.append("- " + title)
            lines.append("")
        if session["fights"]:
            lines.append("## Fights")
            lines.append("")
            for fight in session["fights"]:
                label = fight["mob"] or "unnamed mob"
                if fight["ticks"] and not fight["named"]:
                    label += " (name hidden during combat)"
                lines.append(
                    "- " + label + " in " + (fight["zone"] or "unknown")
                    + ", " + ("%.1f" % fight["duration"]) + "s, " + str(fight["xp"]) + " XP"
                )
            lines.append("")
        if session["deaths"]:
            lines.append("## Deaths")
            lines.append("")
            for when, zone_name, level in session["deaths"]:
                lines.append("- " + iso(when) + " in " + zone_name + " at level " + (level or "?"))
            lines.append("")
        write_page(folder / "sessions" / (str(session["id"]) + ".md"), "\n".join(lines))

    if chapter is not None:
        lo, hi = chapter
        shown_seconds = elapsed if elapsed is not None else sum(session["seconds"] for session in sessions.values())
        rate = round(total_xp / shown_seconds * 3600) if shown_seconds else 0
        lines = [
            "---",
            "type: chapter",
            "levels: " + yq("%d-%d" % (lo, hi)),
            "seconds: " + str(shown_seconds),
            "xp: " + str(total_xp),
            "copper_in: " + str(total_in),
            "copper_out: " + str(total_out),
            "---",
            "",
            "# Levels %d-%d" % (lo, hi),
            "",
            "- Time: " + duration_text(shown_seconds),
            "- Experience: " + str(total_xp) + " (" + str(rate) + "/hr)",
            "- Money in: " + copper_text(total_in),
            "- Money out: " + copper_text(total_out),
            "- Deaths: " + str(total_deaths),
            "- Quests turned in: " + str(sum(1 for quest in quests.values() if quest["turnins"])),
            "",
            "## Zones",
            "",
        ]
        if zone_files:
            for zone_name, filename in zone_files.items():
                zone = zones[zone_name]
                lines.append(
                    "- [" + zone_name + "](zones/" + filename + ") - "
                    + duration_text(zone["seconds"]) + ", " + str(zone["xp"]) + " XP"
                )
        else:
            lines.append("- None yet.")
        lines.extend(["", "## Quests", ""])
        if quest_files:
            for quest_id, filename in quest_files.items():
                lines.append("- [" + quests[quest_id]["title"] + "](quests/" + filename + ")")
        else:
            lines.append("- None yet.")
        lines.extend(["", "## Mobs", ""])
        if mob_files:
            for mob_name, filename in mob_files.items():
                lines.append("- [" + mob_name + "](mobs/" + filename + ")")
        else:
            lines.append("- None yet.")
        lines.extend(["", "## Routes", ""])
        if route_links:
            for session_id, zone_name, filename, count in route_links:
                lines.append("- [Session " + str(session_id) + " " + zone_name + "](routes/" + filename + ") (" + str(count) + " points)")
        else:
            lines.append("- None yet.")
        lines.append("")
        write_page(folder / "index.md", "\n".join(lines))
        return {
            "lo": lo,
            "hi": hi,
            "slug": band_slug(chapter),
            "seconds": shown_seconds,
            "xp": total_xp,
            "copper_in": total_in,
            "copper_out": total_out,
        }

    lines = [
        "---",
        "type: character",
        "name: " + yq(name),
        "realm: " + yq(realm),
        "start_level: " + str(start_level or 0),
        "started: " + yq(iso(started) if started else ""),
        "---",
        "",
        "# " + name + " - " + realm,
        "",
    ]
    if start_level:
        lines.append(
            "Recording began at level "
            + str(start_level)
            + " on "
            + (day_key(started) if started else "the first session")
            + ". Earlier play was not observed."
        )
    else:
        lines.append("No session has been recorded yet.")
    lines.extend([
        "",
        "## Totals",
        "",
        "- Sessions: " + str(len(sessions)),
        "- Experience: " + str(total_xp),
        "- Money in: " + copper_text(total_in),
        "- Money out: " + copper_text(total_out),
        "- Quests turned in: " + str(sum(1 for quest in quests.values() if quest["turnins"])),
        "- Deaths: " + str(total_deaths),
        "- Fight windows: " + str(total_fights),
        "",
        "## Level timeline",
        "",
    ])
    for session in sorted(sessions.values(), key=lambda item: item["id"]):
        if session["start"] and session["level_start"]:
            lines.append("- " + iso(session["start"]) + " level " + str(session["level_start"]) + " (session start)")
        for when, level in session["levels"]:
            lines.append("- " + iso(when) + " level " + str(level))
    lines.extend(["", "## Sessions", ""])
    for session in sorted(sessions.values(), key=lambda item: item["id"]):
        lines.append("- [Session " + str(session["id"]) + "](sessions/" + str(session["id"]) + ".md)")
    lines.extend(["", "## Quests", ""])
    for quest_id, filename in quest_files.items():
        lines.append("- [" + quests[quest_id]["title"] + "](quests/" + filename + ")")
    lines.extend(["", "## Mobs", ""])
    for mob_name, filename in mob_files.items():
        lines.append("- [" + mob_name + "](mobs/" + filename + ")")
    lines.extend(["", "## Zones", ""])
    for zone_name, filename in zone_files.items():
        lines.append("- [" + zone_name + "](zones/" + filename + ")")
    lines.extend(["", "## Routes", ""])
    for session_id, zone_name, filename, count in route_links:
        lines.append("- [Session " + str(session_id) + " " + zone_name + "](routes/" + filename + ") (" + str(count) + " points)")
    lines.append("")
    write_page(folder / "index.md", "\n".join(lines))
    return {
        "name": name,
        "realm": realm,
        "start_level": start_level or 0,
        "started": iso(started) if started else "",
        "events": len(events),
    }


def rebuild_character(folder, realm, name, events):
    for sub in ("sessions", "quests", "mobs", "zones", "routes", "levels"):
        path = folder / sub
        if path.exists():
            shutil.rmtree(path)
    stamp_levels(events)
    grouped = {}
    for event in events:
        grouped.setdefault(band_for(event["char_level"]), []).append(event)
    played = gap_seconds(events)
    chapters = []
    for band in BANDS:
        band_events = grouped.get(band)
        if not band_events:
            continue
        chapter_dir = folder / "levels" / band_slug(band)
        stats = rebuild(
            chapter_dir,
            realm,
            name,
            prepare_slice(events, band_events),
            chapter=band,
            elapsed=played.get(band, 0),
        )
        chapters.append(stats)

    start_level = None
    started = None
    for event in events:
        if event["kind"] == "session_start":
            start_level = num(event, 0)
            started = event["t"]
            break
    lines = [
        "---",
        "type: character",
        "name: " + yq(name),
        "realm: " + yq(realm),
        "start_level: " + str(start_level or 0),
        "started: " + yq(iso(started) if started else ""),
        "---",
        "",
        "# " + name + " - " + realm,
        "",
    ]
    if start_level:
        lines.append(
            "Recording began at level "
            + str(start_level)
            + " on "
            + (day_key(started) if started else "the first session")
            + ". Earlier play was not observed."
        )
    else:
        lines.append("No session has been recorded yet.")
    lines.extend([
        "",
        "Open one level chapter. The raw log stays in `log/` and is not copied into these chapters.",
        "",
        "## Level chapters",
        "",
    ])
    if not chapters:
        lines.append("No chapters yet.")
    for chapter in chapters:
        rate = round(chapter["xp"] / chapter["seconds"] * 3600) if chapter["seconds"] else 0
        lines.append(
            "- [%d-%d](levels/%s/index.md) - %s, %d XP (%d/hr), in %s, out %s"
            % (
                chapter["lo"],
                chapter["hi"],
                chapter["slug"],
                duration_text(chapter["seconds"]),
                chapter["xp"],
                rate,
                copper_text(chapter["copper_in"]),
                copper_text(chapter["copper_out"]),
            )
        )
    lines.append("")
    write_page(folder / "index.md", "\n".join(lines))
    return {
        "name": name,
        "realm": realm,
        "start_level": start_level or 0,
        "started": iso(started) if started else "",
        "events": len(events),
    }


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


def write_schema(wiki):
    wiki.mkdir(parents=True, exist_ok=True)
    (wiki / "SCHEMA.md").write_text(SCHEMA, encoding="utf-8")


def write_root_index(wiki):
    characters = []
    root = wiki / "characters"
    if root.exists():
        for folder in sorted(path for path in root.iterdir() if path.is_dir()):
            page = folder / "index.md"
            if not page.exists():
                continue
            meta = read_meta(page.read_text(encoding="utf-8"))
            characters.append((folder.name, meta))
    lines = [
        "---",
        "type: index",
        "---",
        "",
        "# I see you forever",
        "",
        "One folder per character. Recording starts at the level that character had when the addon was installed.",
        "",
    ]
    if not characters:
        lines.append("No character logs yet.")
    else:
        lines.append("## Characters")
        lines.append("")
        for folder_name, meta in characters:
            label = meta.get("name", folder_name)
            realm = meta.get("realm", "")
            if realm:
                label += " - " + realm
            level = meta.get("start_level", "")
            started = meta.get("started", "")
            extra = []
            if level and level != "0":
                extra.append("from level " + level)
            if started:
                extra.append(started)
            suffix = " (" + ", ".join(extra) + ")" if extra else ""
            lines.append("- [" + label + "](characters/" + folder_name + "/index.md)" + suffix)
    lines.append("")
    (wiki / "index.md").write_text("\n".join(lines), encoding="utf-8")


def export_save(lua_path, wiki):
    text = lua_path.read_text(encoding="utf-8")
    if "ISYF_Char" not in text:
        return None
    raw_lines = extract_events(text)
    if not raw_lines:
        return None
    realm, name = identity_from_path(lua_path)
    if realm == "Unknown":
        for line in raw_lines:
            event = parse_event(line)
            if event and event["kind"] == "session_start":
                if field(event, 10):
                    realm = field(event, 10)
                event_name = field(event, 9)
                if event_name and event_name != "this character":
                    name = event_name
                break
    folder = wiki / "characters" / (slugify(realm) + "__" + slugify(name))
    folder.mkdir(parents=True, exist_ok=True)
    added = append_logs(folder, realm, name, raw_lines)
    events = load_events(folder / "log")
    meta = rebuild_character(folder, realm, name, events)
    meta["added"] = added
    meta["folder"] = str(folder)
    return meta


def main():
    parser = argparse.ArgumentParser(description="Build the I see you forever markdown wiki.")
    parser.add_argument("path", nargs="?", help="SavedVariables file or a folder to search")
    parser.add_argument("--out", default="", help="Wiki directory. Defaults to ./wiki next to the addon repo.")
    args = parser.parse_args()
    wiki = Path(args.out) if args.out else Path(__file__).resolve().parent.parent / "wiki"
    write_schema(wiki)
    results = []
    if args.path:
        target = Path(args.path)
        saves = find_saves(target)
        if not saves:
            raise SystemExit("No ISeeYouForever.lua SavedVariables found at " + str(target))
        for save in saves:
            meta = export_save(save, wiki)
            if meta:
                results.append(meta)
    write_root_index(wiki)
    if args.path and not results:
        raise SystemExit("Found SavedVariables, but none contained character events.")
    for meta in results:
        print(
            "%s - %s: %d events (%d new), recording from level %s -> %s"
            % (meta["name"], meta["realm"], meta["events"], meta["added"], meta["start_level"], meta["folder"])
        )
    if not results:
        print("Wrote " + str(wiki / "SCHEMA.md"))


if __name__ == "__main__":
    main()
