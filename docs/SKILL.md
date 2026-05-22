---
name: "Mac Metadata"
description: "Read, write, and search macOS file metadata — Finder tags, colour labels, comments, and custom extended attributes"
alwaysAllow: ["Bash"]
---

# Mac Metadata Skill

This skill gives you control over macOS file metadata: Finder tags, colour labels, Finder comments, and custom extended attributes (xattrs). It wraps a CLI tool called `meta` that handles all operations with correct macOS semantics.

## The Tool

The `meta` CLI is located at:

```
/Users/bear/Me/scratch/metadata-test/meta/meta
```

All commands return JSON. All commands exit 0 on success, 1 on error (with a JSON error message on stderr).

Call it via bash:

```bash
/Users/bear/Me/scratch/metadata-test/meta/meta <verb> <noun> [args...]
```

You may find it useful to set a shell alias at the start of a session:

```bash
alias meta=/Users/bear/Me/scratch/metadata-test/meta/meta
```

## Command Structure

The tool uses a **verb–noun** pattern. The verbs are: `get`, `set`, `add`, `remove`, `clear`, `delete`, `search`, `backup`, `restore`.

### GET — Read metadata

```bash
meta get all <file>                  # Full JSON dump of all metadata
meta get tags <file>                 # Tags with colour info
meta get label <file>                # Current label colour
meta get comment <file>              # Finder comment
meta get xattr <file> <key>         # Custom xattr value
meta get xattrs <file>               # All xattr keys and values
```

### SET — Write metadata (replaces existing value)

```bash
meta set tags <file> "tag1" "tag2,red"        # Replace all tags
meta set label <file> <colour>                 # Set exclusive label colour
meta set comment <file> "comment text"         # Set Finder comment
meta set xattr <file> <key> <value>            # Write custom xattr
```

### ADD — Append without replacing

```bash
meta add tags <file> "newtag"        # Add tag to existing set
meta add tags <file> "review,red"    # Add tag with colour
```

### REMOVE — Remove specific items from a collection

```bash
meta remove tags <file> "tagname"    # Remove one tag, leave others
```

### CLEAR — Empty a value

```bash
meta clear tags <file>               # Remove all tags
meta clear label <file>              # Remove label colour only (keeps text tags)
meta clear comment <file>            # Clear Finder comment
```

### DELETE — Remove an attribute key entirely

```bash
meta delete xattr <file> <key>       # Delete custom xattr
```

### SEARCH — Find files by metadata

```bash
meta search tag <tagname> [--dir <path>]        # Spotlight search by tag
meta search label <colour> [--dir <path>]       # Spotlight search by label
meta search xattr <key> [--dir <path>]          # Filesystem search for custom xattr
meta search text <terms> [--dir <path>]         # Spotlight text search
meta search query "<predicate>" [--dir <path>]  # Raw mdfind predicate
```

### BACKUP / RESTORE — Safety net

```bash
meta backup <file>                   # Snapshot to .osxmetadata.json
meta restore <file>                  # Restore from snapshot
```

## Directory Mode

Any `set` or `add` command can operate on all files in a directory instead of a single file. Use `--dir <path>` or `--pattern <glob>`:

```bash
meta add tags . "project-x" --pattern '*.pdf'
meta set label . red --dir ~/Documents/inbox
```

## Critical Concept: Tags vs Labels

macOS stores two related but distinct kinds of colour metadata. **You must understand the difference.**

### Tags (multi-valued, no exclusivity)
- A file can have any number of tags: `"project-x"`, `"urgent"`, `"draft"`
- Tags optionally carry a colour: `"review,red"`, `"final,green"`
- Multiple colour tags CAN coexist (the CLI does not prevent this)
- Tags are visible in Finder sidebar, Get Info, and Spotlight

### Labels (exclusive colour — one at a time)
- A file has **exactly one label colour** at a time
- Setting a label via `meta set label` **replaces** the previous colour while **preserving all text tags**
- This is custom logic — no standard macOS tool handles this correctly
- The colour appears as a dot in Finder list view and as a tint in icon view

**Rule of thumb:** Use `meta set label` for colour. Use `meta add tags` / `meta set tags` for text organisation. The label and tags are independent — you can have a red label and text tags simultaneously.

### Colour names
`none` (0), `gray`/`grey` (1), `green` (2), `purple` (3), `blue` (4), `yellow` (5), `red` (6), `orange` (7)

You can use names or numbers.

## Custom Xattrs

You can write arbitrary key-value metadata to files using any namespace:

```bash
meta set xattr <file> com.agent.status "processed"
meta set xattr <file> com.agent.notes "Reviewed on Friday"
meta get xattr <file> com.agent.status
meta delete xattr <file> com.agent.status
```

### Limitations of custom xattrs
- **Invisible to Spotlight** — `mdfind` cannot search them. Use `meta search xattr` instead (which scans the filesystem directly).
- **Stripped by iCloud Drive** — if the file syncs via iCloud, custom xattrs will be lost on other machines. Only Finder Tags (`_kMDItemUserTags`) survive iCloud sync.
- **Size** — keep values under ~3 KB for best performance (stays in APFS inline tier).
- **Persistence** — custom xattrs survive file content changes, same-volume moves, `cp`, and Finder duplication. They are lost by `rsync` without `-X` and by standard `zip`.

## Search Strategies

### Fast: Spotlight (tags, labels, text)
```bash
meta search tag "project-x" --dir ~/Documents       # By tag name
meta search label red --dir ~/Documents              # By colour
meta search text "invoice Q3" --dir ~/Documents      # Full text content
meta search query "kMDItemContentType == 'com.adobe.pdf'" --dir .
```
Spotlight is fast (indexed, O(log n)) but may have a brief lag for recently-written metadata.

### Slow but comprehensive: Custom xattr scan
```bash
meta search xattr com.agent.status --dir ~/Documents
```
This scans the filesystem directly — slower but finds everything, including metadata Spotlight cannot see.

### Complex queries
```bash
meta search query "(kMDItemUserTags == 'inbox') && (kMDItemContentModificationDate > \$time.today(-7))" --dir .
```
Uses raw mdfind predicates. See Apple's Spotlight Query Syntax documentation for full predicate language.

## Common Workflows

### Tag files for a project
```bash
meta add tags <file> "project-name"
meta add tags ~/Documents/project/ "project-name" --pattern '*.md'
```

### Set a colour label for status
```bash
meta set label <file> red          # Needs attention
meta set label <file> orange       # In progress
meta set label <file> green        # Done
meta set label <file> blue         # On hold
```

### Find all files needing attention
```bash
meta search label red --dir ~/Documents
```

### Snapshot metadata before bulk changes
```bash
meta backup <file>
# ... make changes ...
meta restore <file>    # if something went wrong
```

### Full metadata audit of a file
```bash
meta get all <file>
```

## Error Handling

The tool returns JSON errors with exit code 1:

```json
{"error": "No such file: /path/to/file"}
{"error": "Unknown colour: 'turquoise'. Use: [...]" }
{"error": "Unknown verb: 'modify'. Use: get, set, add, ..."}
```

Common error scenarios:
- **File not found** — check the path exists
- **Permission denied** — file may be on a SIP-protected path, or immutable (`uchg` flag)
- **Unknown colour** — use one of the 8 named colours or 0–7
- **Command failed** — underlying tool (osxmetadata, xattr) returned an error; details in the message

## Platform Notes

- **macOS only** — this skill does not work on Linux or other Unix systems
- **APFS** — all semantics tested on Apple File System
- **Symlinks** — all operations follow symlinks to the target (correct behaviour for metadata)
- **Folders** — labels and tags work on directories identically to files
- **Finder** — Finder must be running for comment writes (uses Scripting Bridge). Label dots update on folder view refresh without restarting Finder.
- **Spotlight lag** — after writing metadata, Spotlight may take 1–2 seconds to reflect changes. The tool runs `mdimport` automatically after writes to minimise this.
