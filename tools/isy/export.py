"""Read SavedVariables or an existing wiki log and publish every derived view."""

import argparse
from pathlib import Path

from isy.check import collect_issues, write_check
from isy.model import derive, identity_from_events, prepare_events
from isy.parse import (
    align_folder,
    append_logs,
    character_slug,
    event_ids,
    extract_events,
    find_saves,
    identity_from_path,
    load_events,
    move_folder,
    parse_event,
)
from isy.schema import name_fields
from isy.store import write_jsonl, write_schema_json, write_sqlite
from isy.wiki import rebuild_character, write_root_index, write_schema


def data_root_for(wiki):
    return wiki.parent / "data"


def publish(folder, realm, name, events):
    prepare_events(events)
    realm, name, guid, class_token, race, faction = identity_from_events(events, realm, name)
    meta = rebuild_character(folder, realm, name, events, guid, class_token, race, faction)
    model = derive(folder.name, realm, name, guid, class_token, race, faction, events)
    issues = collect_issues(events)
    data_root = data_root_for(folder.parent.parent)
    write_schema_json(data_root)
    character_data = data_root / "characters" / folder.name
    write_jsonl(character_data / "events.jsonl", events)
    write_check(character_data / "check.md", realm, name, issues)
    write_sqlite(data_root, model)
    meta["issues"] = len(issues)
    meta["folder"] = str(folder)
    meta["data"] = str(character_data)
    return meta


def _identity_from_lines(raw_lines, path):
    realm, name = identity_from_path(path) if path is not None else ("Unknown", "Unknown")
    guid = ""
    for line in raw_lines:
        event = parse_event(line)
        if not event:
            continue
        name_fields(event)
        if event["kind"] == "session_start":
            named = event["named"]
            if named.get("name") and named["name"] != "this character":
                name = named["name"]
            if named.get("realm"):
                realm = named["realm"]
        elif event["kind"] == "character" and event["named"].get("guid"):
            guid = event["named"]["guid"]
    return realm, name, guid


def export_save(lua_path, wiki):
    text = lua_path.read_text(encoding="utf-8")
    if "ISYF_Char" not in text:
        return None
    raw_lines = extract_events(text)
    if not raw_lines:
        return None
    realm, name, guid = _identity_from_lines(raw_lines, lua_path)
    folder = align_folder(wiki, realm, name, guid, event_ids(raw_lines))
    folder.mkdir(parents=True, exist_ok=True)
    added = append_logs(folder, realm, name, raw_lines)
    events = load_events(folder / "log")
    meta = publish(folder, realm, name, events)
    meta["added"] = added
    return meta


def rebuild_logged(wiki):
    root = wiki / "characters"
    results = []
    if not root.exists():
        return results
    folders = [path for path in root.iterdir() if path.is_dir() and (path / "log").exists()]
    for folder in folders:
        events = load_events(folder / "log")
        if not events:
            continue
        prepare_events(events)
        realm, name, guid, _class_token, _race, _faction = identity_from_events(events, "Unknown", folder.name)
        desired = character_slug(realm, name)
        if folder.name != desired:
            target = folder.parent / desired
            if not target.exists():
                folder = move_folder(folder, target)
        meta = publish(folder, realm, name, events)
        meta["added"] = 0
        results.append(meta)
    return results


def main():
    parser = argparse.ArgumentParser(description="Build the I see you forever markdown wiki.")
    parser.add_argument("path", nargs="?", help="SavedVariables file or a folder to search")
    parser.add_argument("--out", default="", help="Wiki directory. Defaults to ./wiki next to the addon repo.")
    args = parser.parse_args()
    wiki = Path(args.out) if args.out else Path(__file__).resolve().parent.parent.parent / "wiki"
    write_schema(wiki)
    write_schema_json(data_root_for(wiki))
    results = []
    exported = set()
    if args.path:
        target = Path(args.path)
        saves = find_saves(target)
        if not saves:
            raise SystemExit("No ISeeYouForever.lua SavedVariables found at " + str(target))
        for save in saves:
            meta = export_save(save, wiki)
            if meta:
                results.append(meta)
                exported.add(Path(meta["folder"]).resolve())
    for meta in rebuild_logged(wiki):
        if Path(meta["folder"]).resolve() in exported:
            continue
        results.append(meta)
    write_root_index(wiki)
    if args.path and not results:
        raise SystemExit("Found SavedVariables, but none contained character events.")
    for meta in results:
        print(
            "%s - %s: %d events (%d new), %d issues -> %s"
            % (
                meta["name"],
                meta["realm"],
                meta["events"],
                meta.get("added", 0),
                meta.get("issues", 0),
                meta["folder"],
            )
        )
    if not results:
        print("Wrote " + str(wiki / "SCHEMA.md"))
