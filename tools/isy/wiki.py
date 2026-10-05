import shutil

from isy.format import copper_text, day_key, duration_text, iso, yq
from isy.model import stamp_levels
from isy.parse import field, flt, num, read_meta
from isy.schema import schema_markdown

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
        "reported_level": None,
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
        "ids": set(),
        "xp": [],
        "seen": 0,
    })


def add_mob_meta(mobs, mob_name, level, classification, creature_type, zone, npc_id="", count=True):
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
    if npc_id:
        mob["ids"].add(str(npc_id))
    if count:
        mob["seen"] += 1


def ensure_quest(quests, quest_id, title):
    quest = quests.setdefault(quest_id, {
        "title": title or ("Quest " + quest_id),
        "accepts": [],
        "turnins": [],
        "abandons": 0,
        "progress": [],
        "seen": [],
        "ready": [],
        "zone": "",
        "level": "",
        "giver": "",
        "giver_id": "",
        "turnin_npc": "",
        "turnin_npc_id": "",
        "reward_item": "",
        "preexisting": False,
    })
    if title:
        quest["title"] = title
    return quest


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


def _slugify_file(text):
    from isy.format import slugify
    return slugify(text)


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
        if not zone_name:
            return
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

    def zone_after(index):
        session_id = events[index]["session"]
        for later in events[index + 1:]:
            if later["session"] != session_id:
                return ""
            if later["kind"] == "zone" and field(later, 0):
                return field(later, 0)
            if later["kind"] == "route" and field(later, 3):
                return field(later, 3)
            if later["kind"] in ("fight_start", "death") and field(later, 0):
                return field(later, 0)
        return ""

    for index, event in enumerate(events):
        last_t = event["t"]
        session = session_for(event)
        session["last"] = event["t"]
        if "anchor" not in session:
            session["anchor"] = event["t"]
        kind = event["kind"]

        if kind == "session_start":
            session["start"] = event["t"]
            session["level_start"] = num(event, 0)
            enter_zone(field(event, 1) or zone_after(index), event["t"])
        elif kind == "session_end":
            session["end"] = event["t"]
            reported = num(event, 0)
            session["reported_level"] = reported
            session["level_end"] = max(session["level_end"] or 0, reported)
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
                add_mob_meta(
                    mobs, mob_name, field(event, 5), field(event, 6), field(event, 7),
                    zone_name, field(event, 9), False,
                )
                ensure_mob(mobs, mob_name)["xp"].append(amount)
        elif kind == "level":
            level = num(event, 0)
            session["level_end"] = max(session["level_end"] or 0, level)
            session["levels"].append((event["t"], level))
        elif kind == "quest_accept":
            quest = ensure_quest(quests, field(event, 0), field(event, 1))
            quest["accepts"].append(event["t"])
            quest["zone"] = field(event, 3) or quest["zone"]
            quest["level"] = field(event, 2) or quest["level"]
            quest["giver"] = field(event, 7) or quest["giver"]
            quest["giver_id"] = field(event, 8) or quest["giver_id"]
        elif kind == "quest_seen":
            quest = ensure_quest(quests, field(event, 0), field(event, 1))
            quest["seen"].append(event["t"])
            quest["preexisting"] = True
            quest["zone"] = field(event, 3) or quest["zone"]
            quest["level"] = field(event, 2) or quest["level"]
        elif kind == "quest_progress":
            quest = ensure_quest(quests, field(event, 0), field(event, 1))
            quest["progress"].append(field(event, 2) + " " + field(event, 3) + "/" + field(event, 4))
        elif kind == "quest_ready":
            quest = ensure_quest(quests, field(event, 0), field(event, 1))
            quest["ready"].append(event["t"])
            quest["zone"] = field(event, 3) or quest["zone"]
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
            quest["turnin_npc"] = field(event, 11) or quest["turnin_npc"]
            quest["turnin_npc_id"] = field(event, 12) or quest["turnin_npc_id"]
            quest["reward_item"] = field(event, 13) or quest["reward_item"]
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
                "npc_id": field(event, 8),
                "t": event["t"],
            }
            add_mob_meta(
                mobs, field(event, 4), field(event, 5), field(event, 6), field(event, 7),
                field(event, 0), field(event, 8),
            )
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
            add_mob_meta(
                mobs, field(event, 0), field(event, 1), field(event, 2), field(event, 3),
                field(event, 4), field(event, 9),
            )
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
        filename = _slugify_file(quest_id + "-" + quest["title"]) + ".md"
        quest_files[quest_id] = filename
        turnin = quest["turnins"][-1] if quest["turnins"] else None
        early_accepts = [when for when in quest["accepts"] if not turnin or when < turnin["t"]]
        late_accepts = [when for when in quest["accepts"] if turnin and when >= turnin["t"]]
        duration = turnin["duration"] if turnin else 0
        if not duration and early_accepts and turnin:
            duration = max(0, turnin["t"] - early_accepts[0])
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
        if quest["preexisting"]:
            lines.append("- Already in the quest log when recording started.")
        if quest["seen"]:
            lines.append("- Seen: " + iso(quest["seen"][0]))
        if early_accepts:
            lines.append("- Accepted: " + iso(early_accepts[0]))
        elif late_accepts and turnin:
            lines.append("- Already in progress at the turn-in. The accept line was logged as the quest log updated.")
        if quest["giver"]:
            giver = quest["giver"]
            if quest["giver_id"]:
                giver += " (" + quest["giver_id"] + ")"
            lines.append("- Giver: " + giver)
        if quest["ready"]:
            lines.append("- Objectives finished: " + iso(quest["ready"][0]))
        if turnin:
            lines.append("- Turned in: " + iso(turnin["t"]))
            lines.append("- Reward: " + str(turnin["xp"]) + " XP, " + copper_text(turnin["copper"]))
            if quest["turnin_npc"]:
                npc = quest["turnin_npc"]
                if quest["turnin_npc_id"]:
                    npc += " (" + quest["turnin_npc_id"] + ")"
                lines.append("- Turned in to: " + npc)
            if quest["reward_item"]:
                lines.append("- Chosen reward item: " + quest["reward_item"])
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
        filename = _slugify_file(mob_name) + ".md"
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
        if mob["ids"]:
            lines.append("- NPC id: " + ", ".join(sorted(mob["ids"])))
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
        filename = _slugify_file(zone_name) + ".md"
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
        filename = _slugify_file(str(session_id) + "-" + zone_name + "-" + str(map_id)) + ".md"
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
        if session["reported_level"] and session["reported_level"] != session["level_end"]:
            lines.append(
                "- Recorded session end said level "
                + str(session["reported_level"])
                + ". The level events in this session reached "
                + str(session["level_end"])
                + "."
            )
            lines.append("")
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

    return {
        "name": name,
        "realm": realm,
        "start_level": start_level or 0,
        "started": iso(started) if started else "",
        "events": len(events),
    }


def _identity_fields(events, guid, class_token, race, faction):
    for event in events:
        if event["kind"] != "character":
            continue
        named = event.get("named") or {}
        guid = guid or named.get("guid") or ""
        class_token = class_token or named.get("class") or ""
        race = race or named.get("race") or ""
        faction = faction or named.get("faction") or ""
        break
    return guid, class_token, race, faction


def rebuild_character(folder, realm, name, events, guid="", class_token="", race="", faction=""):
    for sub in ("sessions", "quests", "mobs", "zones", "routes", "levels"):
        path = folder / sub
        if path.exists():
            shutil.rmtree(path)
    stamp_levels(events)
    guid, class_token, race, faction = _identity_fields(events, guid, class_token, race, faction)
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
    ]
    if guid:
        lines.append("guid: " + yq(guid))
    if class_token:
        lines.append("class: " + yq(class_token))
    if race:
        lines.append("race: " + yq(race))
    if faction:
        lines.append("faction: " + yq(faction))
    lines.extend([
        "start_level: " + str(start_level or 0),
        "started: " + yq(iso(started) if started else ""),
        "---",
        "",
        "# " + name + " - " + realm,
        "",
    ])
    if class_token or race or faction:
        detail = ", ".join(part for part in (class_token, race, faction) if part)
        lines.append(detail + ".")
        lines.append("")
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
        "guid": guid,
        "start_level": start_level or 0,
        "started": iso(started) if started else "",
        "events": len(events),
    }


def write_schema(wiki):
    wiki.mkdir(parents=True, exist_ok=True)
    (wiki / "SCHEMA.md").write_text(schema_markdown(), encoding="utf-8")


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
