"""One offline HTML page of charts, built from isy.sqlite."""

import json
import sqlite3

from isy.wiki import band_for

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>I see you forever</title>
<style>
:root { color-scheme: light; }
body { margin: 0; font: 15px/1.45 "Segoe UI", sans-serif; background: #f6f5f1; color: #1c1c1c; }
main { max-width: 980px; margin: 0 auto; padding: 28px 20px 64px; }
h1 { font-size: 28px; margin: 0 0 6px; }
h2 { font-size: 18px; margin: 28px 0 8px; }
p.note { color: #555; margin: 0 0 16px; }
label { font-weight: 600; }
select { font: inherit; padding: 4px 8px; margin-left: 8px; }
.card { background: #fff; border: 1px solid #e4e2da; border-radius: 8px; padding: 12px 14px; margin-top: 8px; }
svg.chart { width: 100%; height: auto; display: block; }
.row { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
.row span.name { width: 110px; flex: none; }
.row span.bar { flex: 1; height: 16px; background: #eee; display: flex; }
.row span.bar i { display: block; height: 100%; }
.row span.value { width: 140px; flex: none; text-align: right; color: #444; }
table { width: 100%; border-collapse: collapse; background: #fff; }
th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #eee; }
th { cursor: pointer; }
th.num, td.num { text-align: right; }
.empty { color: #666; }
</style>
</head>
<body>
<main>
<h1>I see you forever</h1>
<p class="note">Charts from the journal database. This page works offline.</p>
<p><label for="who">Character</label><select id="who"></select></p>
<h2>Level over time</h2>
<div class="card" id="level"></div>
<h2>Experience per hour by level</h2>
<div class="card" id="rate"></div>
<h2>Time spent by chapter</h2>
<div class="card" id="time"></div>
<h2>Gold by source</h2>
<div class="card" id="gold"></div>
<h2>Deaths by killer</h2>
<div class="card" id="deaths"></div>
<h2>Quest efficiency</h2>
<div class="card" id="quests"></div>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
var DATA = JSON.parse(document.getElementById("data").textContent);
var STATES = ["dead", "combat", "taxi", "npc", "afk", "moving", "rest", "idle"];
var STATE_COLOR = {
  dead: "#c0392b", combat: "#d35400", taxi: "#8e44ad", npc: "#2980b9",
  afk: "#7f8c8d", moving: "#1e8449", rest: "#148f77", idle: "#b0b0aa"
};
var who = document.getElementById("who");
var sortKey = "perMin";
var sortDir = -1;

function esc(text) {
  return String(text == null ? "" : text).replace(/[&<>"]/g, function (ch) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch];
  });
}

function pick(list) {
  var slug = who.value;
  return list.filter(function (row) { return row.character === slug; });
}

function hours(seconds) {
  var h = Math.floor(seconds / 3600);
  var m = Math.floor((seconds % 3600) / 60);
  if (h) return h + "h " + m + "m";
  return m + "m";
}

function copper(value) {
  var sign = value < 0 ? "-" : "";
  value = Math.abs(Math.round(value));
  var gold = Math.floor(value / 10000);
  var silver = Math.floor((value % 10000) / 100);
  var coins = value % 100;
  if (gold) return sign + gold + "g " + silver + "s " + coins + "c";
  if (silver) return sign + silver + "s " + coins + "c";
  return sign + coins + "c";
}

function empty(node, text) {
  node.innerHTML = '<p class="empty">' + text + "</p>";
}

function svgEl(name) {
  return document.createElementNS("http://www.w3.org/2000/svg", name);
}

function drawLevel() {
  var node = document.getElementById("level");
  var rows = pick(DATA.levels).slice().sort(function (a, b) { return a.level - b.level; });
  if (!rows.length) { empty(node, "No levels recorded."); return; }
  var played = 0;
  var points = rows.map(function (row) {
    played += row.seconds || 0;
    return { x: played / 3600, y: row.level };
  });
  var width = 720, height = 260, pad = 36;
  var maxX = Math.max(points[points.length - 1].x, 0.01);
  var minY = points[0].y;
  var maxY = points[points.length - 1].y;
  if (maxY === minY) maxY = minY + 1;
  function px(hour) { return pad + (hour / maxX) * (width - pad * 2); }
  function py(level) { return height - pad - ((level - minY) / (maxY - minY)) * (height - pad * 2); }
  var svg = svgEl("svg");
  svg.setAttribute("viewBox", "0 0 " + width + " " + height);
  svg.setAttribute("class", "chart");
  var axis = svgEl("path");
  axis.setAttribute("d", "M" + pad + " " + pad + " V" + (height - pad) + " H" + (width - pad));
  axis.setAttribute("fill", "none");
  axis.setAttribute("stroke", "#ccc");
  svg.appendChild(axis);
  var d = points.map(function (point, index) {
    return (index ? "L" : "M") + px(point.x).toFixed(1) + " " + py(point.y).toFixed(1);
  }).join(" ");
  var line = svgEl("path");
  line.setAttribute("d", d);
  line.setAttribute("fill", "none");
  line.setAttribute("stroke", "#2f6f8f");
  line.setAttribute("stroke-width", "2");
  svg.appendChild(line);
  node.innerHTML = "";
  node.appendChild(svg);
}

function drawRate() {
  var node = document.getElementById("rate");
  var rows = pick(DATA.levels).filter(function (row) { return row.seconds > 0; });
  if (!rows.length) { empty(node, "No experience rate yet."); return; }
  var max = 0;
  rows.forEach(function (row) {
    row.rate = row.xp / row.seconds * 3600;
    if (row.rate > max) max = row.rate;
  });
  node.innerHTML = "";
  rows.forEach(function (row) {
    var line = document.createElement("div");
    line.className = "row";
    var width = max ? Math.round(row.rate / max * 100) : 0;
    line.innerHTML = '<span class="name">Level ' + row.level + '</span><span class="bar"><i style="width:' + width + '%;background:#2f6f8f"></i></span><span class="value">' + Math.round(row.rate).toLocaleString() + "/hr</span>";
    node.appendChild(line);
  });
}

function drawTime() {
  var node = document.getElementById("time");
  var rows = pick(DATA.segments);
  if (!rows.length) { empty(node, "No time recorded."); return; }
  var bands = {};
  var order = [];
  rows.forEach(function (row) {
    if (!bands[row.band]) {
      bands[row.band] = {};
      order.push(row.band);
    }
    bands[row.band][row.state] = (bands[row.band][row.state] || 0) + row.seconds;
  });
  order.sort();
  node.innerHTML = "";
  order.forEach(function (band) {
    var totals = bands[band];
    var sum = 0;
    STATES.forEach(function (state) { sum += totals[state] || 0; });
    var bar = "";
    STATES.forEach(function (state) {
      var seconds = totals[state] || 0;
      if (!seconds || !sum) return;
      bar += '<i title="' + state + " " + hours(seconds) + '" style="width:' + (seconds / sum * 100) + "%;background:" + STATE_COLOR[state] + '"></i>';
    });
    var line = document.createElement("div");
    line.className = "row";
    line.innerHTML = '<span class="name">' + esc(band) + '</span><span class="bar">' + bar + '</span><span class="value">' + hours(sum) + "</span>";
    node.appendChild(line);
  });
  var key = document.createElement("p");
  key.className = "note";
  key.textContent = STATES.join(", ");
  node.appendChild(key);
}

function drawGold() {
  var node = document.getElementById("gold");
  var rows = pick(DATA.money);
  if (!rows.length) { empty(node, "No money recorded."); return; }
  var max = 1;
  rows.forEach(function (row) { max = Math.max(max, row.copper_in, row.copper_out); });
  rows.sort(function (a, b) { return (b.copper_in + b.copper_out) - (a.copper_in + a.copper_out); });
  node.innerHTML = "";
  rows.forEach(function (row) {
    var line = document.createElement("div");
    line.className = "row";
    var bigger = Math.max(row.copper_in, row.copper_out);
    var width = Math.round(bigger / max * 100);
    var color = row.copper_in >= row.copper_out ? "#1e8449" : "#c0392b";
    line.innerHTML = '<span class="name">' + esc(row.source) + '</span><span class="bar"><i style="width:' + width + '%;background:' + color + '"></i></span><span class="value">in ' + copper(row.copper_in) + " / out " + copper(row.copper_out) + "</span>";
    node.appendChild(line);
  });
}

function drawDeaths() {
  var node = document.getElementById("deaths");
  var rows = pick(DATA.deaths);
  if (!rows.length) { empty(node, "No deaths recorded."); return; }
  var max = 1;
  rows.forEach(function (row) { if (row.count > max) max = row.count; });
  rows.sort(function (a, b) { return b.count - a.count; });
  node.innerHTML = "";
  rows.forEach(function (row) {
    var line = document.createElement("div");
    line.className = "row";
    line.innerHTML = '<span class="name">' + esc(row.killer) + '</span><span class="bar"><i style="width:' + Math.round(row.count / max * 100) + '%;background:#c0392b"></i></span><span class="value">' + row.count + "</span>";
    node.appendChild(line);
  });
}

function questRows() {
  return pick(DATA.quests).map(function (row) {
    var copy = {
      title: row.title, zone: row.zone, xp: row.xp, duration: row.duration, copper: row.copper,
      perMin: row.duration ? row.xp / (row.duration / 60) : 0
    };
    return copy;
  });
}

function drawQuests() {
  var node = document.getElementById("quests");
  var rows = questRows();
  if (!rows.length) { empty(node, "No turned-in quests lasted 30 seconds or more."); return; }
  rows.sort(function (a, b) {
    var left = a[sortKey], right = b[sortKey];
    if (typeof left === "string") return left.localeCompare(right) * sortDir;
    return (left - right) * sortDir;
  });
  var headers = [
    ["title", "Quest"], ["zone", "Zone"], ["xp", "XP"], ["duration", "Time"], ["perMin", "XP/min"], ["copper", "Gold"]
  ];
  var html = "<table><thead><tr>";
  headers.forEach(function (header) {
    var mark = header[0] === sortKey ? (sortDir < 0 ? " \\u2193" : " \\u2191") : "";
    var cls = header[0] === "title" || header[0] === "zone" ? "" : " num";
    html += '<th class="' + cls.trim() + '" data-key="' + header[0] + '">' + header[1] + mark + "</th>";
  });
  html += "</tr></thead><tbody>";
  rows.forEach(function (row) {
    html += "<tr><td>" + esc(row.title) + "</td><td>" + esc(row.zone) + "</td><td class=\\"num\\">" + row.xp +
      '</td><td class="num">' + hours(row.duration) + '</td><td class="num">' + Math.round(row.perMin) +
      '</td><td class="num">' + copper(row.copper) + "</td></tr>";
  });
  html += "</tbody></table>";
  node.innerHTML = html;
  var heads = node.querySelectorAll("th");
  for (var i = 0; i < heads.length; i++) {
    heads[i].addEventListener("click", function () {
      var key = this.getAttribute("data-key");
      sortDir = key === sortKey ? -sortDir : (key === "title" || key === "zone" ? 1 : -1);
      sortKey = key;
      drawQuests();
    });
  }
}

function draw() {
  drawLevel();
  drawRate();
  drawTime();
  drawGold();
  drawDeaths();
  drawQuests();
}

DATA.characters.forEach(function (row) {
  var option = document.createElement("option");
  option.value = row.slug;
  option.textContent = row.name + (row.realm ? " - " + row.realm : "");
  who.appendChild(option);
});
if (!DATA.characters.length) {
  who.parentNode.innerHTML = '<p class="empty">No characters in the database yet.</p>';
} else {
  who.addEventListener("change", draw);
  draw();
}
</script>
</body>
</html>
"""


def _rows(conn, sql, params=()):
    return [dict(row) for row in conn.execute(sql, params)]


def _columns(conn, table):
    return {row[1] for row in conn.execute("PRAGMA table_info(%s)" % table)}


def load_payload(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        characters = _rows(conn, "SELECT slug, name, realm, class FROM characters ORDER BY name, realm")
        levels = _rows(
            conn,
            'SELECT "character" AS character, level, seconds, xp FROM levels ORDER BY level',
        )
        sessions = {
            (row["character"], row["id"]): row["level_start"] or 1
            for row in conn.execute('SELECT "character" AS character, id, level_start FROM sessions')
        }
        grouped = {}
        if "segments" in _tables(conn):
            for row in conn.execute(
                'SELECT "character" AS character, session, state, SUM(seconds) AS seconds '
                'FROM segments GROUP BY "character", session, state'
            ):
                level = sessions.get((row["character"], row["session"]), 1) or 1
                band = "%02d-%02d" % band_for(level)
                key = (row["character"], band, row["state"] or "idle")
                grouped[key] = grouped.get(key, 0) + (row["seconds"] or 0)
        segments = [
            {"character": key[0], "band": key[1], "state": key[2], "seconds": seconds}
            for key, seconds in grouped.items()
        ]
        money = []
        if "money" in _tables(conn):
            money = _rows(
                conn,
                """
                SELECT "character" AS character, COALESCE(NULLIF(source, ''), 'unknown') AS source,
                    SUM(CASE WHEN delta > 0 THEN delta ELSE 0 END) AS copper_in,
                    SUM(CASE WHEN delta < 0 THEN -delta ELSE 0 END) AS copper_out
                FROM money GROUP BY "character", source
                """,
            )
        deaths = []
        if "deaths" in _tables(conn):
            killer = "killer_name" if "killer_name" in _columns(conn, "deaths") else "''"
            deaths = _rows(
                conn,
                """
                SELECT "character" AS character,
                    COALESCE(NULLIF(%s, ''), 'unknown') AS killer,
                    COUNT(*) AS count
                FROM deaths GROUP BY "character", killer
                """ % killer,
            )
        quests = []
        if "quests" in _tables(conn):
            quests = _rows(
                conn,
                """
                SELECT "character" AS character, title, zone, xp, duration, copper
                FROM quests
                WHERE duration >= 30 AND turnin_t IS NOT NULL
                """,
            )
        return {
            "characters": characters,
            "levels": levels,
            "segments": segments,
            "money": money,
            "deaths": deaths,
            "quests": quests,
        }
    finally:
        conn.close()


def _tables(conn):
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def write_dashboard(wiki, data_root):
    wiki.mkdir(parents=True, exist_ok=True)
    path = data_root / "isy.sqlite"
    if path.exists():
        try:
            payload = load_payload(path)
        except sqlite3.Error:
            payload = {"characters": [], "levels": [], "segments": [], "money": [], "deaths": [], "quests": []}
    else:
        payload = {"characters": [], "levels": [], "segments": [], "money": [], "deaths": [], "quests": []}
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    (wiki / "dashboard.html").write_text(PAGE.replace("__DATA__", data), encoding="utf-8")
    return wiki / "dashboard.html"
