# Changelog

## 1.0.0 - 2026-11-13

First release.

- `releasegate.py <zip or folder>`: reads the package in memory, writes nothing, runs nothing from it.
- To fix: key-shaped strings (value hidden), stray files, missing README, LICENSE or CHANGELOG, unsafe ZIP entry names.
- To review: key look-alikes, absolute paths, network code, archives inside the package.
- For a person to read: refund and warranty wording, price mentions.
- `--strict` makes "to review" items fail too; `--details N` sets how many lines are shown per group.
- `gate_patterns.py`: every pattern in one readable file, shared with Skill Install Gate.
- `make_sample.py`: builds a flawed sample package and a fixed one to try the tool on.
- 38 unit tests.
