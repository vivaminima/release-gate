"""Tests for releasegate.py and gate_patterns.py.

Run from the package folder:  python -m unittest discover -s tests -v

Fake keys and paths are joined from pieces at run time, so this file itself
holds no key-shaped string and no absolute path.
"""
import locale
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
SCRIPT = os.path.join(PACKAGE, "releasegate.py")
sys.path.insert(0, PACKAGE)

import gate_patterns as gp  # noqa: E402
import releasegate as rg  # noqa: E402


def j(*pieces):
    return "".join(pieces)


BODY = "Zx81Qm4TvK9cLw27HdN6yB3gR5aFpE0u"
SK_KEY = j("s", "k-", BODY)
AWS_KEY = j("AK", "IA", "Q7ZP4MX2LD9VB6TN")
GH_TOKEN = j("gh", "p_", BODY, "1234")
SLACK_TOKEN = j("xo", "xb-", "123456789012-", BODY[:20])
GOOGLE_KEY = j("AI", "za", BODY, "_-x")
PAY_KEY = j("s", "k_", "live_", BODY[:24])
PEM = j("-----BEGIN ", "RSA PRIVATE KEY", "-----")
JWT = j("ey", "J", BODY[:16], ".", "ey", "J", BODY[4:20], ".", BODY[:12])
MAC = j("/", "Users", "/sam/work/app.db")
LINUX = j("/", "home", "/sam/work/app.db")
WIN = j("C", ":", "\\", "Users", "\\", "sam", "\\", "app.db")
WIN_ESCAPED = j("D", ":", "\\\\", "work", "\\\\", "app.db")
WIN_SLASH = j("E", ":", "/", "work/app.db")
WEB = j("ht", "tps://example.com")


class Case(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="rg test "))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.pkg = os.path.join(self.root, "pkg")

    def write(self, name, content="x\n", base=None):
        path = os.path.join(base or self.pkg, *name.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if isinstance(content, bytes):
            with open(path, "wb") as handle:
                handle.write(content)
        else:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
        return path

    def clean_package(self):
        self.write("README.md", "# Tool\n")
        self.write("LICENSE", "MIT License\n")
        self.write("CHANGELOG.md", "# Changelog\n\n## 1.0.0\n")
        self.write("tool.py", "print('hello')\n")

    def zip_package(self, top="pkg-1.0.0", extra=()):
        path = os.path.join(self.root, top + ".zip")
        with zipfile.ZipFile(path, "w") as archive:
            for folder, dirs, files in os.walk(self.pkg):
                for name in files:
                    full = os.path.join(folder, name)
                    relative = os.path.relpath(full, self.pkg).replace("\\", "/")
                    archive.write(full, (top + "/" if top else "") + relative)
            for name, data in extra:
                archive.writestr(name, data)
        return path

    def findings(self, path=None):
        return rg.inspect(rg.load_target(path or self.pkg))

    def by_category(self, path=None):
        grouped = {}
        for item in self.findings(path):
            grouped.setdefault(item["category"], []).append(item)
        return grouped

    def run_script(self, args, env=None):
        environ = dict(os.environ)
        for name in ("PYTHONIOENCODING", "PYTHONUTF8"):
            environ.pop(name, None)
        if sys.flags.utf8_mode:
            environ["PYTHONUTF8"] = "1"
        environ.update(env or {})
        proc = subprocess.run([sys.executable, SCRIPT] + list(args), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=environ, cwd=self.root)
        encoding = environ.get("PYTHONIOENCODING") or locale.getpreferredencoding(False)
        return (proc.returncode, proc.stdout.decode(encoding, "replace"),
                proc.stderr.decode(encoding, "replace"))


class CleanPackage(Case):
    def test_folder_has_nothing_to_fix(self):
        self.clean_package()
        self.assertEqual(self.findings(), [])
        code, out, err = self.run_script([self.pkg])
        self.assertEqual(code, 0, out)
        self.assertIn("Result: NOTHING TO FIX: 0 to fix, 0 to review, 0 for a person to read", out)
        self.assertEqual(err, "")

    def test_zip_has_nothing_to_fix(self):
        self.clean_package()
        code, out, err = self.run_script([self.zip_package()])
        self.assertEqual(code, 0, out)
        self.assertIn("Target: pkg-1.0.0.zip  (zip, 4 files, 0 not scanned)", out)

    def test_result_never_claims_safety(self):
        self.clean_package()
        out = self.run_script([self.pkg])[1]
        self.assertIn("does not mean the package is safe or compliant", out)
        for word in ("PASS", "SAFE", "CLEAN", "APPROVED", "CERTIFIED"):
            self.assertNotIn(word, out.replace("is safe or compliant", ""))

    def test_no_end_line_without_a_real_number(self):
        self.clean_package()
        self.assertNotIn("Release Gate Pro", self.run_script([self.pkg])[1])


class Keys(Case):
    def test_each_known_format_is_found_and_hidden(self):
        self.clean_package()
        samples = [SK_KEY, AWS_KEY, GH_TOKEN, SLACK_TOKEN, GOOGLE_KEY, PAY_KEY, PEM, JWT]
        self.write("config.py", "".join("V%d = '%s'\n" % (i, s) for i, s in enumerate(samples)))
        found = self.by_category()["key-shaped strings"]
        self.assertEqual([item["line"] for item in found], list(range(1, len(samples) + 1)))
        code, out, err = self.run_script([self.pkg])
        self.assertEqual(code, 1)
        for secret in samples:
            self.assertNotIn(secret, out)
        self.assertNotIn(BODY, out)
        self.assertIn("config.py:1  API key (sk- prefix)  %s***(%d chars)"
                      % (SK_KEY[:4], len(SK_KEY)), out)

    def test_placeholders_are_not_reported(self):
        self.clean_package()
        self.write("README.md", "# Tool\nSet " + j("s", "k-") + "your-api-key-goes-here-123456\n"
                   "api_key = \"YOUR_API_KEY_GOES_HERE\"\ntoken: '<paste-your-token-here>'\n"
                   "password = \"xxxxxxxxxxxxxxxxxxxx\"\n")
        self.assertEqual(self.findings(), [])

    def test_assigned_secret_is_a_look_alike_and_hidden(self):
        self.clean_package()
        secret = BODY[:20]
        self.write("settings.json", '{"api_key": "%s", "name": "tool"}\n' % secret)
        found = self.by_category()
        self.assertNotIn("key-shaped strings", found)
        self.assertEqual(len(found["key look-alikes"]), 1)
        self.assertNotIn(secret, found["key look-alikes"][0]["text"])
        code, out, err = self.run_script([self.pkg])
        self.assertEqual(code, 0)
        self.assertNotIn(secret, out)
        self.assertEqual(self.run_script([self.pkg, "--strict"])[0], 1)

    def test_long_hex_is_a_look_alike_except_in_hash_files(self):
        self.clean_package()
        digest = "0123456789abcdef" * 4
        self.write("notes.txt", "build %s\n" % digest)
        self.write("SHA256SUMS.txt", "%s  tool.zip\n" % digest)
        found = self.by_category()["key look-alikes"]
        self.assertEqual([item["file"] for item in found], ["notes.txt"])

    def test_mask(self):
        self.assertEqual(gp.mask("abcdefghijklmnop"), "abcd***(16 chars)")
        self.assertEqual(gp.mask("short"), "sh***(5 chars)")


class StrayAndRequired(Case):
    def test_stray_files_in_a_folder(self):
        self.clean_package()
        for name in (".env", ".DS_Store", "Thumbs.db", "tool.py.bak", "notes.swp",
                     "cert.pem", ".env.local", "__pycache__/tool.cpython-310.pyc",
                     ".git/config", "node_modules/x/index.js", ".claude/settings.json",
                     "sub/.idea/workspace.xml"):
            self.write(name, "x")
        self.write(".env.example", "KEY=\n")
        found = sorted(item["file"] for item in self.by_category()["stray files"])
        self.assertEqual(found, sorted([
            ".env", ".DS_Store", "Thumbs.db", "tool.py.bak", "notes.swp", "cert.pem",
            ".env.local", "__pycache__/", ".git/", "node_modules/", ".claude/", "sub/.idea/"]))

    def test_stray_files_in_a_zip(self):
        self.clean_package()
        self.write("__pycache__/tool.cpython-310.pyc", b"\x00\x01")
        self.write(".env", "A=1\n")
        found = self.by_category(self.zip_package())["stray files"]
        self.assertEqual(sorted(item["file"] for item in found),
                         ["pkg-1.0.0/.env", "pkg-1.0.0/__pycache__/tool.cpython-310.pyc"])

    def test_contents_of_stray_files_are_not_scanned(self):
        self.clean_package()
        self.write(".env", "TOKEN=%s\n" % SK_KEY)
        found = self.by_category()
        self.assertNotIn("key-shaped strings", found)
        self.assertEqual(len(found["stray files"]), 1)

    def test_missing_docs(self):
        self.write("tool.py", "print('x')\n")
        self.write("docs/README.md", "nested does not count\n")
        missing = [item["text"] for item in self.by_category()["required files"]]
        self.assertEqual(missing, ["missing: README", "missing: LICENSE", "missing: CHANGELOG"])

    def test_doc_name_variants(self):
        self.write("readme.txt")
        self.write("LICENCE.md")
        self.write("HISTORY.md")
        self.assertEqual(self.findings(), [])
        shutil.rmtree(self.pkg)
        self.write("README")
        self.write("COPYING")
        self.write("CHANGES.rst")
        self.assertEqual(self.findings(), [])

    def test_zip_without_a_top_folder(self):
        self.clean_package()
        self.assertEqual(self.findings(self.zip_package(top="")), [])

    def test_zip_docs_must_be_in_the_top_folder(self):
        self.write("tool.py", "x = 1\n")
        self.write("docs/README.md")
        self.write("docs/LICENSE")
        self.write("docs/CHANGELOG.md")
        found = self.by_category(self.zip_package())["required files"]
        self.assertEqual(len(found), 3)
        self.assertEqual(found[0]["file"], "pkg-1.0.0/")

    def test_unsafe_zip_entry_names(self):
        self.clean_package()
        path = self.zip_package(extra=[("../escape.txt", "x"), ("/abs.txt", "x"),
                                       ("pkg-1.0.0/a/../../b.txt", "x")])
        found = [item["file"] for item in self.by_category(path)["unsafe entry names"]]
        self.assertEqual(sorted(found), ["../escape.txt", "/abs.txt", "pkg-1.0.0/a/../../b.txt"])

    def test_archive_inside(self):
        self.clean_package()
        self.write("vendor/lib.zip", b"PK\x03\x04")
        found = self.by_category()["archives inside"]
        self.assertEqual(found[0]["file"], "vendor/lib.zip")


class PathsAndNetwork(Case):
    def test_absolute_paths(self):
        self.clean_package()
        self.write("notes.md", "\n".join([MAC, LINUX, WIN, WIN_ESCAPED, WIN_SLASH, ""]))
        found = self.by_category()["absolute paths"]
        self.assertEqual([item["line"] for item in found], [1, 2, 3, 4, 5])

    def test_things_that_are_not_absolute_paths(self):
        self.clean_package()
        self.write("notes.md", "\n".join([
            "See %s/x and %s/y" % (WEB, j("ht", "tp://localhost:8000")),
            "Ratio a:b, time 10:30, key:value, C: drive",
            "relative/path/file.txt and ./local and ~/home-relative",
            "The pattern [A-Z]:\\ is described here, and a regex such as \\d\\d:\\d\\d too.",
            "",
        ]))
        self.assertNotIn("absolute paths", self.by_category())

    def test_network_code_is_found_in_code_files_only(self):
        self.clean_package()
        python = ("import " + "urllib.request\nfrom " + "requests import get\n"
                  "import os\nx = " + "urlopen" + "('u')\n")
        self.write("net.py", python)
        self.write("docs.md", python)
        self.write("app.js", "const r = await " + "fetch" + "('/api');\n"
                   "const a = " + "require" + "('axios');\n")
        self.write("get.sh", "cu" + "rl -s " + WEB + "/install > x\n")
        self.write("get.ps1", "Invoke-" + "WebRequest -Uri $u\n")
        found = self.by_category()["network code"]
        self.assertEqual(sorted(set(item["file"] for item in found)),
                         ["app.js", "get.ps1", "get.sh", "net.py"])
        self.assertEqual([item["line"] for item in found if item["file"] == "net.py"], [1, 2, 4])

    def test_plain_code_has_no_network_findings(self):
        self.clean_package()
        self.write("tool.py", "import os\nimport json\nfrom urllib.parse import unquote\n"
                   "def fetch_rows(rows):\n    return rows\n")
        self.write("app.js", "function prefetch(x) { return x; }\n")
        found = self.by_category().get("network code", [])
        self.assertEqual([(i["file"], i["line"]) for i in found], [("tool.py", 3)])


class HumanItems(Case):
    def test_refund_and_warranty_words_are_listed_not_failed(self):
        self.clean_package()
        self.write("README.md", "# Tool\nFull " + "ref" + "und within 30 days.\n"
                   "100% satisfaction " + "guar" + "anteed.\n" + "환" + "불 가능\n")
        found = self.by_category()["refund and warranty words"]
        self.assertEqual([item["line"] for item in found], [2, 3, 4])
        self.assertTrue(all(item["level"] == "HUMAN" for item in found))
        code, out, err = self.run_script([self.pkg, "--strict"])
        self.assertEqual(code, 0, out)

    def test_licence_disclaimer_is_skipped(self):
        self.clean_package()
        self.write("LICENSE", "PROVIDED AS IS, WITHOUT " + "WARR" + "ANTY OF ANY KIND\n")
        self.assertEqual(self.findings(), [])

    def test_price_mentions_and_end_line(self):
        self.clean_package()
        self.write("README.md", "# Tool\nPrice: " + "$" + "19\nWas " + "$" + "9.99, or 19 " +
                   "USD, or " + "₩" + "25,000, or 25000" + "원.\nVersion 2.0, 19 files, $HOME\n")
        found = self.by_category()["price mentions"]
        self.assertEqual(len(found), 5)
        code, out, err = self.run_script([self.pkg])
        self.assertEqual(code, 0)
        self.assertIn("5 price mention(s) found. Checking them against your listing price is "
                      "in Release Gate Pro.", out)

    def test_prices_in_code_are_not_counted(self):
        self.clean_package()
        self.write("tool.py", "cost = '" + "$" + "19'\n")
        self.assertNotIn("price mentions", self.by_category())


class Loading(Case):
    def test_binary_and_large_files_are_listed_as_not_scanned(self):
        self.clean_package()
        self.write("logo.png", b"\x89PNG\x00\x00binary" + SK_KEY.encode())
        self.write("big.txt", "a" * (rg.MAX_FILE_BYTES + 1))
        target = rg.load_target(self.pkg)
        self.assertEqual(rg.inspect(target), [])
        self.assertEqual(sorted(rg.not_scanned(target)), [
            ("big.txt", "larger than 2 MB, not scanned"),
            ("logo.png", "binary, contents not scanned")])
        out = self.run_script([self.pkg])[1]
        self.assertIn("(folder, 6 files, 2 not scanned)", out)

    def test_utf16_and_bom_files_are_read(self):
        self.clean_package()
        path = os.path.join(self.pkg, "notes.txt")
        with open(path, "w", encoding="utf-16") as handle:
            handle.write("path %s\n" % MAC)
        self.write("bom.md", "﻿path %s\n" % LINUX)
        self.assertEqual(len(self.by_category()["absolute paths"]), 2)

    def test_korean_and_spaces_in_names(self):
        self.clean_package()
        self.write("문서 폴더/메모 파일.md", "경로 %s\n" % MAC)
        code, out, err = self.run_script([self.pkg])
        self.assertIn("문서 폴더/메모 파일.md:1", out)
        code, out, err = self.run_script([self.zip_package()])
        self.assertIn("pkg-1.0.0/문서 폴더/메모 파일.md:1", out)

    def test_target_is_never_changed(self):
        self.clean_package()
        self.write(".env", "A=1\n")
        path = self.zip_package()
        before = (sorted(os.listdir(self.pkg)), os.path.getsize(path), os.path.getmtime(path))
        self.run_script([self.pkg])
        self.run_script([path])
        after = (sorted(os.listdir(self.pkg)), os.path.getsize(path), os.path.getmtime(path))
        self.assertEqual(before, after)
        self.assertEqual(sorted(os.listdir(self.root)), ["pkg", "pkg-1.0.0.zip"])

    def test_bad_targets(self):
        code, out, err = self.run_script([os.path.join(self.root, "nope.zip")])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("no such file or folder", err)
        code, out, err = self.run_script([self.write("plain.txt", "not a zip", self.root)])
        self.assertEqual(code, 2)
        self.assertIn("not a ZIP archive", err)

    def test_output_has_no_absolute_path_of_the_target(self):
        self.clean_package()
        code, out, err = self.run_script([self.zip_package()])
        self.assertNotIn(self.root, out)
        self.assertEqual(gp.find(gp.ABSOLUTE_PATHS, out), [])


class Output(Case):
    def test_detail_limit(self):
        self.clean_package()
        self.write("notes.md", "".join("%s%d\n" % (MAC, i) for i in range(30)))
        out = self.run_script([self.pkg])[1]
        self.assertIn("... and 10 more", out)
        out = self.run_script([self.pkg, "--details", "5"])[1]
        self.assertIn("... and 25 more", out)

    def test_cp949_console(self):
        self.clean_package()
        self.write("café ✅ 메모.md", "%s\n" % MAC)
        code, out, err = self.run_script([self.pkg], env={"PYTHONIOENCODING": "cp949"})
        self.assertEqual(code, 0)
        self.assertIn("메모.md:1", out)
        self.assertNotIn("Traceback", err)

    def test_version(self):
        code, out, err = self.run_script(["--version"])
        self.assertIn(rg.__version__, out)


class Patterns(unittest.TestCase):
    def test_stray_names(self):
        self.assertEqual(gp.is_stray("a/b/tool.py"), "")
        self.assertEqual(gp.is_stray(".env.example"), "")
        self.assertEqual(gp.is_stray("environment.py"), "")
        self.assertEqual(gp.is_stray("a/.git/"), "inside .git/")
        self.assertEqual(gp.is_stray("a/__pycache__/x.pyc"), "inside __pycache__/")
        self.assertEqual(gp.is_stray("x.pyc"), "*.pyc file")
        self.assertEqual(gp.is_stray("backup~"), "*~ file")

    def test_licence_kind(self):
        self.assertEqual(gp.licence_kind("MIT License\n\nPermission is hereby granted"), "MIT")
        self.assertEqual(gp.licence_kind("Apache License, Version 2.0"), "Apache-2.0")
        self.assertEqual(gp.licence_kind("All rights reserved."), "other")

    def test_this_package_holds_no_key_shaped_string(self):
        for name in ("gate_patterns.py", "releasegate.py", "make_sample.py"):
            with open(os.path.join(PACKAGE, name), encoding="utf-8") as handle:
                found = [f for f in gp.find_keys(handle.read()) if f[4]]
            self.assertEqual(found, [], name)


if __name__ == "__main__":
    unittest.main()
