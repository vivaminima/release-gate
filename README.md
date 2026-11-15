# Release Gate

A pre-release check for the ZIP or folder you are about to ship. It reads the package and lists what you would not want a buyer to find: a key left in the code, a `.env`, a path from your own machine, a missing changelog.

## New to this? Start here

**Who it is for:** anyone who sells or shares a downloadable package (a tool, a template, a skill) and builds the ZIP by hand or with a script.

**The problem it solves:** the mistakes that get shipped are the boring ones. A test key in a config file. `__pycache__` in the ZIP. A README that still says the old price. Release Gate reads the finished package and lists them before anyone else does.

**Four steps** (in Claude Desktop, Code tab):

1. Unzip this folder somewhere on your computer. You need Python 3.8 or newer.
2. In the Code tab, choose this folder as the project folder.
3. Type the sentence below.
4. Read the table in Claude's reply: the "FAIL" rows are what to fix first.

**Type this to Claude:**

    Run make_sample.py, then run releasegate.py on sample-out/acme-notes-1.0.0.zip and tell me what I have to fix before I ship it.

**What you get back** (real output of the tool, run on 2026-11-13 by a fresh Claude Code agent session given that sentence and a copy of this folder; cut where marked `...`; Claude's own summary around it will differ):

```
Release Gate 1.0.0  (patterns 1.0.0)
Target: acme-notes-1.0.0.zip  (zip, 6 files, 2 not scanned)

  FAIL    key-shaped strings            1   a well-known key format; the value is hidden
  FAIL    stray files                   3   files and folders that are usually left in by accident
  FAIL    required files                1   README, LICENSE and CHANGELOG at the top of the package
  ok      unsafe entry names            0   ZIP entries with absolute or parent paths
  ok      key look-alikes               0   may be a secret, may be a hash or a sample
  REVIEW  absolute paths                2   paths from the machine the package was made on
  REVIEW  network code                  2   code that can make network requests
  ok      archives inside               0   archives in the package; their contents are not scanned
  HUMAN   refund and warranty words     2   wording a person should read before selling
  HUMAN   price mentions                1   prices written in the package

Details
  key-shaped strings
    acme-notes-1.0.0/notes.py:5  API key (sk- prefix)  sk-Z***(35 chars)
  stray files
    acme-notes-1.0.0/.DS_Store  file .DS_Store
    acme-notes-1.0.0/.env  file .env
    acme-notes-1.0.0/__pycache__/notes.cpython-310.pyc  inside __pycache__/
  required files
    acme-notes-1.0.0/  missing: CHANGELOG
  ...

Result: NOT READY: 5 to fix, 4 to review, 3 for a person to read
Release Gate is a pre-release check aid. It looks for the patterns above and nothing else. A result with nothing to fix does not mean the package is safe or compliant.
1 price mention(s) found. Checking them against your listing price is in Release Gate Pro.
```

In that run Claude then listed the five things to fix in plain words: remove the key from `notes.py` and replace the key itself, take `.env`, `.DS_Store` and `__pycache__` out of the ZIP, and add a CHANGELOG.

The sample is made up, and `make_sample.py` builds it on your machine. A second sample, `sample-out/acme-notes-1.0.1.zip`, is the same package with the mistakes fixed.

## Use

```
python releasegate.py my-tool-1.2.0.zip
python releasegate.py path/to/folder
python releasegate.py my-tool-1.2.0.zip --strict
```

| Option | Meaning |
| --- | --- |
| `target` | The ZIP file or folder you are about to ship. |
| `--strict` | Exit 1 when there are items to review, too. |
| `--details N` | Lines of detail shown per group. Default 20. |

Exit codes: `0` nothing to fix, `1` something to fix, `2` the target could not be read.

The tool reads the package in memory. It extracts nothing to disk, runs nothing from the package and writes no files.

## What it looks for

| Row | Level | What it is |
| --- | --- | --- |
| key-shaped strings | FAIL | Well-known key formats: `sk-` keys, cloud access key ids, code-host and chat tokens, payment keys, private key blocks, JSON web tokens. The value is never printed; you see the first characters and the length. |
| stray files | FAIL | `__pycache__`, `.git`, `node_modules`, `.claude`, `.env` (but not `.env.example`), `.DS_Store`, `Thumbs.db`, `*.pyc`, `*.bak`, `*.pem`, editor folders and the like. |
| required files | FAIL | A README, a LICENSE and a CHANGELOG at the top of the package. |
| unsafe entry names | FAIL | ZIP entries with an absolute path or `..` in the name. |
| key look-alikes | REVIEW | A value assigned to something named key, secret, token or password; a long hex string. Often a hash or a sample. |
| absolute paths | REVIEW | Windows drive paths and macOS or Linux home paths, which usually carry a user name. |
| network code | REVIEW | In code files only: network imports and calls in Python, `fetch` and network modules in JavaScript, download commands in shell scripts. |
| archives inside | REVIEW | Archives in the package. Their contents are not scanned. |
| refund and warranty words | HUMAN | Words such as refund, guarantee, warranty, 환불, 보증. Listed so a person reads the sentence. LICENSE files are skipped. |
| price mentions | HUMAN | Prices written in documents. |

- **FAIL** rows make the exit code 1.
- **REVIEW** rows are things that are sometimes intended. Read each one. `--strict` treats them as failures.
- **HUMAN** rows are never failures. The tool cannot know whether a sentence about refunds is what you mean; it only makes sure you see it.

Placeholders such as `YOUR_API_KEY` or `xxxxxxxx` are not reported. Files larger than 2 MB and binary files are listed under "Not scanned".

Every pattern is in [gate_patterns.py](gate_patterns.py), in plain regular expressions you can read and change.

## What this tool is not

Release Gate is a check aid. It looks for the patterns in the table and nothing else.

- A result of "NOTHING TO FIX" means those patterns were not found. It does not mean the package is safe, legal or compliant, and the tool never says so.
- It does not run your code, so it cannot tell you whether the package works.
- It does not find secrets in formats it does not know, secrets inside binary files, or secrets inside nested archives.
- "Network code" is found by pattern. Code that reaches the network in another way is not listed.

Use it as the last look before a person decides, not as the decision.

## Tests

```
python -m unittest discover -s tests -v
```

38 tests: each key format found and hidden, placeholders skipped, stray files in folders and ZIPs, required files, unsafe entry names, absolute paths and what is not one, network code in code files only, the human-read rows, binary and large files, Korean file names, a cp949 console, and that the target is never changed.

## Known limits

- Pattern matching gives false positives (a path in a tutorial, a hash) and false negatives (a key in an unknown format). The REVIEW level exists for the first; nothing fixes the second.
- A file over 2 MB is skipped whole and listed under "Not scanned".
- A ZIP protected by a password cannot be read; its entries are listed as not scanned.
- Tested on Windows with Python 3.10.

## About the name

The beginner steps mention Claude Desktop because that is where they were tried. This tool is not affiliated with, endorsed by or sponsored by Anthropic.

## Licence

MIT. See [LICENSE](LICENSE). Copyright (c) 2026 Vivaminima.

## More from Vivaminima

- **Token Audit Kit ($19)** — see how many tokens your CLAUDE.md and its @imports cost before your first prompt, and a step-by-step guide to split it. Free script: https://github.com/vivaminima/context-file-audit · Paid kit: https://vivaminima.lemonsqueezy.com/checkout/buy/57973270-94ea-4cc7-bcb4-294693714087
- Free tools: [skill-audit-kit](https://github.com/vivaminima/skill-audit-kit) · [secret-map](https://github.com/vivaminima/secret-map) · [inbox-ledger](https://github.com/vivaminima/inbox-ledger) · [release-gate](https://github.com/vivaminima/release-gate) · [skill-install-gate](https://github.com/vivaminima/skill-install-gate) · [console-safe](https://github.com/vivaminima/console-safe) · [checklist-stop](https://github.com/vivaminima/checklist-stop) · [handoff-check](https://github.com/vivaminima/handoff-check) · [llm-budget-router-lite](https://github.com/vivaminima/llm-budget-router-lite) · [go-no-go-verdict-skill](https://github.com/vivaminima/go-no-go-verdict-skill) · [ai-company-starter-kit](https://github.com/vivaminima/ai-company-starter-kit) · [beginner-readme-section](https://github.com/vivaminima/beginner-readme-section)

Vivaminima is not affiliated with, endorsed by or sponsored by Anthropic.
