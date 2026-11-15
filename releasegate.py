#!/usr/bin/env python3
"""Release Gate: a pre-release check for a ZIP or a folder you are about to ship.

It looks for:
  * key-shaped strings (the value is never printed)
  * files that got in by accident (__pycache__, .env, .DS_Store, ...)
  * a missing README, LICENSE or CHANGELOG
  * unsafe entry names in a ZIP
  * absolute paths from your own machine
  * code that makes network requests
  * refund, warranty and price wording, listed for a person to read

Release Gate is a check aid. It finds the patterns listed in gate_patterns.py
and nothing else. A result with nothing to fix is not a statement that the
package is safe, legal or compliant.

Standard library only. Makes no network requests. Reads the target, writes
nothing, runs nothing from it.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import gate_patterns as gp  # noqa: E402

__version__ = "1.0.0"

MAX_FILE_BYTES = 2 * 1024 * 1024
DETAIL_LIMIT = 20

FAIL, REVIEW, HUMAN = "FAIL", "REVIEW", "HUMAN"

# (category, level, what the row means)
CATEGORIES = [
    ("key-shaped strings", FAIL, "a well-known key format; the value is hidden"),
    ("stray files", FAIL, "files and folders that are usually left in by accident"),
    ("required files", FAIL, "README, LICENSE and CHANGELOG at the top of the package"),
    ("unsafe entry names", FAIL, "ZIP entries with absolute or parent paths"),
    ("key look-alikes", REVIEW, "may be a secret, may be a hash or a sample"),
    ("absolute paths", REVIEW, "paths from the machine the package was made on"),
    ("network code", REVIEW, "code that can make network requests"),
    ("archives inside", REVIEW, "archives in the package; their contents are not scanned"),
    ("refund and warranty words", HUMAN, "wording a person should read before selling"),
    ("price mentions", HUMAN, "prices written in the package"),
]
LEVEL_OF = dict((name, level) for name, level, _ in CATEGORIES)
MEANING_OF = dict((name, meaning) for name, _, meaning in CATEGORIES)

DISCLAIMER = ("Release Gate is a pre-release check aid. It looks for the patterns above and "
              "nothing else. A result with nothing to fix does not mean the package is safe "
              "or compliant.")

_ARCHIVE_SUFFIXES = (".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".whl", ".jar")
_DOC_NAMES = {
    "README": re.compile(r"^readme(\.[a-z0-9]+)?$", re.IGNORECASE),
    "LICENSE": re.compile(r"^(licen[sc]e|copying)([.-][a-z0-9.-]+)?$", re.IGNORECASE),
    "CHANGELOG": re.compile(r"^(changelog|changes|history|release[-_]?notes)(\.[a-z0-9]+)?$",
                            re.IGNORECASE),
}
_HASH_FILE_RE = re.compile(r"sha\d*|sums|checksum|\.lock$|integrity", re.IGNORECASE)


class TargetError(Exception):
    pass


class Entry(object):
    __slots__ = ("name", "size", "data", "is_dir", "note")

    def __init__(self, name, size=0, data=None, is_dir=False, note=""):
        self.name = name
        self.size = size
        self.data = data
        self.is_dir = is_dir
        self.note = note


class Target(object):
    __slots__ = ("kind", "label", "entries")

    def __init__(self, kind, label, entries):
        self.kind = kind
        self.label = label
        self.entries = entries

    @property
    def files(self):
        return [entry for entry in self.entries if not entry.is_dir]


# ---------------------------------------------------------------- loading

def harden_streams():
    """Never crash on a console that cannot print a character (cp949, cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="backslashreplace")
        except Exception:
            pass


def _load_folder(path):
    entries = []
    for folder, dirs, files in os.walk(path):
        keep = []
        for name in sorted(dirs):
            if name in gp.STRAY_DIRS:
                relative = os.path.relpath(os.path.join(folder, name), path).replace("\\", "/")
                entries.append(Entry(relative + "/", is_dir=True))
            else:
                keep.append(name)
        dirs[:] = keep
        for name in sorted(files):
            full = os.path.join(folder, name)
            relative = os.path.relpath(full, path).replace("\\", "/")
            try:
                size = os.path.getsize(full)
            except OSError:
                entries.append(Entry(relative, note="could not be read"))
                continue
            if size > MAX_FILE_BYTES:
                entries.append(Entry(relative, size, note="larger than 2 MB, not scanned"))
                continue
            try:
                with open(full, "rb") as handle:
                    entries.append(Entry(relative, size, handle.read()))
            except OSError:
                entries.append(Entry(relative, size, note="could not be read"))
    return entries


def _load_zip(path):
    entries = []
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise TargetError("not a readable ZIP file (%s)" % exc.__class__.__name__)
    with archive:
        for info in archive.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/"):
                entries.append(Entry(name, is_dir=True))
                continue
            if info.file_size > MAX_FILE_BYTES:
                entries.append(Entry(name, info.file_size, note="larger than 2 MB, not scanned"))
                continue
            try:
                entries.append(Entry(name, info.file_size, archive.read(info)))
            except Exception:
                entries.append(Entry(name, info.file_size, note="could not be read"))
    return entries


def load_target(path):
    """Read a folder or a ZIP into memory. Nothing is extracted to disk or run."""
    label = os.path.basename(os.path.abspath(path).rstrip("/\\")) or "target"
    if os.path.isdir(path):
        return Target("folder", label, _load_folder(path))
    if os.path.isfile(path):
        if not zipfile.is_zipfile(path):
            raise TargetError("the file is not a ZIP archive")
        return Target("zip", label, _load_zip(path))
    raise TargetError("no such file or folder")


def decode(data):
    """Text of a file, or None when it looks binary."""
    if data is None:
        return None
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    if b"\x00" in data[:8192]:
        return None
    return data.decode("utf-8-sig", errors="replace")


def package_root(target):
    """"name/" when every entry of a ZIP sits in one top folder, else ""."""
    if target.kind != "zip":
        return ""
    tops = set(entry.name.split("/", 1)[0] for entry in target.entries if "/" in entry.name)
    loose = [entry for entry in target.entries if "/" not in entry.name]
    if len(tops) == 1 and not loose:
        return tops.pop() + "/"
    return ""


# ---------------------------------------------------------------- checking

def finding(category, file, line=0, text=""):
    return {"level": LEVEL_OF[category], "category": category, "file": file,
            "line": line, "text": text}


def _shorten(text, width=90):
    text = " ".join(text.split())
    return text if len(text) <= width else text[:width - 3] + "..."


def check_names(target):
    found = []
    for entry in target.entries:
        name = entry.name
        if target.kind == "zip":
            parts = name.split("/")
            if name.startswith("/") or ".." in parts or re.match(r"^[A-Za-z]:", name):
                found.append(finding("unsafe entry names", name, text="absolute or parent path"))
        reason = gp.is_stray(name)
        if reason:
            found.append(finding("stray files", name, text=reason))
        elif not entry.is_dir and name.lower().endswith(_ARCHIVE_SUFFIXES):
            found.append(finding("archives inside", name, text="%d bytes" % entry.size))
    return found


def check_required(target):
    root = package_root(target)
    top = [entry.name[len(root):] for entry in target.files
           if entry.name.startswith(root) and "/" not in entry.name[len(root):]]
    missing = [label for label, pattern in _DOC_NAMES.items()
               if not any(pattern.match(name) for name in top)]
    return [finding("required files", root or ".", text="missing: " + label) for label in missing]


def check_contents(target):
    found = []
    for entry in target.files:
        if gp.is_stray(entry.name):
            continue
        text = decode(entry.data)
        if text is None:
            continue
        name = entry.name
        base = name.split("/")[-1]
        hash_file = bool(_HASH_FILE_RE.search(base))
        for line, ident, label, masked, definite in gp.find_keys(text):
            if ident == "long-hex" and hash_file:
                continue
            category = "key-shaped strings" if definite else "key look-alikes"
            found.append(finding(category, name, line, "%s  %s" % (label, masked)))
        for line, ident, label, matched in gp.find(gp.ABSOLUTE_PATHS, text):
            found.append(finding("absolute paths", name, line, _shorten(matched)))
        if gp.is_code(name):
            for line, ident, label, matched in gp.find(gp.NETWORK, text):
                found.append(finding("network code", name, line,
                                     "%s: %s" % (label, _shorten(matched.strip(), 60))))
        if not _DOC_NAMES["LICENSE"].match(base):
            for match in gp.REFUND_WORDS.finditer(text):
                found.append(finding("refund and warranty words", name,
                                     gp.line_of(text, match.start()), match.group()))
        if not gp.is_code(name):
            for match in gp.PRICE.finditer(text):
                found.append(finding("price mentions", name,
                                     gp.line_of(text, match.start()), match.group().strip()))
    return found


def inspect(target):
    """Run every check. Returns the findings, in category order."""
    found = check_names(target) + check_required(target) + check_contents(target)
    order = dict((name, index) for index, (name, _, _) in enumerate(CATEGORIES))
    found.sort(key=lambda item: (order[item["category"]], item["file"], item["line"]))
    return found


def not_scanned(target):
    """Files whose contents were not looked at, with the reason."""
    skipped = []
    for entry in target.files:
        if entry.note:
            skipped.append((entry.name, entry.note))
        elif decode(entry.data) is None:
            skipped.append((entry.name, "binary, contents not scanned"))
    return skipped


def counts_by_level(findings):
    counts = {FAIL: 0, REVIEW: 0, HUMAN: 0}
    for item in findings:
        counts[item["level"]] += 1
    return counts


def verdict(findings, strict=False):
    """(result line, exit code)."""
    counts = counts_by_level(findings)
    tail = "%d to fix, %d to review, %d for a person to read" % (
        counts[FAIL], counts[REVIEW], counts[HUMAN])
    if counts[FAIL]:
        return "NOT READY: " + tail, 1
    if strict and counts[REVIEW]:
        return "NOT READY (--strict): " + tail, 1
    return "NOTHING TO FIX: " + tail, 0


def where(item):
    return "%s:%d" % (item["file"], item["line"]) if item["line"] else item["file"]


def render_text(target, findings, strict=False, detail_limit=DETAIL_LIMIT, title=None,
                categories=None):
    categories = categories or CATEGORIES
    skipped = not_scanned(target)
    lines = [title or "Release Gate %s  (patterns %s)" % (__version__, gp.PATTERNS_VERSION),
             "Target: %s  (%s, %d files, %d not scanned)"
             % (target.label, target.kind, len(target.files), len(skipped)), ""]
    for name, level, meaning in categories:
        count = sum(1 for item in findings if item["category"] == name)
        lines.append("  %-7s %-27s %3d   %s" % (level if count else "ok", name, count, meaning))
    if findings:
        lines.extend(["", "Details"])
        for name, level, meaning in categories:
            group = [item for item in findings if item["category"] == name]
            if not group:
                continue
            lines.append("  %s" % name)
            for item in group[:detail_limit]:
                lines.append("    %s  %s" % (where(item), item["text"]))
            if len(group) > detail_limit:
                lines.append("    ... and %d more" % (len(group) - detail_limit))
    if skipped:
        lines.extend(["", "Not scanned"])
        for name, note in skipped[:detail_limit]:
            lines.append("    %s  %s" % (name, note))
        if len(skipped) > detail_limit:
            lines.append("    ... and %d more" % (len(skipped) - detail_limit))
    lines.extend(["", "Result: " + verdict(findings, strict)[0], DISCLAIMER])
    return "\n".join(lines)


# --------------------------------------------------------------------- cli

def build_parser():
    parser = argparse.ArgumentParser(
        prog="releasegate.py",
        description="Pre-release check for a ZIP or a folder. Reads the target; "
                    "writes nothing and runs nothing from it.",
    )
    parser.add_argument("target", help="the ZIP file or folder you are about to ship")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 when there are items to review, too")
    parser.add_argument("--details", type=int, default=DETAIL_LIMIT, metavar="N",
                        help="lines of detail per group (default: %d)" % DETAIL_LIMIT)
    parser.add_argument("--version", action="version", version="release-gate " + __version__)
    return parser


def main(argv=None):
    harden_streams()
    args = build_parser().parse_args(argv)
    try:
        target = load_target(args.target)
    except TargetError as exc:
        sys.stderr.write("release-gate: %s\n" % exc)
        return 2
    findings = inspect(target)
    print(render_text(target, findings, args.strict, max(1, args.details)))
    prices = sum(1 for item in findings if item["category"] == "price mentions")
    if prices:
        print("%d price mention(s) found. Checking them against your listing price is in "
              "Release Gate Pro." % prices)
    return verdict(findings, args.strict)[1]


if __name__ == "__main__":
    sys.exit(main())
