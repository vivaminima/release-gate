#!/usr/bin/env python3
"""make_sample.py: build a small, deliberately flawed package to try Release Gate on.

Creates, next to this file:

  sample-out/acme-notes-1.0.0/      a package with typical pre-release mistakes
  sample-out/acme-notes-1.0.0.zip   the same package as a ZIP
  sample-out/acme-notes-1.0.1/      the same package with the mistakes fixed
  sample-out/acme-notes-1.0.1.zip
  sample-out/listing.txt            a pretend store listing (used by the Pro price check)

Everything in it is made up. The fake key, the fake paths and the fake wording
are joined from pieces at run time, so this file itself contains none of them.

Standard library only. Writes only inside sample-out/.
"""
from __future__ import annotations

import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sample-out")
ZIP_TIME = (2026, 1, 5, 9, 0, 0)


def j(*pieces):
    return "".join(pieces)


FAKE_KEY = j("s", "k-", "Zx81", "Qm4T", "vK9c", "Lw27", "HdN6", "yB3g", "R5aF", "pE0u")
MAC_PATH = j("/", "Users", "/sam/projects/acme-notes/notes.db")
WIN_PATH = j("C", ":", "\\", "work", "\\", "acme-notes", "\\", "notes.db")
OLD_PRICE = j("$", "12")
NEW_PRICE = j("$", "24")
PROMISE = j("30-day ", "money", "-back ", "guar", "antee")

LICENSE = """MIT License

Copyright (c) 2026 Acme Studio (a made-up company)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction. THE SOFTWARE IS PROVIDED "AS IS".
"""

NET_MODULE = j("url", "lib", ".request")
NET_IMPORT = j("imp", "ort ", NET_MODULE)
NET_OPEN = j(NET_MODULE, ".url", "open")
SYNC_URL = j("ht", "tps", "://sync.acme-notes.example/v1/push")

NOTES_PY_BAD = j('''"""acme-notes: keep short notes in a local file."""
import json
''', NET_IMPORT, '''

API_KEY = "''', FAKE_KEY, '''"
DEFAULT_DB = "''', MAC_PATH, '''"
BACKUP_DB = r"''', WIN_PATH, '''"


def sync(notes):
    request = ''', NET_MODULE, '''.Request("''', SYNC_URL, '''",
                                     data=json.dumps(notes).encode("utf-8"))
    return ''', NET_OPEN, '''(request).status


def add(notes, text):
    notes.append(text)
    return notes
''')

NOTES_PY_GOOD = '''"""acme-notes: keep short notes in a local file."""
import os

DEFAULT_DB = os.path.join(os.path.expanduser("~"), ".acme-notes", "notes.db")


def add(notes, text):
    notes.append(text)
    return notes
'''

README_BAD = j("""# acme-notes

Keep short notes in a local file.

Version 1.0.0. Price: """, OLD_PRICE, """ (launch price).

Comes with a """, PROMISE, """.

## Use

    python notes.py add "buy milk"
""")

README_GOOD = j("""# acme-notes

Keep short notes in a local file.

Version 1.0.1. Price: """, NEW_PRICE, """.

## Use

    python notes.py add "buy milk"
""")

CHANGELOG_GOOD = j("""# Changelog

## 1.0.1

- Removed the sync feature and the key that came with it.
- The notes file now lives in the user's home folder.
- Price is """, NEW_PRICE, """.

## 1.0.0

- First release.
""")

LISTING = j("""acme-notes 1.0.1
Keep short notes in a local file.
Price: """, NEW_PRICE, """
One download, one Python file.
""")


def write(base, relative, content):
    path = os.path.join(base, *relative.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if isinstance(content, bytes) else "w"
    if isinstance(content, bytes):
        with open(path, mode) as handle:
            handle.write(content)
    else:
        with open(path, mode, encoding="utf-8", newline="\n") as handle:
            handle.write(content)


def make_zip(folder):
    path = folder + ".zip"
    top = os.path.basename(folder)
    names = []
    for current, dirs, files in os.walk(folder):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(current, name)
            names.append((full, top + "/" + os.path.relpath(full, folder).replace("\\", "/")))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for full, name in sorted(names, key=lambda pair: pair[1]):
            info = zipfile.ZipInfo(name, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            with open(full, "rb") as handle:
                archive.writestr(info, handle.read())
    return path


def build(out=OUT):
    if os.path.isdir(out):
        shutil.rmtree(out)
    bad = os.path.join(out, "acme-notes-1.0.0")
    write(bad, "README.md", README_BAD)
    write(bad, "LICENSE", LICENSE)
    write(bad, "notes.py", NOTES_PY_BAD)
    write(bad, ".env", j("SYNC_", "SECRET=", FAKE_KEY, "\n"))
    write(bad, "__pycache__/notes.cpython-310.pyc", b"\x00\x00\x00\x00not real bytecode")
    write(bad, ".DS_Store", b"\x00\x00\x00\x01Bud1")

    good = os.path.join(out, "acme-notes-1.0.1")
    write(good, "README.md", README_GOOD)
    write(good, "LICENSE", LICENSE)
    write(good, "CHANGELOG.md", CHANGELOG_GOOD)
    write(good, "notes.py", NOTES_PY_GOOD)

    write(out, "listing.txt", LISTING)
    return [make_zip(bad), make_zip(good)]


def main():
    zips = build()
    print("Made the sample in sample-out/:")
    for path in zips:
        print("  %s" % os.path.relpath(path, HERE).replace("\\", "/"))
    print("  sample-out/listing.txt")
    print("Try: python releasegate.py sample-out/acme-notes-1.0.0.zip")
    return 0


if __name__ == "__main__":
    sys.exit(main())
