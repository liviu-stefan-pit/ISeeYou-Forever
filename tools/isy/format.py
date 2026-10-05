from datetime import datetime, timezone


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
