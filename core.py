#!/usr/bin/env python3
"""
macmeta.core — Core metadata operations for macOS.

Custom logic for label-exclusive set/clear and low-level xattr operations.
Everything else is delegated to osxmetadata CLI, mdfind, mdimport, xattr.
"""

import json
import plistlib
import subprocess
import os

# ── Constants ──────────────────────────────────────────────────────────────

COLOURS = {
    "none": 0, "gray": 1, "grey": 1, "green": 2,
    "purple": 3, "blue": 4, "yellow": 5, "red": 6, "orange": 7,
}
COLOUR_NAMES = {v: k for k, v in COLOURS.items() if v > 0}

TAGS_XATTR = "com.apple.metadata:_kMDItemUserTags"
FINDERINFO_XATTR = "com.apple.FinderInfo"

COLOUR_MASK = 0xF1  # preserve bits 0,4-7; clear bits 1-3 (colour)


# ── Helpers ────────────────────────────────────────────────────────────────

def resolve_colour(name_or_index):
    """Accept 'red', 'Red', 6, '6' — return integer 0-7."""
    if isinstance(name_or_index, int):
        return name_or_index
    s = str(name_or_index).strip().lower()
    if s in COLOURS:
        return COLOURS[s]
    try:
        i = int(s)
        if 0 <= i <= 7:
            return i
    except ValueError:
        pass
    raise ValueError(f"Unknown colour: {name_or_index!r}. Use: {sorted(set(COLOURS.keys()))}")


def _run(cmd, check=True):
    """Run a subprocess, return CompletedProcess."""
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _read_xattr_hex(filepath, key):
    """Read an xattr as hex string. Returns None if key doesn't exist."""
    r = _run(["xattr", "-px", key, filepath], check=False)
    if r.returncode != 0:
        return None
    return r.stdout.strip().replace("\n", "").replace(" ", "")


def _write_xattr_hex(filepath, key, hex_value):
    """Write an xattr from hex string."""
    _run(["xattr", "-wx", key, hex_value, filepath])


def _read_tags_raw(filepath):
    """Read _kMDItemUserTags as a Python list of strings. Returns [] if none."""
    hex_str = _read_xattr_hex(filepath, TAGS_XATTR)
    if hex_str is None:
        return []
    raw = bytes.fromhex(hex_str)
    return plistlib.loads(raw)


def _write_tags_raw(filepath, tags_list):
    """Write a list of tag strings to _kMDItemUserTags."""
    bp = plistlib.dumps(tags_list)
    _write_xattr_hex(filepath, TAGS_XATTR, bp.hex())


def _read_finderinfo_byte9(filepath):
    """Read byte 9 from FinderInfo. Returns 0 if no FinderInfo xattr."""
    hex_str = _read_xattr_hex(filepath, FINDERINFO_XATTR)
    if hex_str is None:
        return 0
    raw = bytes.fromhex(hex_str)
    return raw[9]


def _write_finderinfo_colour(filepath, colour_index):
    """Set the colour bits in FinderInfo byte 9, preserving all other bits."""
    hex_str = _read_xattr_hex(filepath, FINDERINFO_XATTR)
    if hex_str is None:
        if colour_index == 0:
            return
        finder_info = bytearray(32)
    else:
        finder_info = bytearray.fromhex(hex_str)

    finder_info[9] = (finder_info[9] & COLOUR_MASK) | (colour_index << 1)

    if colour_index == 0:
        if all(b == 0 for b in finder_info):
            _run(["xattr", "-d", FINDERINFO_XATTR, filepath], check=False)
            return

    _write_xattr_hex(filepath, FINDERINFO_XATTR, finder_info.hex())


def _mdimport(filepath):
    """Nudge Spotlight to re-index a file."""
    _run(["mdimport", filepath], check=False)


def _encode_tag(name, colour_index):
    """Encode a tag as 'Name\\n<colour>'."""
    return f"{name}\n{colour_index}"


def _check_file(filepath):
    """Validate file exists."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"No such file: {filepath}")


def _collect_files(target, pattern=None):
    """Resolve a target to a list of file paths.
    If target is a file, return [target].
    If target is a directory (via --dir), return all matching files recursively."""
    if os.path.isfile(target):
        return [target]
    if os.path.isdir(target):
        import fnmatch
        files = []
        for entry in os.scandir(target):
            if entry.is_file(follow_symlinks=True):
                if pattern is None or fnmatch.fnmatch(entry.name, pattern):
                    files.append(entry.path)
        return files
    raise FileNotFoundError(f"No such file or directory: {target}")


# ── GET operations ─────────────────────────────────────────────────────────

def get_all(filepath):
    """Full JSON metadata dump via osxmetadata."""
    _check_file(filepath)
    r = _run(["osxmetadata", "-j", "--list", filepath])
    return r.stdout


def get_tags(filepath):
    """Return tags as structured list."""
    _check_file(filepath)
    raw = _read_tags_raw(filepath)
    result = []
    for t in raw:
        parts = t.split("\n")
        name = parts[0]
        colour = int(parts[1]) if len(parts) > 1 else 0
        result.append({
            "name": name,
            "colour": colour,
            "colour_name": COLOUR_NAMES.get(colour, "none") if colour > 0 else "none",
        })
    return result


def get_label(filepath):
    """Read the current label colour directly from FinderInfo xattr."""
    _check_file(filepath)
    byte9 = _read_finderinfo_byte9(filepath)
    colour = (byte9 >> 1) & 0x07
    return {
        "colour": colour,
        "colour_name": COLOUR_NAMES.get(colour, "none") if colour > 0 else "none",
    }


def get_comment(filepath):
    """Read Finder comment via osxmetadata."""
    _check_file(filepath)
    r = _run(["osxmetadata", "-j", "-g", "findercomment", filepath])
    data = json.loads(r.stdout)
    return data.get("kMDItemFinderComment") or data.get("findercomment")


def get_xattr(filepath, key):
    """Read a specific xattr value."""
    _check_file(filepath)
    r = _run(["xattr", "-p", key, filepath], check=False)
    if r.returncode != 0:
        return None
    return r.stdout.strip()


def get_xattrs(filepath):
    """List all xattr keys and their values."""
    _check_file(filepath)
    r = _run(["xattr", filepath])
    keys = [k for k in r.stdout.strip().split("\n") if k]
    result = {}
    for key in keys:
        r2 = _run(["xattr", "-p", key, filepath], check=False)
        val = r2.stdout.strip()
        if len(val) > 80:
            val = val[:77] + "..."
        result[key] = val
    return result


# ── SET operations ─────────────────────────────────────────────────────────

def set_tags(filepath, *tag_specs):
    """Replace all tags with the given set."""
    _check_file(filepath)
    for i, spec in enumerate(tag_specs):
        if i == 0:
            _run(["osxmetadata", "--set", "tags", spec, filepath])
        else:
            _run(["osxmetadata", "--append", "tags", spec, filepath])
    _mdimport(filepath)
    return {"success": True, "file": filepath, "operation": "set tags"}


def set_label(filepath, colour):
    """Set the exclusive label colour, preserving existing text tags."""
    _check_file(filepath)
    colour_index = resolve_colour(colour)

    raw_tags = _read_tags_raw(filepath)
    text_tags = []
    removed_colours = []
    for t in raw_tags:
        parts = t.split("\n")
        c = int(parts[1]) if len(parts) > 1 else 0
        if c > 0:
            removed_colours.append((parts[0], c))
        else:
            text_tags.append(t)

    new_colour_tag = _encode_tag(COLOUR_NAMES[colour_index].capitalize(), colour_index)
    new_tags = [new_colour_tag] + text_tags

    _write_tags_raw(filepath, new_tags)
    _write_finderinfo_colour(filepath, colour_index)
    _mdimport(filepath)

    return {
        "success": True,
        "file": filepath,
        "operation": "set label",
        "colour": colour_index,
        "colour_name": COLOUR_NAMES.get(colour_index, "none"),
        "removed_colours": [COLOUR_NAMES.get(c, "?") for _, c in removed_colours],
        "preserved_tags": [t.split("\n")[0] for t in text_tags],
    }


def set_comment(filepath, text):
    """Set Finder comment via osxmetadata (Scripting Bridge)."""
    _check_file(filepath)
    _run(["osxmetadata", "--set", "findercomment", text, filepath])
    return {"success": True, "file": filepath, "operation": "set comment"}


def set_xattr(filepath, key, value):
    """Write a custom xattr."""
    _check_file(filepath)
    _run(["xattr", "-w", key, value, filepath])
    _mdimport(filepath)
    return {"success": True, "file": filepath, "operation": "set xattr", "key": key}


# ── ADD operations ─────────────────────────────────────────────────────────

def add_tags(target, *tag_specs, pattern=None):
    """Add one or more tags. Target can be a file or directory."""
    files = _collect_files(target, pattern)
    results = []
    for f in files:
        for spec in tag_specs:
            _run(["osxmetadata", "--append", "tags", spec, f])
        _mdimport(f)
        results.append({"file": f, "tags": get_tags(f)})
    return {"success": True, "operation": "add tags", "count": len(results), "files": results}


# ── REMOVE operations ──────────────────────────────────────────────────────

def remove_tags(filepath, *tag_names):
    """Remove specific tags by name."""
    _check_file(filepath)
    for name in tag_names:
        _run(["osxmetadata", "--remove", "tags", name, filepath])
    _mdimport(filepath)
    return {"success": True, "file": filepath, "operation": "remove tags"}


# ── CLEAR operations ───────────────────────────────────────────────────────

def clear_tags(filepath):
    """Remove all tags."""
    _check_file(filepath)
    _run(["osxmetadata", "--clear", "tags", filepath])
    _mdimport(filepath)
    return {"success": True, "file": filepath, "operation": "clear tags"}


def clear_label(filepath):
    """Remove the label colour only, preserving all text tags."""
    _check_file(filepath)
    raw_tags = _read_tags_raw(filepath)
    text_tags = [t for t in raw_tags if t.split("\n")[1 if "\n" in t else ""] == "0"
                 or (t.split("\n")[1] if "\n" in t else "0") == "0"]
    cleaned = []
    for t in raw_tags:
        parts = t.split("\n")
        c = int(parts[1]) if len(parts) > 1 else 0
        if c == 0:
            cleaned.append(t)

    _write_tags_raw(filepath, cleaned)
    _write_finderinfo_colour(filepath, 0)
    _mdimport(filepath)
    return {"success": True, "file": filepath, "operation": "clear label"}


def clear_comment(filepath):
    """Clear Finder comment."""
    _check_file(filepath)
    _run(["osxmetadata", "--clear", "findercomment", filepath])
    return {"success": True, "file": filepath, "operation": "clear comment"}


# ── DELETE operations ──────────────────────────────────────────────────────

def delete_xattr(filepath, key):
    """Delete a custom xattr key entirely."""
    _check_file(filepath)
    _run(["xattr", "-d", key, filepath])
    _mdimport(filepath)
    return {"success": True, "file": filepath, "operation": "delete xattr", "key": key}


# ── SEARCH operations ──────────────────────────────────────────────────────

def search_tag(tag, directory=None):
    """Search by tag using mdfind."""
    cmd = ["mdfind", f"kMDItemUserTags == '{tag}'"]
    if directory:
        cmd += ["-onlyin", directory]
    r = _run(cmd)
    return [p for p in r.stdout.strip().split("\n") if p]


def search_label(colour, directory=None):
    """Search by label colour using mdfind."""
    colour_index = resolve_colour(colour)
    cmd = ["mdfind", f"kMDItemFSLabel == {colour_index}"]
    if directory:
        cmd += ["-onlyin", directory]
    r = _run(cmd)
    return [p for p in r.stdout.strip().split("\n") if p]


def search_query(predicate, directory=None):
    """Raw mdfind query."""
    cmd = ["mdfind", predicate]
    if directory:
        cmd += ["-onlyin", directory]
    r = _run(cmd)
    return [p for p in r.stdout.strip().split("\n") if p]


def search_text(terms, directory=None):
    """Spotlight text search."""
    cmd = ["mdfind", terms]
    if directory:
        cmd += ["-onlyin", directory]
    r = _run(cmd)
    return [p for p in r.stdout.strip().split("\n") if p]


def search_xattr(key, directory="."):
    """Search for files with a specific custom xattr key (os.scandir, not Spotlight)."""
    results = []
    for entry in os.scandir(directory):
        if not entry.is_file(follow_symlinks=True):
            continue
        r = _run(["xattr", entry.path], check=False)
        if r.returncode == 0 and key in r.stdout:
            results.append(entry.path)
    return results


# ── BACKUP / RESTORE ───────────────────────────────────────────────────────

def backup(filepath):
    """Snapshot metadata to .osxmetadata.json."""
    _check_file(filepath)
    _run(["osxmetadata", "--backup", filepath])
    return {"success": True, "file": filepath, "operation": "backup"}


def restore(filepath):
    """Restore metadata from .osxmetadata.json."""
    _check_file(filepath)
    _run(["osxmetadata", "--restore", filepath])
    return {"success": True, "file": filepath, "operation": "restore"}
