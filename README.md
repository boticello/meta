# meta

A command-line tool for reading, writing, and searching macOS file metadata — Finder tags, colour labels, Finder comments, and custom extended attributes.

All output is JSON. All commands exit 0 on success, 1 on error.

## Why this exists

macOS has rich file metadata, but the standard tools have gaps. `tag` doesn't enforce label exclusivity. `osxmetadata` doesn't handle custom xattrs or search. `xattr` is low-level. And no tool correctly handles the distinction between **tags** (multi-valued text labels) and **labels** (exclusive colour dots).

`meta` brings these together into one verb–noun interface with correct semantics.

## Installation

### Prerequisites

- **macOS** (APFS, Apple Silicon or Intel)
- **Python 3.10+**
- **[osxmetadata](https://github.com/RhetTbull/osxmetadata)** — install via pipx:

  ```bash
  pipx install osxmetadata
  ```

  The built-in `xattr`, `mdfind`, and `mdimport` tools are already on macOS.

### Install meta

Clone the repo and symlink the `meta` script onto your PATH:

```bash
git clone https://github.com/bear/<repo>.git ~/Me/repos/meta
ln -s ~/Me/repos/meta/meta /usr/local/bin/meta
```

Or add the directory to your PATH in your shell config:

```bash
export PATH="$HOME/Me/repos/meta:$PATH"
```

There is no pip package — this is a single script with no installable dependencies.

## Quick start

```bash
# What's on this file?
meta get all report.pdf

# Tag it
meta add tags report.pdf "quarterly-review" "urgent"

# Give it a red label (the dot in Finder)
meta set label report.pdf red

# Find all red-labelled files
meta search label red --dir ~/Documents

# Write custom metadata
meta set xattr report.pdf com.project.status "draft"

# Snapshot before changes
meta backup report.pdf
meta restore report.pdf
```

## Commands

The tool uses a **verb–noun** pattern. Run `meta` or `meta --help` for the full reference.

### Reading

| Command | Description |
|---------|-------------|
| `meta get all <file>` | Full JSON dump of all metadata |
| `meta get tags <file>` | Tags with name, colour index, colour name |
| `meta get label <file>` | Current label colour |
| `meta get comment <file>` | Finder comment |
| `meta get xattr <file> <key>` | Value of a specific custom xattr |
| `meta get xattrs <file>` | All xattr keys and values |

### Writing

| Command | Description |
|---------|-------------|
| `meta set tags <file> <tag>...` | Replace all tags |
| `meta set label <file> <colour>` | Set exclusive label colour |
| `meta set comment <file> <text>` | Set Finder comment |
| `meta set xattr <file> <key> <value>` | Write custom xattr |
| `meta add tags <file\|dir> <tag>...` | Append tags (supports `--pattern`) |
| `meta remove tags <file> <tag>...` | Remove specific tags |
| `meta clear tags <file>` | Remove all tags |
| `meta clear label <file>` | Remove label only (keeps text tags) |
| `meta clear comment <file>` | Clear Finder comment |
| `meta delete xattr <file> <key>` | Delete an xattr key entirely |

### Searching

| Command | Description |
|---------|-------------|
| `meta search tag <tag> [--dir <path>]` | Spotlight search by tag |
| `meta search label <colour> [--dir <path>]` | Spotlight search by label colour |
| `meta search xattr <key> [--dir <path>]` | Filesystem scan for custom xattr |
| `meta search text <terms> [--dir <path>]` | Spotlight text search |
| `meta search query <predicate> [--dir <path>]` | Raw `mdfind` predicate |

### Safety

| Command | Description |
|---------|-------------|
| `meta backup <file>` | Snapshot metadata to `.osxmetadata.json` |
| `meta restore <file>` | Restore from snapshot |

### Directory mode

Add `--dir <path>` or `--pattern <glob>` to `set` or `add` commands to operate on all matching files in a directory:

```bash
meta add tags ~/Downloads/ "to-sort" --pattern '*.pdf'
meta set label ~/Documents/inbox red --dir ~/Documents/inbox
```

### Colours

`none` (0), `gray`/`grey` (1), `green` (2), `purple` (3), `blue` (4), `yellow` (5), `red` (6), `orange` (7)

Tags with colour use the form `'name,colour'` — e.g. `'review,red'`, `'final,green'`.

## Tags vs Labels — the critical distinction

**Tags** are multi-valued text labels. A file can have many: `"project-x"`, `"urgent"`, `"draft"`. They optionally carry a colour. Multiple colour tags can coexist.

**Labels** are exclusive colour dots. A file has exactly one at a time. `meta set label` replaces the previous colour while preserving all text tags — this is custom logic, because no standard macOS tool handles it correctly.

Use `meta set label` for colour status. Use `meta add tags` for text organisation. They're independent — a file can have a red label *and* text tags simultaneously.

## Help system

```bash
meta                          # Full command reference
meta help concepts            # Tags vs labels, verb semantics, persistence
meta help search              # Search strategies (Spotlight vs xattr scan)
meta help xattrs              # Custom xattr details and limitations
meta help examples            # Common workflows
meta <verb> --help            # Verb-specific help (e.g. meta set --help)
```

## Dependencies

| Tool | Purpose | How installed |
|------|---------|--------------|
| `osxmetadata` | Tags, comments, reads, backup/restore | `pipx install osxmetadata` |
| `xattr` | Raw extended attribute operations | Built into macOS |
| `mdfind` | Spotlight search | Built into macOS |
| `mdimport` | Post-write Spotlight re-index | Built into macOS |

The `meta` script itself uses only Python stdlib (`plistlib`, `subprocess`, `json`).

## Testing

```bash
python3 tests/run_tests.py            # Run all tests
python3 tests/run_tests.py --verbose  # With output
python3 tests/run_tests.py --keep     # Keep temp directory on failure
```

Tests create isolated fixtures in a temp directory and clean up after themselves. Some search tests may pass gracefully if Spotlight hasn't indexed the temp directory yet.

## Limitations

- **macOS only** — all operations use macOS-specific APIs and xattr semantics
- **Custom xattrs are invisible to Spotlight** — use `meta search xattr` (filesystem scan) instead
- **Custom xattrs are stripped by iCloud Drive** — only Finder Tags survive sync
- **Spotlight lag** — metadata may take 1–2 seconds to appear in search results; `meta` runs `mdimport` automatically after writes to minimise this
- **Comment writes require Finder** — uses Scripting Bridge; won't work in fully headless environments

## Project structure

```
meta            # CLI entry point (symlink this onto your PATH)
core.py         # Core operations (label-exclusive logic, xattr helpers)
help.py         # Topic-based help text
docs/
  requirements.md   # Full requirements and research notes
  SKILL.md          # Craft Agent skill definition
tests/
  run_tests.py      # Self-contained test suite
```

## Licence

Personal use.
