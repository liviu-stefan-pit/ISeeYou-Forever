"""Anomalies a later guide or dashboard should not have to guess about."""

from isy.format import iso, yq
from isy.schema import KINDS

GAP_SECONDS = 300


def collect_issues(events):
    issues = []
    issues.extend(_kind_issues(events))
    issues.extend(_level_issues(events))
    issues.extend(_xp_issues(events))
    issues.extend(_quest_issues(events))
    issues.extend(_gap_issues(events))
    return issues


def _kind_issues(events):
    issues = []
    for event in events:
        spec = KINDS.get(event["kind"])
        if spec is None:
            issues.append("event %d: unknown kind %s" % (event["id"], event["kind"]))
            continue
        schema = event.get("schema") or 1
        for name, _typ, since, required in spec:
            if since > schema or not required:
                continue
            if not event["present"].get(name):
                issues.append(
                    "event %d %s: %s is empty" % (event["id"], event["kind"], name)
                )
        if event.get("extra"):
            issues.append(
                "event %d %s: %d unexpected fields"
                % (event["id"], event["kind"], len(event["extra"]))
            )
    return issues


def _level_issues(events):
    issues = []
    last = None
    sessions = {}
    for event in events:
        sid = event["session"]
        row = sessions.setdefault(sid, {"max_level": 0, "end_level": None, "end_id": None})
        row["max_level"] = max(row["max_level"], event.get("char_level") or 0)
        kind = event["kind"]
        named = event["named"]
        if kind == "session_start":
            level = named.get("level") or 0
            if last is not None and level and level < last:
                issues.append(
                    "event %d: level went from %d back to %d" % (event["id"], last, level)
                )
            if level:
                last = level
        elif kind == "level":
            level = named.get("level") or 0
            if last is not None and level and level < last:
                issues.append(
                    "event %d: level went from %d back to %d" % (event["id"], last, level)
                )
            if level:
                last = level
                row["max_level"] = max(row["max_level"], level)
        elif kind == "session_end":
            row["end_level"] = named.get("level") or 0
            row["end_id"] = event["id"]
    for sid, row in sessions.items():
        if row["end_level"] is None:
            continue
        if row["max_level"] and row["end_level"] < row["max_level"]:
            issues.append(
                "session %d event %d: session_end level %d is below level %d reached in the session"
                % (sid, row["end_id"], row["end_level"], row["max_level"])
            )
    return issues


def _xp_issues(events):
    issues = []
    totals = {}
    reported = {}
    for event in events:
        sid = event["session"]
        if event["kind"] == "xp":
            totals[sid] = totals.get(sid, 0) + (event["named"].get("amount") or 0)
        elif event["kind"] == "session_end" and event["present"].get("xp"):
            reported[sid] = (event["id"], event["named"].get("xp") or 0)
    for sid, (event_id, value) in reported.items():
        gained = totals.get(sid, 0)
        if gained != value:
            issues.append(
                "session %d event %d: xp events sum to %d but session_end says %d"
                % (sid, event_id, gained, value)
            )
    starts = [event for event in events if event["kind"] == "session_start"]
    for previous, nxt in zip(starts, starts[1:]):
        if (previous["named"].get("level") or 0) != (nxt["named"].get("level") or 0):
            continue
        gained = 0
        leveled = False
        for event in events:
            if (event["t"], event["id"]) <= (previous["t"], previous["id"]):
                continue
            if (event["t"], event["id"]) >= (nxt["t"], nxt["id"]):
                break
            if event["kind"] == "level":
                leveled = True
            elif event["kind"] == "xp":
                gained += event["named"].get("amount") or 0
        if leveled:
            continue
        delta = (nxt["named"].get("xp") or 0) - (previous["named"].get("xp") or 0)
        if delta != gained:
            issues.append(
                "sessions %d and %d: experience bar moved %d but xp events sum to %d"
                % (previous["session"], nxt["session"], delta, gained)
            )
    return issues


def _quest_issues(events):
    quests = {}
    for event in events:
        if event["kind"] not in ("quest_accept", "quest_seen", "quest_turnin"):
            continue
        quest_id = str(event["named"].get("quest_id") or "")
        row = quests.setdefault(quest_id, {"title": "", "accept": None, "seen": None, "turnin": None})
        title = event["named"].get("title") or ""
        if title:
            row["title"] = title
        if event["kind"] == "quest_accept" and row["accept"] is None:
            row["accept"] = event
        elif event["kind"] == "quest_seen" and row["seen"] is None:
            row["seen"] = event
        elif event["kind"] == "quest_turnin" and row["turnin"] is None:
            row["turnin"] = event
    issues = []
    for quest_id, row in sorted(quests.items()):
        turnin = row["turnin"]
        accept = row["accept"]
        if turnin is None:
            continue
        label = row["title"] or quest_id
        if accept is not None and (turnin["t"], turnin["id"]) < (accept["t"], accept["id"]):
            issues.append(
                "quest %s %s: turned in at event %d before accept at event %d"
                % (quest_id, label, turnin["id"], accept["id"])
            )
        elif accept is None and row["seen"] is None:
            issues.append(
                "quest %s %s: turned in at event %d with no accept" % (quest_id, label, turnin["id"])
            )
    return issues


def _gap_issues(events):
    issues = []
    for index in range(len(events) - 1):
        current = events[index]
        nxt = events[index + 1]
        if current["session"] != nxt["session"]:
            continue
        delta = nxt["t"] - current["t"]
        if delta > GAP_SECONDS:
            issues.append(
                "session %d: %d second gap between event %d and event %d (%s to %s)"
                % (current["session"], delta, current["id"], nxt["id"], iso(current["t"]), iso(nxt["t"]))
            )
    return issues


def write_check(path, realm, name, issues):
    lines = [
        "---",
        "type: check",
        "character: " + yq(name),
        "realm: " + yq(realm),
        "issues: " + str(len(issues)),
        "---",
        "",
        "# Check",
        "",
    ]
    if not issues:
        lines.append("No anomalies.")
    else:
        for issue in issues:
            lines.append("- " + issue)
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
