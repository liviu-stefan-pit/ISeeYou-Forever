---
type: schema
---

# I see you forever wiki

This wiki is rebuilt from append-only logs. Raw lines live in each character's `log/` folder. Compiled pages are derived and can be deleted; the next export restores them.

Tracking starts when the addon first loads on that character. A level 20 character has no record of levels 1-19.

## Layout

- `index.md` lists characters.
- `characters/<Realm>__<Name>/index.md` is the character page.
- `log/YYYY-MM-DD.md` is the immutable source for that day.
- `sessions/`, `quests/`, `mobs/`, `zones/`, and `routes/` are compiled per character.

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
Session: `type`, `id`, `character`, `realm`, `started`, `ended`, `level_start`, `level_end`, `xp`, `copper_in`, `copper_out`, `seconds`.
Quest: `type`, `id`, `title`, `zone`, `level`, `xp`, `copper`, `duration_seconds`.
Mob: `type`, `name`, `classification`, `creature_type`, `level_min`, `level_max`, `xp_samples`, `xp_average`.
Zone: `type`, `name`, `seconds`, `xp`, `deaths`, `quests`.
Route: `type`, `session`, `zone`, `map`, `points`.
Log: `type`, `character`, `realm`, `date`.
