---
type: schema
schema: 3
---

# I see you forever wiki

This wiki is rebuilt from append-only logs. Raw lines live in each character's `log/` folder. Compiled pages are derived and can be deleted; the next export restores them.

Fields are append-only. New fields are added at the end of a kind and never reordered, so older logs still parse. `session_start` carries a `schema` field (3 for the current addon). Sessions without that field are schema 1.

Tracking starts when the addon first loads on that character. A level 20 character has no record of levels 1-19.

Stable ids, when the game provides them, are the player GUID, the NPC id (6th segment of a creature GUID), quest ids, and item ids. Names are labels.

## Layout

- `index.md` lists characters.
- `characters/<Realm>__<Name>/index.md` lists level chapters.
- `log/YYYY-MM-DD.md` is the immutable source for that day. It is not split.
- `levels/01-10/`, `levels/11-20/`, `levels/21-30/`, then five-level folders through `56-60/`. Each chapter has its own zones, quests, mobs, routes, and sessions.
- `data/SCHEMA.json` is this field list as JSON.
- `data/isy.sqlite` is one database for every character.
- `data/characters/<slug>/events.jsonl` is one named event per line.
- `data/characters/<slug>/check.md` lists anomalies.
- `dashboard.html` is one offline page of charts for every character.

## Event line

`id, unix time, session id, kind, fields...` separated by tabs. The log stores each line as `event: <line>`.

Coordinates are map fractions times 10000. Money is copper.

| Kind | Fields |
| --- | --- |
| session_start | level*, zone*, subzone, map, x, y, money, xp, xp_max, name*, realm, schema (v2) |
| session_end | level*, seconds, xp, copper_in, copper_out |
| played | total_seconds, level_seconds |
| xp | amount*, rested, level, source*, mob_name, mob_level, classification, creature_type, quest_id, npc_id (v2) |
| level | level* |
| quest_accept | quest_id*, title, level, zone, map, x, y, giver_name (v2), giver_id (v2) |
| quest_progress | quest_id*, title, objective, done, required, level (v2), zone (v2), map (v2), x (v2), y (v2) |
| quest_abandon | quest_id*, title, level |
| quest_turnin | quest_id*, title, xp, copper, level, zone, map, x, y, accept_unix, duration, npc_name (v2), npc_id (v2), reward_item (v2) |
| quest_seen | quest_id (v2)*, title (v2), level (v2), zone (v2), map (v2), x (v2), y (v2) |
| quest_ready | quest_id (v2)*, title (v2), level (v2), zone (v2), map (v2), x (v2), y (v2) |
| money | delta, balance, source, detail |
| route | map, x, y, zone |
| zone | zone*, subzone, map, x, y |
| fight_start | zone, map, x, y, mob_name, mob_level, classification, creature_type, npc_id (v2) |
| fight_end | duration, xp, zone, map, x, y, named, ticks |
| mob | name*, level, classification, creature_type, zone, map, x, y, context, npc_id (v2) |
| death | zone*, map, x, y, level, killer_name (v3), killer_id (v3), killer_level (v3), ability (v3), attackers (v3), damage (v3) |
| unghost | zone, map, x, y |
| alive | zone, map, x, y |
| loot | text*, item_id (v2), count (v2), quality (v2) |
| skill | text |
| rep | name, reaction, standing |
| bags | slots |
| bag_delta | changes (v2) |
| group | size |
| travel | method, origin, destination |
| character | guid (v2), class (v2), race (v2), faction (v2), sex (v2), level (v2), talents (v2), gear (v2), reason (v2) |
| gear | slot (v2), old_item (v2), new_item (v2) |
| npc | kind (v2)*, name (v2), npc_id (v2), zone (v2), map (v2), x (v2), y (v2) |
| npc_close | kind (v2), duration (v2) |
| bind | zone (v2), subzone (v2) |
| spell_learned | spell_id (v2), name (v2), level (v2) |
| taxi_start | origin (v2), destination (v2) |
| taxi_end | destination (v2), zone (v2), map (v2), x (v2), y (v2) |
| rest | resting (v2) |
| afk | afk (v2) |
| mount | mounted (v2) |
| kill | name (v2), npc_id (v2), level (v2), classification (v2), creature_type (v2), zone (v2), map (v2), x (v2), y (v2) |

A star marks a field that should not be empty. A suffix such as `(v2)` or `(v3)` is the schema that added the field. Older lines omit it.

Session experience totals come from `xp` events. Quest pages come from quest events. Money totals come from `money` events. A quest turn-in therefore appears once as experience, once as a quest reward, and once in the money ledger.

`bags` is a full inventory snapshot and replaces derived bag state. `bag_delta` is the change since the previous bag event, written as `itemId:+n` or `itemId:-n`.

Activity segments cover every second of a session: dead, combat, taxi, npc, afk, moving, rest, then idle. The first matching state wins.

## Page frontmatter

Character: `type`, `name`, `realm`, `guid`, `class`, `race`, `faction`, `start_level`, `started`.
Chapter: `type`, `levels`, `seconds`, `xp`, `copper_in`, `copper_out`, then `seconds_dead`, `seconds_combat`, `seconds_taxi`, `seconds_npc`, `seconds_afk`, `seconds_moving`, `seconds_rest`, `seconds_idle`.
Session: `type`, `id`, `character`, `realm`, `started`, `ended`, `level_start`, `level_end`, `xp`, `copper_in`, `copper_out`, `seconds`, then the same `seconds_*` activity keys as a chapter.
Quest: `type`, `id`, `title`, `zone`, `level`, `xp`, `copper`, `duration_seconds`.
Mob: `type`, `name`, `classification`, `creature_type`, `level_min`, `level_max`, `xp_samples`, `xp_average`.
Zone: `type`, `name`, `seconds`, `xp`, `deaths`, `quests`.
Route: `type`, `session`, `zone`, `map`, `points`.
Log: `type`, `character`, `realm`, `date`.
