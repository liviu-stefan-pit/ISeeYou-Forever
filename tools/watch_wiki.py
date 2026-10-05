#!/usr/bin/env python3
"""Update the wiki when WoW Forever writes the addon save.

The addon cannot write markdown. WoW writes ISeeYouForever.lua on logout
and /reload. This script watches that file and runs the exporter after the
write settles.

Leave it running while you play:

  py -3 tools/watch_wiki.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from export_wiki import export_save, find_saves, read_lua_string, write_root_index, write_schema

DEFAULT_WTF = Path(r"C:\Program Files (x86)\World of Warcraft\_classic_beta_\WTF")
DEFAULT_WIKI = Path(__file__).resolve().parent.parent / "wiki"
SETTLE_SECONDS = 3
POLL_SECONDS = 2


def snapshot(path):
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def collect(wtf):
    if not wtf.exists():
        return []
    return find_saves(wtf)


def wiki_path_from_saves(saves):
    marker = '["wikiPath"]'
    for save in saves:
        try:
            text = save.read_text(encoding="utf-8")
        except OSError:
            continue
        at = text.find(marker)
        if at < 0:
            continue
        equals = text.find("=", at + len(marker))
        if equals < 0:
            continue
        quote = text.find('"', equals)
        if quote < 0:
            continue
        value, _ = read_lua_string(text, quote)
        value = value.strip()
        if value:
            return Path(value)
    return None


def export_all(saves, wiki):
    write_schema(wiki)
    results = []
    for save in saves:
        try:
            meta = export_save(save, wiki)
        except OSError as err:
            print("Skipped %s (%s)" % (save, err))
            continue
        if meta:
            results.append(meta)
            print(
                "%s - %s: %d events (%d new)"
                % (meta["name"], meta["realm"], meta["events"], meta["added"]),
                flush=True,
            )
    write_root_index(wiki)
    if not results:
        print("Save changed, but it has no character events yet.", flush=True)
    return results


def run_once(wtf, wiki):
    saves = collect(wtf)
    if not saves:
        print("No addon save found under %s" % wtf, flush=True)
        print("Log out of the game once so WoW can write it.", flush=True)
        return 1
    chosen = wiki_path_from_saves(saves) or wiki
    print("Writing wiki to %s" % chosen, flush=True)
    export_all(saves, chosen)
    return 0


def main():
    once = "--once" in sys.argv[1:]
    args = [arg for arg in sys.argv[1:] if arg != "--once"]
    wtf = Path(args[0]) if args else DEFAULT_WTF
    wiki = Path(args[1]) if len(args) > 1 else DEFAULT_WIKI
    if once:
        raise SystemExit(run_once(wtf, wiki))
    print("Watching %s" % wtf, flush=True)
    print("Wiki defaults to %s until you paste a folder in /isy." % wiki, flush=True)
    print("The wiki updates a few seconds after you log out or /reload. Close this window to stop.", flush=True)

    seen = {}
    pending = False
    pending_at = 0.0

    while True:
        saves = collect(wtf)
        changed = False
        live = {}
        for save in saves:
            state = snapshot(save)
            live[save] = state
            if state is not None and seen.get(save) != state:
                changed = True
        if changed:
            pending = True
            pending_at = time.time()
            seen.update(live)
        elif pending and (time.time() - pending_at) >= SETTLE_SECONDS:
            pending = False
            chosen = wiki_path_from_saves(saves) or wiki
            print("Writing wiki to %s" % chosen, flush=True)
            export_all(saves, chosen)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
