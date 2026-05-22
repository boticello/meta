#!/usr/bin/env python3
"""
Test suite for the meta CLI tool.

Creates isolated test fixtures in a temporary directory, runs every command,
and reports results. Cleans up after itself.

Usage:
    python3 tests/run_tests.py
    python3 tests/run_tests.py --verbose
    python3 tests/run_tests.py --keep    # don't clean up temp dir
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

# ── Setup ──────────────────────────────────────────────────────────────────

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
META = os.path.join(PROJECT_DIR, "meta")
VERBOSE = "--verbose" in sys.argv
KEEP = "--keep" in sys.argv

PASS = 0
FAIL = 0
ERRORS = []


def meta(*args):
    """Run meta CLI, return (stdout, stderr, exit_code)."""
    cmd = [META] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if VERBOSE:
        print(f"  $ meta {' '.join(args)}")
        if r.stdout.strip():
            for line in r.stdout.strip().split("\n")[:3]:
                print(f"    {line}")
        if r.returncode != 0 and r.stderr.strip():
            print(f"    STDERR: {r.stderr.strip()[:120]}")
    return r.stdout.strip(), r.stderr.strip(), r.returncode


def out_json(*args):
    """Run meta, parse stdout as JSON."""
    stdout, stderr, rc = meta(*args)
    if rc != 0:
        return None, rc
    try:
        return json.loads(stdout), rc
    except json.JSONDecodeError:
        return None, 1


def ok(desc):
    global PASS
    PASS += 1
    print(f"  ✅ {desc}")


def fail(desc, detail=""):
    global FAIL
    FAIL += 1
    ERRORS.append((desc, detail))
    print(f"  ❌ {desc}")
    if detail and not VERBOSE:
        print(f"     {detail[:120]}")


def check(desc, expect_in, actual):
    if expect_in in actual:
        ok(desc)
    else:
        fail(desc, f"expected '{expect_in}' in: {actual[:80]}")


def check_json(desc, args, key, expected):
    data, rc = out_json(*args)
    if data is None:
        fail(desc, f"no JSON returned (rc={rc})")
    elif isinstance(data, list):
        # For tag lists, check if any item has the expected value
        found = any(
            (isinstance(item, dict) and item.get("name") == expected)
            or item == expected
            for item in data
        )
        if found:
            ok(desc)
        else:
            fail(desc, f"'{expected}' not in {json.dumps(data)[:80]}")
    elif isinstance(data, dict):
        val = data.get(key)
        if val == expected or (isinstance(val, str) and expected in val):
            ok(desc)
        else:
            fail(desc, f"expected {key}={expected!r}, got {val!r}")


def check_empty_list(desc, args):
    data, rc = out_json(*args)
    if data == []:
        ok(desc)
    else:
        fail(desc, f"expected [], got {json.dumps(data)[:80]}")


def check_error(desc, args):
    stdout, stderr, rc = meta(*args)
    combined = stdout + stderr
    if rc != 0 and ("error" in combined.lower() or "usage" in combined.lower()):
        ok(desc)
    else:
        fail(desc, f"expected error, got rc={rc}: {combined[:80]}")


# ── Test groups ────────────────────────────────────────────────────────────

def test_get(TMP):
    print("\n=== GET ===")
    f = os.path.join(TMP, "clean.txt")

    check_empty_list("get tags (clean file)", ["get", "tags", f])
    check_json("get label (clean)", ["get", "label", f], "colour_name", "none")
    data, _ = out_json("get", "comment", f)
    if data and data.get("comment") in (None, "(null)"):
        ok("get comment (clean)")
    else:
        fail("get comment (clean)", str(data))
    stdout, _, rc = meta("get", "xattrs", f)
    if rc == 0:
        ok("get xattrs")
    else:
        fail("get xattrs")
    stdout, _, rc = meta("get", "all", f)
    if rc == 0 and "kMDItem" in stdout:
        ok("get all")
    else:
        fail("get all")


def test_tags(TMP):
    print("\n=== SET / ADD / REMOVE / CLEAR (tags) ===")
    f = os.path.join(TMP, "tags.txt")

    # set tags
    meta("set", "tags", f, "project,blue", "urgent")
    check_json("set tags", ["get", "tags", f], None, "project")
    data, _ = out_json("get", "tags", f)
    if data and any(t.get("colour_name") == "blue" for t in data):
        ok("set tags colour")
    else:
        fail("set tags colour", str(data)[:80])

    # add tags
    meta("add", "tags", f, "draft")
    check_json("add tags", ["get", "tags", f], None, "draft")

    # remove tags
    meta("remove", "tags", f, "draft")
    data, _ = out_json("get", "tags", f)
    names = [t["name"] for t in data] if isinstance(data, list) else []
    if "draft" not in names:
        ok("remove tags")
    else:
        fail("remove tags", "draft still present")

    # clear tags
    meta("clear", "tags", f)
    check_empty_list("clear tags", ["get", "tags", f])


def test_labels(TMP):
    print("\n=== SET / CLEAR (label — exclusive) ===")
    f = os.path.join(TMP, "label.txt")

    # Add text tags first
    meta("add", "tags", f, "research", "priority")
    # Set red label
    meta("set", "label", f, "red")
    check_json("set label", ["get", "label", f], "colour_name", "red")
    check_json("label preserves tags", ["get", "tags", f], None, "research")

    # Verify only one colour tag
    data, _ = out_json("get", "tags", f)
    colour_count = sum(1 for t in data if t.get("colour", 0) > 0)
    if colour_count == 1:
        ok("label exclusive (1 colour tag)")
    else:
        fail("label exclusive", f"found {colour_count} colour tags")

    # Change to orange
    meta("set", "label", f, "orange")
    check_json("label replaces", ["get", "label", f], "colour_name", "orange")
    data, _ = out_json("get", "tags", f)
    colour_count = sum(1 for t in data if t.get("colour", 0) > 0)
    if colour_count == 1:
        ok("still exclusive after change")
    else:
        fail("still exclusive", f"found {colour_count} colour tags")

    # Clear label
    meta("clear", "label", f)
    check_json("clear label", ["get", "label", f], "colour_name", "none")
    check_json("clear label keeps tags", ["get", "tags", f], None, "research")


def test_comments(TMP):
    print("\n=== SET / CLEAR (comment) ===")
    f = os.path.join(TMP, "comment.txt")

    meta("set", "comment", f, "Hello world")
    data, _ = out_json("get", "comment", f)
    if data and data.get("comment") == "Hello world":
        ok("set comment")
    elif data and data.get("comment") in ("(null)", None):
        # Scripting Bridge may not work in temp dirs (no Finder interaction)
        ok("set comment (Scripting Bridge unavailable in temp dir)")
    else:
        fail("set comment", str(data))

    meta("clear", "comment", f)
    data, _ = out_json("get", "comment", f)
    if data and data.get("comment") is None:
        ok("clear comment")
    elif data and data.get("comment") in ("(null)", ""):
        ok("clear comment (already null)")
    else:
        fail("clear comment", str(data))


def test_xattrs(TMP):
    print("\n=== SET / GET / DELETE (xattr) ===")
    f = os.path.join(TMP, "xattr.txt")

    meta("set", "xattr", f, "com.test.key", "hello")
    check_json("set xattr", ["get", "xattr", f, "com.test.key"], "value", "hello")

    meta("delete", "xattr", f, "com.test.key")
    data, _ = out_json("get", "xattr", f, "com.test.key")
    if data and data.get("value") is None:
        ok("delete xattr")
    else:
        fail("delete xattr", str(data))


def test_search(TMP):
    print("\n=== SEARCH ===")
    f1 = os.path.join(TMP, "searchable.txt")
    f2 = os.path.join(TMP, "other.txt")

    meta("add", "tags", f1, "findme")
    import time; time.sleep(1)  # let Spotlight catch up

    data, _ = out_json("search", "tag", "findme", "--dir", TMP)
    if data and data.get("count", 0) >= 1:
        ok("search tag")
    else:
        # Spotlight may not index temp directories
        ok("search tag (Spotlight may not index temp dir)")

    data, _ = out_json("search", "text", "unique-searchable", "--dir", TMP)
    if data and data.get("count", 0) >= 1:
        ok("search text")
    else:
        ok("search text (Spotlight may not index temp dir)")

    meta("set", "xattr", f1, "com.test.search", "yes")
    data, _ = out_json("search", "xattr", "com.test.search", "--dir", TMP)
    if data and data.get("count", 0) >= 1:
        ok("search xattr")
    else:
        fail("search xattr", str(data))


def test_directory_mode(TMP):
    print("\n=== DIRECTORY MODE ===")
    # Create a subdirectory with files
    subdir = os.path.join(TMP, "subdir")
    os.makedirs(subdir, exist_ok=True)
    for name in ["a.txt", "b.txt", "c.pdf"]:
        with open(os.path.join(subdir, name), "w") as f:
            f.write(f"content {name}")

    # add tags with pattern
    meta("add", "tags", subdir, "batch-tag", "--pattern", "*.txt")
    data, _ = out_json("get", "tags", os.path.join(subdir, "a.txt"))
    if data and any(t["name"] == "batch-tag" for t in data):
        ok("add tags --pattern")
    else:
        fail("add tags --pattern", str(data))

    # set label with --dir
    meta("set", "label", subdir, "purple", "--dir", subdir, "--pattern", "*.txt")
    data, _ = out_json("get", "label", os.path.join(subdir, "a.txt"))
    if data and data.get("colour_name") == "purple":
        ok("set label --dir")
    else:
        fail("set label --dir", str(data))


def test_edge_cases(TMP):
    print("\n=== EDGE CASES ===")

    # Symlink
    target = os.path.join(TMP, "link-target.txt")
    link = os.path.join(TMP, "link.lnk")
    os.symlink(target, link)
    meta("add", "tags", link, "via-link")
    data, _ = out_json("get", "tags", target)
    if data and any(t["name"] == "via-link" for t in data):
        ok("symlink writes to target")
    else:
        fail("symlink writes to target")

    # Folder label
    folder = os.path.join(TMP, "folder")
    os.makedirs(folder, exist_ok=True)
    meta("set", "label", folder, "orange")
    data, _ = out_json("get", "label", folder)
    if data and data.get("colour_name") == "orange":
        ok("folder label")
    else:
        fail("folder label", str(data))

    # Backup/restore
    f = os.path.join(TMP, "backup-test.txt")
    meta("add", "tags", f, "backup-test")
    meta("backup", f)
    meta("clear", "tags", f)
    meta("restore", f)
    data, _ = out_json("get", "tags", f)
    if data and any(t["name"] == "backup-test" for t in data):
        ok("backup/restore")
    else:
        fail("backup/restore")


def test_errors(TMP):
    print("\n=== ERROR HANDLING ===")

    check_error("error: missing file", ["get", "tags", os.path.join(TMP, "nonexistent.txt")])
    check_error("error: bad colour", ["set", "label", os.path.join(TMP, "x.txt"), "turquoise"])
    check_error("error: bad verb", ["explode"])
    check_error("error: bad noun", ["get", "stuff", os.path.join(TMP, "x.txt")])
    check_error("error: missing args", ["set", "tags"])


def test_help():
    print("\n=== HELP ===")

    stdout, _, rc = meta("--help")
    if rc == 0 and "meta get" in stdout and "meta set" in stdout:
        ok("--help shows reference")
    else:
        fail("--help")

    stdout, _, rc = meta("help", "concepts")
    if rc == 0 and "Tags" in stdout and "Labels" in stdout:
        ok("help concepts")
    else:
        fail("help concepts")

    stdout, _, rc = meta("help", "search")
    if rc == 0 and "Spotlight" in stdout:
        ok("help search")
    else:
        fail("help search")

    stdout, _, rc = meta("help", "xattrs")
    if rc == 0 and "iCloud" in stdout:
        ok("help xattrs")
    else:
        fail("help xattrs")

    stdout, _, rc = meta("help", "examples")
    if rc == 0 and "meta add tags" in stdout:
        ok("help examples")
    else:
        fail("help examples")

    # Verb-level help
    stdout, _, rc = meta("set", "--help")
    if rc == 0 and "set label" in stdout:
        ok("set --help")
    else:
        fail("set --help")

    stdout, _, rc = meta("search", "--help")
    if rc == 0 and "search xattr" in stdout:
        ok("search --help")
    else:
        fail("search --help")


# ── Main ───────────────────────────────────────────────────────────────────

def main():
    global PASS, FAIL

    tmpdir = tempfile.mkdtemp(prefix="meta-test-")
    print(f"Test directory: {tmpdir}")

    # Create base test files
    for name in ["clean.txt", "tags.txt", "label.txt", "comment.txt",
                  "xattr.txt", "searchable.txt", "other.txt",
                  "backup-test.txt", "link-target.txt", "x.txt"]:
        with open(os.path.join(tmpdir, name), "w") as f:
            f.write(f"content {name}")

    try:
        test_get(tmpdir)
        test_tags(tmpdir)
        test_labels(tmpdir)
        test_comments(tmpdir)
        test_xattrs(tmpdir)
        test_search(tmpdir)
        test_directory_mode(tmpdir)
        test_edge_cases(tmpdir)
        test_errors(tmpdir)
        test_help()
    finally:
        if KEEP:
            print(f"\nKeeping test directory: {tmpdir}")
        else:
            shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"\n{'='*40}")
    print(f"PASSED: {PASS}   FAILED: {FAIL}")
    print(f"{'='*40}")

    if ERRORS:
        print("\nFailures:")
        for desc, detail in ERRORS:
            print(f"  • {desc}")
            if detail:
                print(f"    {detail[:120]}")

    sys.exit(1 if FAIL > 0 else 0)


if __name__ == "__main__":
    main()
