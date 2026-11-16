---
name: release-gate
description: Checks a release ZIP or folder before it ships: key-shaped strings, stray files, machine paths, missing README/LICENSE/CHANGELOG, version mismatches. Use when the user asks, for example, "check my release", "is this zip safe to ship", "run release gate", "출시 전에 ZIP 점검해 줘".
---

# release-gate

Checks a release ZIP or folder before it ships: key-shaped strings, stray files, machine paths, missing README/LICENSE/CHANGELOG, version mismatches. A small Python tool shipped in this plugin: standard library only, nothing to install, runs locally.

## Run

Use `python` (Windows: `py -3` also works; macOS/Linux: `python3`). On Windows add `-X utf8` if the console shows broken characters.

    python "${CLAUDE_PLUGIN_ROOT}/releasegate.py" <file.zip or folder>
    python "${CLAUDE_PLUGIN_ROOT}/releasegate.py" <file.zip or folder> --strict

Run it from the user's project folder and pass the path they mean. If no path is given, ask which folder or file to check.

## Read the result

FAIL lines must be fixed before shipping; REVIEW lines need a human look; the Details block lists each file and line. Key values are never printed in full.

Show the tool's own output (shortened if long) and then a two- or three-line summary. Do not change the user's files unless they ask.
