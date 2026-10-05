#!/usr/bin/env python3
"""Compile ISeeYouForever SavedVariables into a per-character markdown wiki.

Recording starts at the level the character had when the addon loaded.
Each character gets a folder under wiki/characters/. Structured copies are
written to data/ next to the wiki: events.jsonl, isy.sqlite, and check.md.

Usage:
  python tools/export_wiki.py PATH [--out wiki]
  python tools/export_wiki.py --out wiki

PATH is a character SavedVariables file (ISeeYouForever.lua) or a folder
to search, such as WTF/Account. With no PATH, existing character logs are
rebuilt. This command leaves the game save in place. export-wiki.bat
clears it after a successful export.
"""

from isy.export import export_save, main
from isy.parse import find_saves, read_lua_string
from isy.wiki import write_root_index, write_schema

__all__ = [
    "export_save",
    "find_saves",
    "read_lua_string",
    "write_root_index",
    "write_schema",
    "main",
]

if __name__ == "__main__":
    main()
