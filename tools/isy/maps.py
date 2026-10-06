"""Plain SVG route drawings. Coordinates are map fractions times 10000."""

SIZE = 1000


def _esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _xy(x_value, y_value):
    try:
        x_value = float(x_value) / 10.0
        y_value = float(y_value) / 10.0
    except (TypeError, ValueError):
        return None
    if x_value < 0:
        x_value = 0
    elif x_value > SIZE:
        x_value = SIZE
    if y_value < 0:
        y_value = 0
    elif y_value > SIZE:
        y_value = SIZE
    return x_value, y_value


def render_svg(paths, markers):
    """Draw route polylines and event markers on a light grid.

    paths: lists of (x, y) in stored units (fraction times 10000).
    markers: dicts with kind, x, y, and label. Kinds are death, accept, turnin, kill.
    """
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">' % (SIZE, SIZE, SIZE, SIZE),
        '<rect width="%d" height="%d" fill="#f7f7f4"/>' % (SIZE, SIZE),
    ]
    for step in range(0, SIZE + 1, 100):
        parts.append(
            '<line x1="%d" y1="0" x2="%d" y2="%d" stroke="#e4e4de" stroke-width="1"/>' % (step, step, SIZE)
        )
        parts.append(
            '<line x1="0" y1="%d" x2="%d" y2="%d" stroke="#e4e4de" stroke-width="1"/>' % (step, SIZE, step)
        )
    for path in paths:
        points = []
        for x_value, y_value in path:
            point = _xy(x_value, y_value)
            if point:
                points.append(point)
        if len(points) >= 2:
            drawn = " ".join("%.1f,%.1f" % point for point in points)
            parts.append(
                '<polyline fill="none" stroke="#2f6f8f" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" points="%s"/>'
                % drawn
            )
        elif len(points) == 1:
            x_value, y_value = points[0]
            parts.append(
                '<circle cx="%.1f" cy="%.1f" r="3" fill="#2f6f8f"><title>Route sample</title></circle>'
                % (x_value, y_value)
            )
    for marker in markers:
        point = _xy(marker.get("x"), marker.get("y"))
        if not point:
            continue
        x_value, y_value = point
        label = _esc(marker.get("label") or "")
        kind = marker.get("kind") or ""
        if kind == "death":
            parts.append(
                '<g stroke="#c0392b" stroke-width="2">'
                '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>'
                "<title>%s</title></g>"
                % (
                    x_value - 6, y_value - 6, x_value + 6, y_value + 6,
                    x_value - 6, y_value + 6, x_value + 6, y_value - 6,
                    label,
                )
            )
        elif kind == "accept":
            parts.append(
                '<text x="%.1f" y="%.1f" text-anchor="middle" font-size="22" font-family="sans-serif" fill="#9a7b12">!<title>%s</title></text>'
                % (x_value, y_value + 6, label)
            )
        elif kind == "turnin":
            parts.append(
                '<text x="%.1f" y="%.1f" text-anchor="middle" font-size="22" font-family="sans-serif" fill="#2e7d32">?<title>%s</title></text>'
                % (x_value, y_value + 6, label)
            )
        else:
            parts.append(
                '<circle cx="%.1f" cy="%.1f" r="4" fill="#555555"><title>%s</title></circle>'
                % (x_value, y_value, label)
            )
    parts.append("</svg>")
    parts.append("")
    return "\n".join(parts)
