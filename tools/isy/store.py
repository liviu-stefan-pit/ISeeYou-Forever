"""Named JSONL plus one SQLite database. Both are rebuilt from the log."""

import json
import sqlite3

from isy.schema import schema_document

DB_VERSION = 1

TABLES = (
    "events",
    "sessions",
    "levels",
    "quests",
    "quest_points",
    "kills",
    "fights",
    "deaths",
    "segments",
    "npcs",
    "money",
    "items",
    "route_points",
)


def write_schema_json(data_root):
    data_root.mkdir(parents=True, exist_ok=True)
    text = json.dumps(schema_document(), indent=2, sort_keys=True)
    (data_root / "SCHEMA.json").write_text(text + "\n", encoding="utf-8")


def write_jsonl(path, events):
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for event in events:
        record = dict(event.get("named") or {})
        record["id"] = event["id"]
        record["t"] = event["t"]
        record["session"] = event["session"]
        record["kind"] = event["kind"]
        record["schema"] = event.get("schema") or 1
        record["char_level"] = event.get("char_level") or 0
        record["char_zone"] = event.get("char_zone") or ""
        lines.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        conn = sqlite3.connect(path)
        version = None
        try:
            row = conn.execute("SELECT value FROM meta WHERE key = 'version'").fetchone()
            if row:
                version = int(row[0])
        except sqlite3.Error:
            version = None
        if version != DB_VERSION:
            conn.close()
            path.unlink()
        else:
            return conn
    conn = sqlite3.connect(path)
    _create(conn)
    return conn


def _create(conn):
    conn.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE characters (
            slug TEXT PRIMARY KEY,
            name TEXT,
            realm TEXT,
            guid TEXT,
            class TEXT,
            race TEXT,
            faction TEXT,
            start_level INTEGER,
            started INTEGER
        );
        CREATE TABLE events (
            "character" TEXT NOT NULL,
            id INTEGER NOT NULL,
            t INTEGER,
            session INTEGER,
            kind TEXT,
            schema INTEGER,
            data TEXT,
            char_level INTEGER,
            char_zone TEXT,
            PRIMARY KEY ("character", id)
        );
        CREATE TABLE sessions (
            "character" TEXT NOT NULL,
            id INTEGER NOT NULL,
            start_t INTEGER,
            end_t INTEGER,
            level_start INTEGER,
            level_end INTEGER,
            reported_level INTEGER,
            xp INTEGER,
            copper_in INTEGER,
            copper_out INTEGER,
            seconds INTEGER,
            schema INTEGER,
            PRIMARY KEY ("character", id)
        );
        CREATE TABLE levels (
            "character" TEXT NOT NULL,
            level INTEGER NOT NULL,
            seconds INTEGER,
            xp INTEGER,
            PRIMARY KEY ("character", level)
        );
        CREATE TABLE quests (
            "character" TEXT NOT NULL,
            quest_id TEXT NOT NULL,
            title TEXT,
            zone TEXT,
            level INTEGER,
            xp INTEGER,
            copper INTEGER,
            accept_t INTEGER,
            turnin_t INTEGER,
            ready_t INTEGER,
            seen_t INTEGER,
            duration INTEGER,
            giver_name TEXT,
            giver_id TEXT,
            turnin_name TEXT,
            turnin_id TEXT,
            reward_item TEXT,
            preexisting INTEGER,
            abandons INTEGER,
            PRIMARY KEY ("character", quest_id)
        );
        CREATE TABLE quest_points (
            "character" TEXT NOT NULL,
            quest_id TEXT,
            kind TEXT,
            t INTEGER,
            session INTEGER,
            zone TEXT,
            map INTEGER,
            x INTEGER,
            y INTEGER,
            objective TEXT,
            done INTEGER,
            required INTEGER
        );
        CREATE TABLE kills (
            "character" TEXT NOT NULL,
            t INTEGER,
            session INTEGER,
            name TEXT,
            npc_id TEXT,
            level INTEGER,
            zone TEXT,
            map INTEGER,
            x INTEGER,
            y INTEGER,
            xp INTEGER,
            inferred INTEGER
        );
        CREATE TABLE fights (
            "character" TEXT NOT NULL,
            session INTEGER,
            start_t INTEGER,
            end_t INTEGER,
            mob_name TEXT,
            npc_id TEXT,
            level INTEGER,
            zone TEXT,
            map INTEGER,
            x INTEGER,
            y INTEGER,
            duration REAL,
            xp INTEGER,
            named_ticks INTEGER,
            ticks INTEGER
        );
        CREATE TABLE deaths (
            "character" TEXT NOT NULL,
            t INTEGER,
            session INTEGER,
            zone TEXT,
            map INTEGER,
            x INTEGER,
            y INTEGER,
            level INTEGER
        );
        CREATE TABLE segments (
            "character" TEXT NOT NULL,
            session INTEGER,
            state TEXT,
            start_t INTEGER,
            end_t INTEGER,
            seconds INTEGER,
            zone TEXT
        );
        CREATE TABLE npcs (
            "character" TEXT NOT NULL,
            t INTEGER,
            session INTEGER,
            kind TEXT,
            name TEXT,
            npc_id TEXT,
            zone TEXT,
            map INTEGER,
            x INTEGER,
            y INTEGER,
            duration INTEGER
        );
        CREATE TABLE money (
            "character" TEXT NOT NULL,
            t INTEGER,
            session INTEGER,
            delta INTEGER,
            balance INTEGER,
            source TEXT,
            detail TEXT
        );
        CREATE TABLE items (
            "character" TEXT NOT NULL,
            t INTEGER,
            session INTEGER,
            item_id TEXT,
            count INTEGER,
            quality INTEGER,
            source TEXT,
            raw TEXT
        );
        CREATE TABLE route_points (
            "character" TEXT NOT NULL,
            t INTEGER,
            session INTEGER,
            map INTEGER,
            x INTEGER,
            y INTEGER,
            zone TEXT
        );
        CREATE INDEX idx_events_kind ON events ("character", kind);
        CREATE INDEX idx_segments_state ON segments ("character", state);
        """
    )
    conn.execute("INSERT INTO meta (key, value) VALUES ('version', ?)", (str(DB_VERSION),))
    conn.commit()


def _clear(conn, slug):
    conn.execute("DELETE FROM characters WHERE slug = ?", (slug,))
    for table in TABLES:
        conn.execute('DELETE FROM %s WHERE "character" = ?' % table, (slug,))


def write_sqlite(data_root, model):
    conn = _connect(data_root / "isy.sqlite")
    slug = model["slug"]
    try:
        _clear(conn, slug)
        conn.execute(
            """
            INSERT INTO characters (slug, name, realm, guid, class, race, faction, start_level, started)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                slug,
                model["name"],
                model["realm"],
                model["guid"],
                model["class_token"],
                model["race"],
                model["faction"],
                model["start_level"],
                model["started"],
            ),
        )
        conn.executemany(
            """
            INSERT INTO events ("character", id, t, session, kind, schema, data, char_level, char_zone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    slug,
                    event["id"],
                    event["t"],
                    event["session"],
                    event["kind"],
                    event.get("schema") or 1,
                    json.dumps(event.get("named") or {}, ensure_ascii=False, sort_keys=True),
                    event.get("char_level") or 0,
                    event.get("char_zone") or "",
                )
                for event in model["events"]
            ],
        )
        conn.executemany(
            """
            INSERT INTO sessions (
                "character", id, start_t, end_t, level_start, level_end, reported_level,
                xp, copper_in, copper_out, seconds, schema
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    slug, row["id"], row["start_t"], row["end_t"], row["level_start"], row["level_end"],
                    row["reported_level"], row["xp"], row["copper_in"], row["copper_out"],
                    row["seconds"], row["schema"],
                )
                for row in model["sessions"]
            ],
        )
        conn.executemany(
            'INSERT INTO levels ("character", level, seconds, xp) VALUES (?, ?, ?, ?)',
            [(slug, row["level"], row["seconds"], row["xp"]) for row in model["levels"]],
        )
        conn.executemany(
            """
            INSERT INTO quests (
                "character", quest_id, title, zone, level, xp, copper, accept_t, turnin_t, ready_t,
                seen_t, duration, giver_name, giver_id, turnin_name, turnin_id, reward_item,
                preexisting, abandons
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    slug, row["quest_id"], row["title"], row["zone"], row["level"], row["xp"], row["copper"],
                    row["accept_t"], row["turnin_t"], row["ready_t"], row["seen_t"], row["duration"],
                    row["giver_name"], row["giver_id"], row["turnin_name"], row["turnin_id"],
                    row["reward_item"], row["preexisting"], row["abandons"],
                )
                for row in model["quests"]
            ],
        )
        conn.executemany(
            """
            INSERT INTO quest_points (
                "character", quest_id, kind, t, session, zone, map, x, y, objective, done, required
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    slug, row["quest_id"], row["kind"], row["t"], row["session"], row["zone"],
                    row["map"], row["x"], row["y"], row["objective"], row["done"], row["required"],
                )
                for row in model["quest_points"]
            ],
        )
        conn.executemany(
            """
            INSERT INTO kills (
                "character", t, session, name, npc_id, level, zone, map, x, y, xp, inferred
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    slug, row["t"], row["session"], row["name"], row["npc_id"], row["level"],
                    row["zone"], row["map"], row["x"], row["y"], row["xp"], row["inferred"],
                )
                for row in model["kills"]
            ],
        )
        conn.executemany(
            """
            INSERT INTO fights (
                "character", session, start_t, end_t, mob_name, npc_id, level, zone, map, x, y,
                duration, xp, named_ticks, ticks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    slug, row["session"], row["start_t"], row["end_t"], row["mob_name"], row["npc_id"],
                    row["level"], row["zone"], row["map"], row["x"], row["y"], row["duration"],
                    row["xp"], row["named_ticks"], row["ticks"],
                )
                for row in model["fights"]
            ],
        )
        conn.executemany(
            'INSERT INTO deaths ("character", t, session, zone, map, x, y, level) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            [
                (slug, row["t"], row["session"], row["zone"], row["map"], row["x"], row["y"], row["level"])
                for row in model["deaths"]
            ],
        )
        conn.executemany(
            """
            INSERT INTO segments ("character", session, state, start_t, end_t, seconds, zone)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (slug, row["session"], row["state"], row["start_t"], row["end_t"], row["seconds"], row["zone"])
                for row in model["segments"]
            ],
        )
        conn.executemany(
            """
            INSERT INTO npcs (
                "character", t, session, kind, name, npc_id, zone, map, x, y, duration
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    slug, row["t"], row["session"], row["kind"], row["name"], row["npc_id"],
                    row["zone"], row["map"], row["x"], row["y"], row["duration"],
                )
                for row in model["npcs"]
            ],
        )
        conn.executemany(
            'INSERT INTO money ("character", t, session, delta, balance, source, detail) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
                (slug, row["t"], row["session"], row["delta"], row["balance"], row["source"], row["detail"])
                for row in model["money"]
            ],
        )
        conn.executemany(
            """
            INSERT INTO items ("character", t, session, item_id, count, quality, source, raw)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (slug, row["t"], row["session"], row["item_id"], row["count"], row["quality"], row["source"], row["raw"])
                for row in model["items"]
            ],
        )
        conn.executemany(
            'INSERT INTO route_points ("character", t, session, map, x, y, zone) VALUES (?, ?, ?, ?, ?, ?, ?)',
            [
                (slug, row["t"], row["session"], row["map"], row["x"], row["y"], row["zone"])
                for row in model["route_points"]
            ],
        )
        conn.commit()
    finally:
        conn.close()
